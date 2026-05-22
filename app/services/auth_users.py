"""
Auth users — bcrypt-hashed password storage backed by the `auth_users` table.

Pure functions, no FastAPI imports. Usable from:
  • app/main.py lifespan (one-shot seed from AUTH_USERS env on first boot)
  • app/auth.py (login + token validation lookup)
  • app/api/settings.py (Settings → Auth & Logins CRUD)
  • tests

The plaintext-in-env debt (CLAUDE.md + audit §10 finding #7) is replaced by
this module. `seed_from_env_if_empty()` performs the one-shot migration on
first boot — subsequent boots short-circuit via the row-count check.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from passlib.context import CryptContext
from sqlalchemy import text

logger = logging.getLogger(__name__)

# bcrypt is the only scheme today; `deprecated="auto"` future-proofs us for
# argon2 migration without breaking existing hashes.
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Matches the ADMIN_EMAIL constant in app/api/settings.py — kept in sync by
# convention. When a future commit adds role-based middleware, this becomes
# a single source of truth via app/config.py.
_ADMIN_EMAIL = "johndean@vin.com"


@dataclass(frozen=True, slots=True)
class AuthUserRow:
    id:               str
    email:            str
    password_hash:    str
    role:             str
    is_active:        bool
    last_login_at:    Optional[str]


def hash_password(plain: str) -> str:
    """Bcrypt-hash a plaintext password. ~50ms by design."""
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt verify. Returns False on any error (corrupt hash, etc.)."""
    try:
        return _pwd.verify(plain, hashed)
    except Exception:  # noqa: BLE001 — never let a hash error leak; treat as auth failure
        return False


def lookup_user(engine_or_conn, email: str) -> Optional[AuthUserRow]:
    """
    Single indexed lookup by email (case-insensitive). Returns None if no row.

    Accepts either a SQLAlchemy Engine (creates a short-lived connection) or
    an existing Connection (caller manages lifecycle).
    """
    sql = text(
        """
        SELECT id, email, password_hash, role, is_active, last_login_at
          FROM auth_users
         WHERE lower(email) = lower(:e)
         LIMIT 1
        """
    )
    if hasattr(engine_or_conn, "connect"):
        # It's an Engine — open a short connection.
        with engine_or_conn.connect() as conn:
            row = conn.execute(sql, {"e": email}).mappings().first()
    else:
        # Assume it's already a Connection.
        row = engine_or_conn.execute(sql, {"e": email}).mappings().first()

    if row is None:
        return None
    return AuthUserRow(
        id=str(row["id"]),
        email=row["email"],
        password_hash=row["password_hash"],
        role=row["role"],
        is_active=bool(row["is_active"]),
        last_login_at=row["last_login_at"].isoformat() if row["last_login_at"] else None,
    )


def user_is_active(engine_or_conn, email: str) -> bool:
    """
    Cheap existence + active check used by get_current_user() on every
    protected request. Indexed SELECT, ~1ms with warm pool.
    """
    sql = text(
        """
        SELECT 1 FROM auth_users
         WHERE lower(email) = lower(:e) AND is_active = TRUE
         LIMIT 1
        """
    )
    if hasattr(engine_or_conn, "connect"):
        with engine_or_conn.connect() as conn:
            return conn.execute(sql, {"e": email}).first() is not None
    return engine_or_conn.execute(sql, {"e": email}).first() is not None


def touch_last_login(engine, email: str) -> None:
    """
    Best-effort `UPDATE auth_users SET last_login_at = now()`. Never raises;
    a logged warning is enough — failing to update the timestamp is not a
    reason to fail a login.
    """
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE auth_users
                       SET last_login_at = now(), updated_at = now()
                     WHERE lower(email) = lower(:e)
                    """
                ),
                {"e": email},
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"touch_last_login failed for {email}: {exc}")


def seed_from_env_if_empty(engine, auth_users_csv: str) -> int:
    """
    One-shot seed from the AUTH_USERS env CSV. Returns the number of rows
    inserted. Idempotent: returns 0 if the table already has any rows.

    Called from app/main.py lifespan. Safe to run on multiple instances
    concurrently — the row-count check short-circuits on second-and-later
    boots, and `ON CONFLICT DO NOTHING` covers the race where two instances
    boot together.

    Imports the existing _parse_auth_users helper from app.auth so the
    parsing semantics never diverge.
    """
    if not auth_users_csv:
        return 0
    # Lazy import to avoid a circular dep at module load (app.auth itself
    # may import from this module in a future refactor).
    from app.auth import _parse_auth_users

    parsed = _parse_auth_users(auth_users_csv)
    if not parsed:
        return 0

    with engine.begin() as conn:
        existing = conn.execute(text("SELECT count(*) FROM auth_users")).scalar() or 0
        if existing > 0:
            return 0
        seeded = 0
        for email, password in parsed.items():
            role = "admin" if email.lower() == _ADMIN_EMAIL.lower() else "user"
            hashed = hash_password(password)
            result = conn.execute(
                text(
                    """
                    INSERT INTO auth_users (email, password_hash, role)
                    VALUES (:e, :h, :r)
                    ON CONFLICT ((lower(email))) DO NOTHING
                    """
                ),
                {"e": email, "h": hashed, "r": role},
            )
            # rowcount is 1 on insert, 0 if the unique-index ON CONFLICT fired.
            seeded += result.rowcount or 0
        return seeded
