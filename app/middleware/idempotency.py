"""
Idempotency-Key middleware — replay-cached responses for mutating endpoints.

Pattern (audit §6 IDEMPOTENCY_KEY_TTL_SECONDS=86400):
  Client sends `Idempotency-Key: <opaque-string>` on POST.
  First call → execute handler → cache response in Redis (key+body hash).
  Same key within TTL → return cached response, skip handler.

Phase 6o / U139-U140.
"""
from __future__ import annotations

import hashlib
import json
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


_IDEMP_KEY_TPL = "idemp:{user}:{key}:{body_hash}"


_PROTECTED_PATHS = (
    "/v1/sessions",
    "/v1/gcs/upload-complete",
    "/v1/improvements",
    "/v1/audit",
)


def _redis():
    import redis as _redis

    return _redis.from_url(settings.REDIS_URL, decode_responses=True)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Only intercept POST + PATCH on protected paths with an Idempotency-Key.
        if request.method not in ("POST", "PATCH"):
            return await call_next(request)
        if not any(request.url.path.startswith(p) for p in _PROTECTED_PATHS):
            return await call_next(request)

        idemp_key = request.headers.get("idempotency-key")
        if not idemp_key:
            return await call_next(request)

        # Compute body hash (sha256) — must read + replay body for downstream handler.
        body = await request.body()
        body_hash = hashlib.sha256(body).hexdigest()[:16]
        # User scoping — falls back to anonymous if no auth present.
        user = request.headers.get("authorization", "anon")[-32:]
        cache_key = _IDEMP_KEY_TPL.format(user=user, key=idemp_key, body_hash=body_hash)

        try:
            r = _redis()
            try:
                cached = r.get(cache_key)
            finally:
                r.close()
            if cached:
                logger.info(f"idempotency: replay {cache_key[:60]}")
                payload = json.loads(cached)
                return Response(
                    content=payload["body"],
                    status_code=payload["status_code"],
                    headers={"content-type": payload.get("media_type", "application/json"),
                             "x-idempotency-replay": "true"},
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"idempotency: redis read failed — {exc}")

        # Replay the consumed body to the downstream handler.
        async def _receive() -> dict:
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = _receive  # type: ignore[attr-defined]
        response = await call_next(request)

        # Cache the response (only 2xx).
        if 200 <= response.status_code < 300:
            try:
                # Read the streaming body
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk
                r = _redis()
                try:
                    r.setex(
                        cache_key,
                        settings.IDEMPOTENCY_KEY_TTL_SECONDS,
                        json.dumps({
                            "body":        response_body.decode("utf-8", errors="replace"),
                            "status_code": response.status_code,
                            "media_type":  response.media_type or "application/json",
                        }),
                    )
                finally:
                    r.close()
                # Rebuild response with the consumed body
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"idempotency: cache write failed — {exc}")
                return response
        return response
