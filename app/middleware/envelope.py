"""
Response envelope — MIC §9.1 locked invariant.

Every JSON response MUST use {success, data, error, meta}.
  success: bool
  data:    the response payload (or null on error)
  error:   {code, message, details, retryable} (or null on success)
  meta:    {request_id, timestamp}

Middleware wraps every JSON response that isn't already an envelope.
Custom exception classes (MICException + subclasses) map to error responses
with the locked error code → HTTP status mapping.

Closes 🟠 #11 (envelope dropped across all responses) + 🟡 #12 (request_id
not in response body — header-only).

Phase 7i / parity-3.

Critical invariant: every JSON response MUST be envelope-shaped. The middleware
is the only place this contract is enforced. Direct `Response(json.dumps(...))`
in a handler bypasses it — don't do that.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ─── Error code → HTTP status (locked enum, MIC §9.2) ───────────────────────


ERROR_HTTP_MAP: dict[str, int] = {
    "INVALID_INPUT":     400,
    "VALIDATION_FAILED": 400,
    "INVALID_TIMESTAMP": 400,   # Phase 4 — segment time-edit validation (start_ms/end_ms)
    "EMPTY_REORDER":     400,   # Phase 6.1 — chat/polls reorder with empty ids array
    "UNKNOWN_CHAT_IDS":  400,   # Phase 6.1 — chat reorder with ids not in session
    "UNKNOWN_POLL_IDS":  400,   # Phase 6.1 — polls reorder with ids not in session
    "UNAUTHORIZED":      401,
    "FORBIDDEN":         403,
    "ADMIN_ONLY":        403,   # Phase 8 step-3 — require_admin
    "NOT_FOUND":         404,
    "CONFLICT":          409,
    "TEMPLATE_LOCKED":   409,
    "RATE_LIMITED":      429,
    "PIPELINE_FAILED":   500,
    "INTERNAL_ERROR":    500,
}

RETRYABLE_CODES = {"INTERNAL_ERROR", "RATE_LIMITED"}


# ─── Exception hierarchy ────────────────────────────────────────────────────


class MICException(Exception):
    """Base — every handler-raised domain error subclasses this."""

    def __init__(self, code: str, message: str, details: Optional[dict] = None) -> None:
        if code not in ERROR_HTTP_MAP:
            raise ValueError(f"Unknown error code '{code}' — not in locked enum")
        self.code = code
        self.message = message
        self.details = details or {}
        self.http_status = ERROR_HTTP_MAP[code]
        self.retryable = code in RETRYABLE_CODES
        super().__init__(message)


class InvalidInputError(MICException):
    def __init__(self, message: str = "Malformed request body or wrong types", details: Optional[dict] = None):
        super().__init__("INVALID_INPUT", message, details)


class ValidationFailedError(MICException):
    def __init__(self, message: str = "Validation failed", details: Optional[dict] = None):
        super().__init__("VALIDATION_FAILED", message, details)


class UnauthorizedError(MICException):
    def __init__(self, message: str = "Missing or invalid authentication token"):
        super().__init__("UNAUTHORIZED", message)


class ForbiddenError(MICException):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__("FORBIDDEN", message)


class NotFoundError(MICException):
    def __init__(self, message: str = "Resource does not exist"):
        super().__init__("NOT_FOUND", message)


class ConflictError(MICException):
    def __init__(self, message: str = "State conflict", details: Optional[dict] = None):
        super().__init__("CONFLICT", message, details)



class RateLimitedError(MICException):
    def __init__(self, retry_after: int, message: str = "Concurrent session limit exceeded"):
        self.retry_after = retry_after
        super().__init__("RATE_LIMITED", message)


class PipelineFailedError(MICException):
    def __init__(self, message: str = "Unrecoverable pipeline stage failure"):
        super().__init__("PIPELINE_FAILED", message)


class InternalError(MICException):
    def __init__(self, message: str = "Internal server error"):
        super().__init__("INTERNAL_ERROR", message)


# ─── Envelope helpers ───────────────────────────────────────────────────────


def _meta(request_id: Optional[str] = None) -> dict:
    return {
        "request_id": request_id or str(uuid.uuid4()),
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }


def success_response(data: Any, status_code: int = 200, request_id: Optional[str] = None) -> JSONResponse:
    """Produce a compliant success envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data":    data,
            "error":   None,
            "meta":    _meta(request_id),
        },
    )


