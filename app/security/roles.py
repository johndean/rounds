"""
Admin-role gate helper.

Replaces the ad-hoc `user.email != ADMIN_EMAIL` checks scattered across
admin endpoints. The hardcoded check exists in (at least) five places
today: `app/api/email_templates.py:39-44`, `app/api/settings.py:20-25`,
`app/api/email_debug.py`, and two adjacent admin routes called out by
the Phase 8 audit (`docs/audits/permissions-open-builder-2026-06-04.md`).

**Phase 8 scaffold only — not yet wired into any endpoint.** The audit
identified that `auth_users.role` already exists (migration 045) but is
never consulted by `get_current_user`. The migration path is:

  1. (this commit) Ship the helper + tests. No endpoint changes. No
     change to `get_current_user`. Behavior identical to current state.
  2. (future) Extend `get_current_user` to load `auth_users.role` into
     the `User` object.
  3. (future) Replace the five hardcoded `_require_admin` patterns with
     `from app.security.roles import require_admin`.

During step 1 (now), callers can already begin using `require_admin`
without passing a role — it falls back to the legacy single-admin email
check, so behavior is a strict superset of what exists today.
"""
from __future__ import annotations

from typing import Optional, Protocol

from fastapi import HTTPException


# Legacy single-admin fallback. Kept during the cutover window — once
# `auth_users.role` is loaded by `get_current_user` and callers pass
# `role=user.role`, this constant becomes dead code (remove with the
# step-3 cleanup commit).
LEGACY_ADMIN_EMAIL = "johndean@vin.com"


class _HasEmail(Protocol):
    """Minimal user shape this helper requires."""
    email: str


def is_admin(user: _HasEmail, *, role: Optional[str] = None) -> bool:
    """
    Return True if ``user`` has admin privileges.

    Resolution order:
      1. If ``role`` is provided (caller has already loaded
         ``auth_users.role`` for this user), use it directly. Case
         insensitive — "admin", "ADMIN", "Admin" all match.
      2. Otherwise fall back to comparing ``user.email`` against
         ``LEGACY_ADMIN_EMAIL``. Case insensitive.

    Returns False when the user object lacks an ``email`` attribute or
    has an empty email. Never raises.
    """
    if role is not None:
        return role.strip().lower() == "admin"
    if not hasattr(user, "email") or not getattr(user, "email"):
        return False
    return user.email.strip().lower() == LEGACY_ADMIN_EMAIL.lower()


def require_admin(user: _HasEmail, *, role: Optional[str] = None) -> None:
    """
    Raise HTTPException(403, ADMIN_ONLY) if ``user`` is not an admin.

    Drop-in replacement for the local ``_require_admin`` helpers in
    `email_templates.py`, `settings.py`, `email_debug.py`. The 403
    detail body matches those callers verbatim so frontend error
    handling is unchanged when adoption begins.
    """
    if not is_admin(user, role=role):
        raise HTTPException(
            status_code=403,
            detail={"code": "ADMIN_ONLY", "message": "admin only"},
        )
