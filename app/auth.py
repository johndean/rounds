"""
Auth — JWT bearer-token login backed by the `auth_users` table (bcrypt-hashed).

Replaces the plaintext AUTH_USERS env CSV that was loaded into an in-memory
dict at import time (audit §6 + §10 finding #7). AUTH_USERS still exists as
the DR bootstrap source: on first boot `app/services/auth_users.seed_from_env_if_empty`
copies it into the table with bcrypt-hashed passwords. After that, the env
var is unused and can be cleared.

Tokens are unchanged: HS256, signed with API_SECRET_KEY, expire after
ACCESS_TOKEN_EXPIRE_MINUTES (default 480 = 8 hours).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import settings

logger = logging.getLogger(__name__)


# ─── User registry ───────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class User:
    email: str


def _parse_auth_users(csv: str) -> dict[str, str]:
    """
    Parse AUTH_USERS into {email: password}. Robust to surrounding whitespace
    and trailing commas. Empty entries are skipped.

    Kept for: (a) the boot-time seed in app/services/auth_users.py, and
    (b) tests/test_auth.py which validates the parsing edge cases directly.
    No longer used as a live login registry.
    """
    out: dict[str, str] = {}
    for entry in csv.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            continue
        email, _, password = entry.partition(":")
        email = email.strip().lower()
        password = password.strip()
        if not email or not password:
            continue
        out[email] = password
    return out


# ─── DB engine (lazy, module-scoped) ──────────────────────────────────────
# Created on first authentication call. Reused across logins + every
# protected request's `get_current_user` check. `pool_pre_ping=True` keeps
# the connection healthy across Postgres restarts.
_engine: Optional[Engine] = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        _engine = create_engine(sync_url, pool_pre_ping=True, pool_size=5, max_overflow=2)
    return _engine


# ─── Authentication ──────────────────────────────────────────────────────
def authenticate(email: str, password: str) -> Optional[User]:
    """
    Verify (email, password) against the `auth_users` table. Returns a `User`
    on success, `None` on any failure (unknown email, inactive, wrong password).

    Bcrypt verify is ~50ms by design — the cost is what makes brute-force
    attacks expensive. Only fires on POST /v1/auth/login, not per-request.
    """
    from app.services.auth_users import lookup_user, verify_password, touch_last_login

    engine = _get_engine()
    try:
        row = lookup_user(engine, email)
        if row is None or not row.is_active:
            return None
        if not verify_password(password, row.password_hash):
            return None
        # Best-effort timestamp update; never blocks login on failure.
        touch_last_login(engine, row.email)
        return User(email=row.email.lower())
    except Exception as exc:  # noqa: BLE001 — DB outage shouldn't 500 the login endpoint
        logger.error(f"authenticate({email}) DB error: {exc}", exc_info=True)
        return None


# ─── Token issuance / verification ────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


def create_access_token(email: str) -> TokenResponse:
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": email.lower(), "exp": expire}
    token = jwt.encode(payload, settings.API_SECRET_KEY, algorithm=settings.ALGORITHM)
    return TokenResponse(access_token=token, expires_in=int(expires_delta.total_seconds()))


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(token: Annotated[Optional[str], Depends(oauth2_scheme)]) -> User:
    """
    Decode the JWT, then verify the user is still active in the DB. Both
    legs must pass — an admin can revoke a session by disabling/deleting a
    user, and the next request rejects the still-valid token.

    The DB check is a single indexed `SELECT 1 … WHERE lower(email)=… AND is_active=TRUE`
    — ~1ms with a warm pool, identical user-facing latency to the prior
    dict lookup.
    """
    from app.services.auth_users import user_is_active

    if not token:
        raise _credentials_exception()
    try:
        payload = jwt.decode(token, settings.API_SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise _credentials_exception() from exc

    email = payload.get("sub")
    if not isinstance(email, str):
        raise _credentials_exception()
    try:
        if not user_is_active(_get_engine(), email):
            raise _credentials_exception()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — DB outage → fail closed
        logger.error(f"get_current_user DB check failed for {email}: {exc}")
        raise _credentials_exception() from exc
    return User(email=email.lower())


CurrentUser = Annotated[User, Depends(get_current_user)]
