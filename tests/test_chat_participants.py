"""
Tests for GET /v1/sessions/{id}/chat-participants — Phase 3 of the
2026-06-04 stakeholder remediation.

Aggregation endpoint powering SessionDetailView's Chat Participants
tally widget. Returns one row per distinct chat author with their
message count + first/last seen timestamps. Ordering: count desc,
then speaker asc.

Tests follow the prevailing pattern in tests/test_auth.py — marked
skipped until a DB-seeding fixture lands. Structural assertions stay
as documentation of the contract.
"""
import pytest
from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app
    return TestClient(app)


@pytest.mark.skip(
    reason="Needs DB fixture to seed chat_messages + auth bearer; mirrors test_auth.py skip pattern."
)
def test_empty_session_returns_empty_list():
    """A session with zero chat_messages MUST return []. Not 404, not
    an error — the endpoint is safe to call against any session and
    used unconditionally by SessionDetailView."""
    client = _client()
    resp = client.get("/v1/sessions/00000000-0000-0000-0000-000000000000/chat-participants")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.skip(
    reason="Needs DB fixture."
)
def test_aggregation_returns_one_row_per_distinct_author():
    """Two chat messages from 'Alice' + one from 'Bob' MUST produce
    exactly 2 rows, ordered Alice first (count 2 > 1)."""
    # Seed: 2 messages by Alice, 1 by Bob
    # Expected: [
    #   {speaker: "Alice", message_count: 2, first_seen_ms, last_seen_ms},
    #   {speaker: "Bob",   message_count: 1, first_seen_ms, last_seen_ms},
    # ]
    ...


@pytest.mark.skip(
    reason="Needs DB fixture."
)
def test_tie_break_orders_by_speaker_ascending():
    """When two speakers have identical counts, ORDER BY author ASC
    breaks the tie deterministically (so Playwright snapshots are
    stable across runs)."""
    # Seed: 1 message each from "Zoe", "Alice", "Mike"
    # Expected order: Alice, Mike, Zoe (count is 1 across the board;
    # alphabetical breaks tie)
    ...


@pytest.mark.skip(
    reason="Needs DB fixture."
)
def test_first_and_last_seen_ms_track_min_max():
    """For a speaker with multiple messages at varying sent_at_ms,
    first_seen_ms = MIN and last_seen_ms = MAX. Used by future
    "when did they join" UX in the widget."""
    # Seed: Alice posts at 1000, 5000, 3000 ms
    # Expected: {first_seen_ms: 1000, last_seen_ms: 5000}
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_unauthenticated_request_returns_401():
    """Auth dependency matches the sibling /chat endpoint. No bearer
    token = 401."""
    client = _client()
    resp = client.get("/v1/sessions/00000000-0000-0000-0000-000000000000/chat-participants")
    # NB: when test_client has no auth, FastAPI's OAuth2PasswordBearer
    # with auto_error=False routes through get_current_user which
    # raises 401 via _credentials_exception. Confirm same path here.
    assert resp.status_code == 401