def error_response(
    code: str,
    message: str,
    http_status: Optional[int] = None,
    details: Optional[dict] = None,
    retryable: Optional[bool] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Produce a compliant error envelope. code must be in the locked enum."""
    if code not in ERROR_HTTP_MAP:
        code = "INTERNAL_ERROR"
    return JSONResponse(
        status_code=http_status or ERROR_HTTP_MAP[code],
        content={
            "success": False,
            "data":    None,
            "error": {
                "code":      code,
                "message":   message,
                "details":   details or {},
                "retryable": retryable if retryable is not None else code in RETRYABLE_CODES,
            },
            "meta": _meta(request_id),
        },
    )


# ─── Middleware ─────────────────────────────────────────────────────────────


_EXEMPT_PATHS = {
    "/docs", "/redoc", "/openapi.json",
    "/favicon.ico",
}


def _is_exempt(path: str) -> bool:
    # WebSocket upgrade requests + docs assets — not wrapped.
    return (
        path in _EXEMPT_PATHS
        or path.startswith("/ws")
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path.startswith("/openapi")
    )


class EnvelopeMiddleware(BaseHTTPMiddleware):
    """
    Wraps every non-envelope JSON response in {success, data, error, meta}.

    Skips:
      • non-JSON responses (HTML, binary, streaming)
      • responses already wrapped (top-level keys exactly {success, data, error, meta})
      • 204 No Content
      • WebSocket + docs paths
    """

    async def dispatch(self, request: Request, call_next):
        if _is_exempt(request.url.path):
            return await call_next(request)

        try:
            response: Response = await call_next(request)
        except MICException as exc:
            return error_response(
                code=exc.code,
                message=exc.message,
                http_status=exc.http_status,
                details=exc.details,
                retryable=exc.retryable,
                request_id=getattr(request.state, "request_id", None),
            )

        # 204 / 304 / streaming → leave alone
        if response.status_code in (204, 304):
            return response

        ctype = (response.headers.get("content-type") or "").lower()
        if "application/json" not in ctype:
            return response

        # Read body — Starlette returns a StreamingResponse-like iterator.
        body_bytes = b""
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            body_bytes += chunk

        try:
            body = json.loads(body_bytes) if body_bytes else None
        except Exception:  # noqa: BLE001
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=ctype,
            )

        request_id = getattr(request.state, "request_id", None)

        # Already-wrapped envelope: ensure meta.request_id matches request.state.
        if isinstance(body, dict) and {"success", "data", "error", "meta"} <= set(body.keys()):
            if request_id:
                meta = body.get("meta") or {}
                if isinstance(meta, dict):
                    meta.setdefault("request_id", request_id)
                    body["meta"] = meta
            return JSONResponse(
                content=body,
                status_code=response.status_code,
                headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
            )

        # FastAPI HTTPException default: {"detail": ...}
        if (
            response.status_code >= 400
            and isinstance(body, dict)
            and set(body.keys()) <= {"detail"}
        ):
            detail = body.get("detail")
            if isinstance(detail, dict):
                code = detail.get("code") or "INTERNAL_ERROR"
                message = detail.get("message") or str(detail)
                details = {k: v for k, v in detail.items() if k not in ("code", "message")}
            else:
                code = _status_to_code(response.status_code)
                message = str(detail) if detail else _status_to_code(response.status_code)
                details = {}
            return error_response(
                code=code if code in ERROR_HTTP_MAP else _status_to_code(response.status_code),
                message=message,
                http_status=response.status_code,
                details=details,
                request_id=request_id,
            )

        # Success — wrap.
        if response.status_code < 400:
            return success_response(body, status_code=response.status_code, request_id=request_id)

        # Other error shapes — wrap as INTERNAL_ERROR with body as details.
        return error_response(
            code=_status_to_code(response.status_code),
            message=_status_to_code(response.status_code),
            http_status=response.status_code,
            details={"body": body} if body is not None else {},
            request_id=request_id,
        )


def _status_to_code(status: int) -> str:
    return {
        400: "INVALID_INPUT",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        429: "RATE_LIMITED",
    }.get(status, "INTERNAL_ERROR" if status >= 500 else "INVALID_INPUT")
