"""
Phase 1 — session_locks route smoke tests.

Audit IDs closed: E1.
Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 1.

We follow the same posture as tests/test_help_ask.py — assert the router
is mounted (401 vs 404 proves the prefix is wired) and that the auth gate
fires. Full DB-integration coverage of acquire/heartbeat/steal lives in the
manual two-tab smoke test documented in the plan's verification section.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app
    return TestClient(app)


SAMPLE_SID = "11111111-1111-1111-1111-111111111111"


def test_lock_acquire_route_registered():
    """POST /v1/sessions/{id}/lock/acquire reaches the handler (401 not 404)."""
    resp = _client().post(f"/v1/sessions/{SAMPLE_SID}/lock/acquire")
    assert resp.status_code == 401


def test_lock_heartbeat_requires_auth():
    resp = _client().post(f"/v1/sessions/{SAMPLE_SID}/lock/heartbeat")
    assert resp.status_code == 401


def test_lock_release_requires_auth():
    resp = _client().post(f"/v1/sessions/{SAMPLE_SID}/lock/release")
    assert resp.status_code == 401


def test_lock_holder_requires_auth():
    resp = _client().get(f"/v1/sessions/{SAMPLE_SID}/lock/holder")
    assert resp.status_code == 401


def test_lock_force_take_requires_auth():
    resp = _client().post(f"/v1/sessions/{SAMPLE_SID}/lock/force-take")
    assert resp.status_code == 401


def test_lock_ttl_constant_matches_plan():
    """The 90s TTL is documented in the plan; pin it so changes are deliberate."""
    from app.api.locks import LOCK_TTL_SECONDS
    assert LOCK_TTL_SECONDS == 90, "Plan §Phase 1 fixes TTL = 90s (3 missed 30s heartbeats)"


def test_lock_router_holder_returns_none_shape_when_unauth():
    """Even on 401, the envelope shape is intact (smoke against envelope middleware)."""
    resp = _client().get(f"/v1/sessions/{SAMPLE_SID}/lock/holder")
    body = resp.json()
    # Envelope: {success, data, error, meta}
    assert "success" in body and body["success"] is False
    assert "error" in body
