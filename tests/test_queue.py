"""
Tests for Phase 7-broader (2 of 2) — /v1/queue/mine endpoint.

Route-registration + auth tests run in CI. DB integration tests are
marked skip pending the project-wide fixture.
"""
import pytest
from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app
    return TestClient(app)


def test_queue_mine_requires_auth():
    """GET /v1/queue/mine without bearer returns 401 via the
    envelope-wrapped UNAUTHORIZED error. Confirms the auth dependency
    fires before the route body."""
    client = _client()
    resp = client.get("/v1/queue/mine")
    assert resp.status_code == 401


def test_queue_router_registered_at_expected_prefix():
    """Smoke test that the queue router is mounted at /v1/queue (so
    /v1/queue/mine is reachable and 401s appear with the envelope
    wrapper rather than 404)."""
    client = _client()
    # 401 (not 404) proves the route is registered but auth-gated.
    resp = client.get("/v1/queue/mine")
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}: {resp.text[:200]}"


@pytest.mark.skip(reason="Needs DB fixture; see tests/test_auth.py.")
def test_queue_mine_filters_to_current_user_email():
    """Sessions where sop_state.assignees[current_stage] == user.email
    appear in the list; sessions assigned to OTHER users do not."""
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_queue_mine_excludes_complete_stage():
    """Sessions whose current_stage is 'complete' are excluded —
    terminal stage means no work remains."""
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_queue_mine_excludes_soft_deleted():
    """Sessions with deleted_at IS NOT NULL are excluded — operators
    don't want soft-deleted items cluttering their queue."""
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_queue_mine_orders_by_entered_current_at_ascending():
    """Longest-waiting items surface first."""
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_queue_mine_computes_overdue_hours():
    """overdue_hours is computed server-side via the inlined SLA map
    + sop_state.sla_target_hours override. Null when on-time;
    positive float when past SLA."""
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_queue_mine_skips_group_assignments():
    """Sessions assigned to a group: prefix (e.g. group:medical_team)
    are NOT in any individual user's queue — group expansion is
    deferred until a per-group roster lands."""
    ...
