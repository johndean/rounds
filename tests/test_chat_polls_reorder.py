"""
Tests for Phase 6 — chat / polls bulk-reorder endpoints.

Pure Pydantic + route-registration tests run in CI. DB-integration
tests are marked skip pending the project-wide fixture (consistent
with tests/test_chat_participants.py + test_auth.py posture).

Verifies the ReorderRequest validation contract and pins the
behavioral guarantees that landed with migration 052 + the two new
PATCH endpoints in app/api/session_resources.py.
"""
import pytest
from fastapi.testclient import TestClient

from app.api.session_resources import ReorderRequest


def _client() -> TestClient:
    from app.main import app
    return TestClient(app)


class TestReorderRequest:
    """Pure-Pydantic shape validation — no DB."""

    def test_accepts_uuid_array(self):
        # 4 valid UUIDs — typical chat reorder request shape.
        ids = [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333",
            "44444444-4444-4444-4444-444444444444",
        ]
        r = ReorderRequest(ids=ids)  # type: ignore[arg-type]
        assert len(r.ids) == 4

    def test_accepts_single_id(self):
        # A 1-item reorder is allowed (degenerate but not invalid).
        r = ReorderRequest(ids=["11111111-1111-1111-1111-111111111111"])  # type: ignore[arg-type]
        assert len(r.ids) == 1

    def test_rejects_non_uuid_strings(self):
        with pytest.raises(Exception):  # Pydantic ValidationError
            ReorderRequest(ids=["not-a-uuid"])  # type: ignore[arg-type]

    def test_rejects_missing_ids(self):
        with pytest.raises(Exception):
            ReorderRequest()  # type: ignore[call-arg]


class TestReorderRoutes:
    """Route-registration + auth tests. No DB fixture needed for the
    no-auth path (the auth dependency fires before the route body)."""

    def test_chat_order_route_requires_auth(self):
        client = _client()
        resp = client.patch(
            "/v1/sessions/00000000-0000-0000-0000-000000000000/chat/order",
            json={"ids": []},
        )
        assert resp.status_code == 401

    def test_polls_order_route_requires_auth(self):
        client = _client()
        resp = client.patch(
            "/v1/sessions/00000000-0000-0000-0000-000000000000/polls/order",
            json={"ids": []},
        )
        assert resp.status_code == 401


# DB-integration tests — pinned contracts, skipped until fixture lands.
@pytest.mark.skip(reason="Needs DB fixture; see tests/test_auth.py.")
def test_chat_order_rejects_empty_ids():
    """Empty ids array returns 400 EMPTY_REORDER."""
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_chat_order_rejects_unknown_ids():
    """ids that don't belong to this session return 400 UNKNOWN_CHAT_IDS
    with the bad ids in the error body (capped at 5)."""
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_chat_order_renumbers_atomically():
    """All UPDATEs in one transaction; partial failure leaves zero
    rows renumbered."""
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_list_chat_uses_coalesce_order_index_sent_at_ms():
    """After reorder, GET /chat returns rows in the new order.
    Un-reordered rows continue to sort by sent_at_ms (the COALESCE
    fallback)."""
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_reorder_writes_single_audit_row():
    """audit_events gets ONE row with kind='chat.reorder' (or
    'polls.reorder') + count + first_3 ids in details. Not one row
    per renumbered chat message."""
    ...
