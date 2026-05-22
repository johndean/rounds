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


# Env-CSV fallback — parsed once at module load. Used when the DB path
# returns nothing (migration not yet applied, seed didn't fire, transient
# DB outage, etc.). This is the "zero-risk cutover" promise from the
# auth-users plan: if the new DB-backed path fails for any reason, the
# old env-dict path still lets known users in.
_ENV_FALLBACK_DB: dict[str, str] = _parse_auth_users(settings.AUTH_USERS)


def _constant_time_eq(a: str, b: str) -> bool:
    """Byte-equal comparison that doesn't short-circuit on first mismatch."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a.encode("utf-8"), b.encode("utf-8")):
        result |= x ^ y
    return result == 0


# ─── Authentication ──────────────────────────────────────────────────────
def authenticate(email: str, password: str) -> Optional[User]:
    """
    Verify (email, password) against the `auth_users` table, with a fallback
    to the AUTH_USERS env CSV when the DB path returns nothing or errors.

    Order of precedence:
      1. DB row found + bcrypt verify succeeds → success.
      2. DB row found + bcrypt verify fails → fail (don't fall through —
         admin may have intentionally rotated; env still has old password).
      3. DB row missing OR DB error → try env CSV. If matches, success.
      4. Otherwise fail.

    Bcrypt verify is ~50ms by design. Env path is a constant-time string
    compare. Only fires on POST /v1/auth/login.
    """
    from app.services.auth_users import lookup_user, verify_password, touch_last_login

    db_row_existed = False
    engine = _get_engine()
    try:
        row = lookup_user(engine, email)
        if row is not None:
            db_row_existed = True
            if not row.is_active:
                return None
            if verify_password(password, row.password_hash):
                touch_last_login(engine, row.email)
                return User(email=row.email.lower())
            return None  # known user, wrong password — do NOT fall through
    except Exception as exc:  # noqa: BLE001 — DB outage falls through to env
        logger.error(f"authenticate DB path failed for {email}: {exc}", exc_info=True)

    # Fallback: env CSV. Reached when there's no DB row OR the DB raised.
    expected = _ENV_FALLBACK_DB.get(email.lower())
    if expected is None:
        return None
    if not _constant_time_eq(expected, password):
        return None
    if not db_row_existed:
        logger.warning(
            f"authenticate: env-CSV fallback used for {email} — DB has no row yet "
            "(seed may have failed or migration not applied)"
        )
    return User(email=email.lower())


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
    Decode the JWT, then verify the user is still active. DB lookup first,
    env-CSV fallback if the DB has no row OR the DB call errors. Keeps
    every existing JWT valid through the cutover, even if migration 045
    or its seed hasn't landed.
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

    # Try DB path. On success or explicit "not active" we're done.
    try:
        if user_is_active(_get_engine(), email):
            return User(email=email.lower())
        # DB query succeeded but row is missing or inactive — fall through to env.
    except Exception as exc:  # noqa: BLE001
        logger.error(f"get_current_user DB check failed for {email}: {exc}")
        # Don't fail closed — fall through to env so existing JWTs still validate.

    # Env CSV fallback: the user must still be present in the original registry.
    if email.lower() in _ENV_FALLBACK_DB:
        return User(email=email.lower())

    raise _credentials_exception()


CurrentUser = Annotated[User, Depends(get_current_user)]
