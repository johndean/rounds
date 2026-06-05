"""
Tests for app/security/roles.py — admin role gate helper.

Phase 8 scaffold (not yet wired into endpoints). Verifies the legacy
email fallback + explicit role-parameter behavior so adoption can begin
safely whenever ``get_current_user`` is extended to load
``auth_users.role`` into the ``User`` object.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.security.roles import LEGACY_ADMIN_EMAIL, is_admin, require_admin


def _user(email: str) -> SimpleNamespace:
    return SimpleNamespace(email=email)


class TestIsAdminLegacyFallback:
    """When ``role`` is not provided, behavior must match the existing
    five hardcoded ``user.email != ADMIN_EMAIL`` checks exactly."""

    def test_legacy_admin_email_is_admin(self):
        assert is_admin(_user(LEGACY_ADMIN_EMAIL)) is True

    def test_legacy_admin_email_is_case_insensitive(self):
        assert is_admin(_user(LEGACY_ADMIN_EMAIL.upper())) is True
        assert is_admin(_user(LEGACY_ADMIN_EMAIL.title())) is True

    def test_legacy_admin_email_whitespace_tolerant(self):
        assert is_admin(_user(f"  {LEGACY_ADMIN_EMAIL}  ")) is True

    def test_non_admin_email_is_not_admin(self):
        assert is_admin(_user("someone@example.com")) is False
        assert is_admin(_user("other@vin.com")) is False

    def test_empty_email_is_not_admin(self):
        assert is_admin(_user("")) is False

    def test_missing_email_attribute_is_not_admin(self):
        assert is_admin(SimpleNamespace()) is False

    def test_none_email_is_not_admin(self):
        u = SimpleNamespace()
        u.email = None
        assert is_admin(u) is False


class TestIsAdminWithExplicitRole:
    """When ``role`` is passed in, it OVERRIDES the legacy email check.
    This is the future path — callers will load
    ``auth_users.role`` and pass ``role=user.role`` to this helper."""

    def test_explicit_admin_role(self):
        assert is_admin(_user("anyone@example.com"), role="admin") is True

    def test_explicit_admin_role_case_insensitive(self):
        assert is_admin(_user("x@y.com"), role="Admin") is True
        assert is_admin(_user("x@y.com"), role="ADMIN") is True
        assert is_admin(_user("x@y.com"), role="aDmIn") is True

    def test_explicit_role_whitespace_tolerant(self):
        assert is_admin(_user("x@y.com"), role="  admin  ") is True

    def test_legacy_admin_email_can_be_demoted_via_role(self):
        # Future: johndean@vin.com is in auth_users with role='editor'
        # → legacy email no longer wins. Role parameter is authoritative.
        assert is_admin(_user(LEGACY_ADMIN_EMAIL), role="editor") is False

    def test_unknown_role_is_not_admin(self):
        assert is_admin(_user("x@y.com"), role="viewer") is False
        assert is_admin(_user("x@y.com"), role="editor") is False
        assert is_admin(_user("x@y.com"), role="") is False


class TestRequireAdmin:
    """Drop-in replacement for the local _require_admin helpers."""

    def test_admin_does_not_raise(self):
        require_admin(_user(LEGACY_ADMIN_EMAIL))  # no exception

    def test_non_admin_raises_403(self):
        with pytest.raises(HTTPException) as exc:
            require_admin(_user("someone@example.com"))
        assert exc.value.status_code == 403
        assert exc.value.detail == {"code": "ADMIN_ONLY", "message": "admin only"}

    def test_role_param_admin_does_not_raise(self):
        require_admin(_user("x@y.com"), role="admin")

    def test_role_param_non_admin_raises_403(self):
        with pytest.raises(HTTPException) as exc:
            require_admin(_user("x@y.com"), role="editor")
        assert exc.value.status_code == 403
        assert exc.value.detail == {"code": "ADMIN_ONLY", "message": "admin only"}

    def test_missing_email_raises(self):
        with pytest.raises(HTTPException) as exc:
            require_admin(SimpleNamespace())
        assert exc.value.status_code == 403


class TestPhase8AdoptionGuarantees:
    """Pinning tests — these document the contract the helper must
    preserve as adoption rolls out across the 5+ admin endpoints."""

    def test_403_detail_shape_matches_existing_endpoint_format(self):
        """Frontend error handling parses this exact dict shape today."""
        with pytest.raises(HTTPException) as exc:
            require_admin(_user("non-admin@example.com"))
        # Existing email_templates.py:41-44 raises this exact shape.
        # Existing settings.py admin gate raises this exact shape.
        # is_admin's negative path MUST produce the same body.
        assert exc.value.detail == {"code": "ADMIN_ONLY", "message": "admin only"}

    def test_legacy_admin_still_works_without_role_param(self):
        """Until get_current_user loads auth_users.role, callers will
        call require_admin(user) without the role kwarg. The single
        existing admin (johndean@vin.com) must still pass."""
        require_admin(_user(LEGACY_ADMIN_EMAIL))  # no exception
