"""
app.security — auth/role helpers shared across API routes and tasks.

Phase 8 of the 2026-06-04 stakeholder remediation introduced this package
to centralize the admin-role gate. Today the package contains a single
helper (roles.py); future work may add scope-token verification,
audit-event guards, etc.
"""
