"""
Idempotency-Key middleware — replay-cached responses for mutating endpoints.

Pattern (audit §6 IDEMPOTENCY_KEY_TTL_SECONDS=86400):
  Client sends `Idempotency-Key: <opaque-string>` on POST/PATCH.

  • First call → SETNX inflight marker (TTL 300s) → execute handler → cache
    response in Redis (key + body hash).
  • Same key + same body within TTL → return cached response, skip handler.
  • Same key + DIFFERENT body within TTL → 409 CONFLICT (#9).
  • Same key while first call still in-flight → 202 Accepted with
    {status: "processing"} (#8 — prevents duplicate concurrent submits).

Phase 7i (parity-3): closes 🟠 #8 + #9.
"""
from __future__ import annotations

import hashlib
import json
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


_PROTECTED_PATHS = (
    "/v1/sessions",
    "/v1/gcs/upload-complete",
    "/v1/improvements",
    "/v1/audit",
)

# Two-tier Redis keyspace: cache key includes body hash; inflight key + body-hash
# anchor (per Idempotency-Key) hold the canonical body hash so we can detect
# different payloads under the same key.
_CACHE_TPL    = "idemp:cache:{user}:{key}:{body_hash}"
_INFLIGHT_TPL = "idemp:inflight:{user}:{key}"
_ANCHOR_TPL   = "idemp:anchor:{user}:{key}"

_INFLIGHT_TTL = 300  # 5 min — caps the longest legitimate request


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

        body = await request.body()
        body_hash = hashlib.sha256(body).hexdigest()[:32]
        user = request.headers.get("authorization", "anon")[-32:]

        cache_key    = _CACHE_TPL.format(user=user, key=idemp_key, body_hash=body_hash)
        inflight_key = _INFLIGHT_TPL.format(user=user, key=idemp_key)
        anchor_key   = _ANCHOR_TPL.format(user=user, key=idemp_key)

        # Phase 1: check cache hit (same key + same body).
        try:
            r = _redis()
            try:
                cached = r.get(cache_key)
            finally:
                r.close()
            if cached:
                logger.info(f"idempotency: replay cache hit {cache_key[-60:]}")
                payload = json.loads(cached)
                return Response(
                    content=payload["body"],
                    status_code=payload["status_code"],
                    headers={"content-type": payload.get("media_type", "application/json"),
                             "x-idempotency-replay": "true"},
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"idempotency: redis read failed — {exc}")

        # Phase 2: check anchor — has this key been used with a different body? (#9)
        try:
            r = _redis()
            try:
                anchor = r.get(anchor_key)
            finally:
                r.close()
        except Exception:  # noqa: BLE001
            anchor = None
        if anchor and anchor != body_hash:
            logger.warning(
                f"idempotency: 409 — key reused with different body "
                f"(prior={anchor[:12]}, current={body_hash[:12]})"
            )
            return Response(
                content=json.dumps({
                    "success": False,
                    "data": None,
                    "error": {
                        "code":      "CONFLICT",
                        "message":   "Idempotency-Key reused with a different request body",
                        "details":   {"key": idemp_key[:60]},
                        "retryable": False,
                    },
                    "meta": {"request_id": getattr(request.state, "request_id", None) or ""},
                }),
                status_code=409,
                media_type="application/json",
            )

        # Phase 3: try to acquire the inflight slot atomically (#8).
        try:
            r = _redis()
            try:
                acquired = bool(r.set(inflight_key, body_hash, nx=True, ex=_INFLIGHT_TTL))
                if acquired:
                    # Anchor the body hash so future reuses can compare.
                    r.set(anchor_key, body_hash, ex=settings.IDEMPOTENCY_KEY_TTL_SECONDS)
            finally:
                r.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"idempotency: inflight setnx failed — {exc}")
            acquired = True  # fail-open: better to potentially double-execute than block

        if not acquired:
            logger.info(f"idempotency: in-flight 202 for {idemp_key[:60]}")
            return Response(
                content=json.dumps({
                    "success": True,
                    "data": {"status": "processing", "key": idemp_key[:60]},
                    "error": None,
                    "meta": {"request_id": getattr(request.state, "request_id", None) or ""},
                }),
                status_code=202,
                media_type="application/json",
                headers={"x-idempotency-inflight": "true"},
            )

        # Phase 4: replay body to downstream handler.
        async def _receive() -> dict:
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = _receive  # type: ignore[attr-defined]

        try:
            response = await call_next(request)
        finally:
            # Always release the inflight slot.
            try:
                r = _redis()
                try:
                    r.delete(inflight_key)
                finally:
                    r.close()
            except Exception:  # noqa: BLE001
                pass

        # Phase 5: cache 2xx responses for full TTL.
        # BR-012 — Idempotency-key TTL (86400s / 24h).
        # See docs/BUSINESS_RULES.md#br-012.
        # Why: mobile-network retries can drift up to ~24h (offline → resume).
        # Inside the window, the same Idempotency-Key returns the cached
        # response (zero re-execution). Outside the window the key is forgotten
        # — a same-key resubmit then runs fresh. Shortening risks double-effect
        # in the gap. Lengthening grows Redis storage linearly.
        if 200 <= response.status_code < 300:
            try:
                response_body = b""
                async for chunk in response.body_iterator:  # type: ignore[attr-defined]
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
