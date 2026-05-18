"""
Request ID middleware — assigns a UUID4 to every request and exposes it
on the response as `x-request-id`. Client uses it for support tickets +
log correlation. Closes residual 🟡 (no client-side request_id for tracing).

Phase 7h.
"""
from __future__ import annotations

import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Respect inbound id (load balancer / proxy) or mint a new one.
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
