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

  1. (commit 7882348) Ship the helper + tests. No endpoint changes.
     No change to `get_current_user`.
  2. (future) Extend `get_current_user` to load `auth_users.role` into
     the `User` object.
  3. (future) Replace the five hardcoded `_require_admin` patterns with
     `from app.security.roles import require_admin`.

Phase 7.3 (2026-06-05) tightened the helper to byte-identical legacy
semantics — case-sensitive exact equality on both the role-param and
legacy-email paths. The pre-tightening implementation accepted
``JOHNDEAN@VIN.COM`` and whitespace-padded emails as admin, silently
widening the admit set; the verification workflow flagged this and the
helper is now a strict drop-in replacement for the existing
``user.email != ADMIN_EMAIL`` patterns. See ``is_admin`` docstring for
the formal contract.

Related ADRs: ADR-001 (authentication).
Related business rules: BR-001 (LEGACY_ADMIN_EMAIL bootstrap admin gate).
"""
from __future__ import annotations

from typing import Optional, Protocol

from fastapi import HTTPException


# BR-001 — Bootstrap admin email gate. See docs/BUSINESS_RULES.md#br-001.
# Why: Rounds still needs a single named superadmin until `auth_users.role`
# is wired into every operator surface. This constant gates `/v1/diag/*`,
# `SESSION_TRASH_ALLOWED` (BR-002), and the editor Admin tab.
# Risk if changed: changing the literal moves all admin power to whatever
# new address is set. Removing the constant breaks every callsite.
# Migration path: see ADR-001-authentication.md "When this ADR should be
# revisited" — retire after `auth_users.role` is loaded by get_current_user
# and every callsite passes `role=user.role`.
#
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
         ``auth_users.role`` for this user), use it directly. Case-
         sensitive exact match against the literal ``"admin"`` — same
         shape the DB column stores. Non-canonical casing or whitespace
         in the role string MUST fail; the database enforces canonical
         casing and a leaky helper would mask data-integrity bugs.
      2. Otherwise fall back to comparing ``user.email`` against
         ``LEGACY_ADMIN_EMAIL``. Case-sensitive, whitespace-sensitive
         exact match — mirrors the existing hardcoded checks in
         ``email_templates.py:_require_admin`` etc. so a swap-in
         migration to this helper is byte-identical behavior.

    Verification workflow 2026-06-05 surfaced that earlier versions of
    this helper were case-insensitive and whitespace-tolerant, which
    silently widened the admin set vs. the legacy gate. Tightened to
    exact-match per that finding (HIGH-confidence MEDIUM severity).
    Callers that want lenient matching must normalize input upstream.

    Returns False when the user object lacks an ``email`` attribute or
    has an empty email. Never raises.
    """
    if role is not None:
        return role == "admin"
    if not hasattr(user, "email") or not getattr(user, "email"):
        return False
    return user.email == LEGACY_ADMIN_EMAIL


def require_admin(
    user: _HasEmail,
    *,
    role: Optional[str] = None,
    message: str = "admin only",
) -> None:
    """
    Raise HTTPException(403, ADMIN_ONLY) if ``user`` is not an admin.

    Drop-in replacement for the local ``_require_admin`` helpers in
    `email_templates.py`, `settings.py`, `email_debug.py`, and the 3
    sessions.py admin gates. The 403 detail body matches the
    ``email_templates.py`` shape (``{"code": "ADMIN_ONLY", "message": ...}``);
    sites that previously raised string-detail 403s (settings.py,
    email_debug.py, sessions.py) move to this richer shape as part of
    adoption. ``message`` preserves the per-site descriptive text
    those sites used (e.g. "Only admin can permanently delete sessions").
    """
    if not is_admin(user, role=role):
        raise HTTPException(
            status_code=403,
            detail={"code": "ADMIN_ONLY", "message": message},
        )
