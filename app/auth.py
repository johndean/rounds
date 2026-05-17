"""
Auth — JWT bearer-token login backed by the AUTH_USERS env CSV.

Ports MIC's `app/auth.py` posture (audit §6 + §10 finding #7):
  • AUTH_USERS is a comma-separated `email:password,email:password,...` CSV.
  • Plaintext passwords in env. Known-debt; rotation = regenerate full CSV
    + redeploy. Schedule for hashed-at-rest migration outside this plan.
  • Tokens: HS256, signed with API_SECRET_KEY, expire after
    ACCESS_TOKEN_EXPIRE_MINUTES (default 480 = 8 hours).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings


# ─── User registry ───────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class User:
    email: str


def _parse_auth_users(csv: str) -> dict[str, str]:
    """
    Parse AUTH_USERS into {email: password}. Robust to surrounding whitespace
    and trailing commas. Empty entries are skipped.
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


_USER_DB: dict[str, str] = _parse_auth_users(settings.AUTH_USERS)


def authenticate(email: str, password: str) -> Optional[User]:
    """Constant-time-ish lookup against AUTH_USERS. Returns User on success."""
    expected = _USER_DB.get(email.lower())
    if expected is None:
        return None
    if not _constant_time_eq(expected, password):
        return None
    return User(email=email.lower())


def _constant_time_eq(a: str, b: str) -> bool:
    """Byte-equal comparison that doesn't short-circuit on first mismatch."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a.encode("utf-8"), b.encode("utf-8")):
        result |= x ^ y
    return result == 0


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
    if not token:
        raise _credentials_exception()
    try:
        payload = jwt.decode(token, settings.API_SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise _credentials_exception() from exc

    email = payload.get("sub")
    if not isinstance(email, str):
        raise _credentials_exception()
    # Still in the registry? (AUTH_USERS could have rotated)
    if email.lower() not in _USER_DB:
        raise _credentials_exception()
    return User(email=email.lower())


CurrentUser = Annotated[User, Depends(get_current_user)]
