"""
Phase 5 — lock discrepancy classification batching behavior.

Covers MIC parity for `classify_discrepancies`:
  • 15-item batches
  • Markdown-fence stripping (Gemini sometimes wraps JSON in ```json ... ```)
  • Per-batch retry on missing ids (Gemini truncation)
  • Partial-success: successful batches preserved even when later batches fail
  • Returns None ONLY when every batch fails (so the task layer can decide
    whether to retry the whole task)
  • Skips items already in `already_classified_ids`

Stubs `call_gemini_text` so no live API key is needed.
"""
from __future__ import annotations

import json

import pytest

from app.engines import llm_client
from app.engines.llm_client import (
    DISCREPANCY_BATCH_SIZE,
    _parse_gemini_json_array,
    classify_discrepancies,
)


# ─── _parse_gemini_json_array ────────────────────────────────────────────────

def test_parse_strips_json_fence():
    raw = '```json\n[{"id":"a","category":"name","is_meaningful":true}]\n```'
    out = _parse_gemini_json_array(raw)
    assert out == [{"id": "a", "category": "name", "is_meaningful": True}]


def test_parse_strips_plain_fence():
    raw = '```\n[{"id":"a","category":"filler","is_meaningful":false}]\n```'
    out = _parse_gemini_json_array(raw)
    assert out == [{"id": "a", "category": "filler", "is_meaningful": False}]


def test_parse_plain_json():
    out = _parse_gemini_json_array('[{"id":"a","category":"other","is_meaningful":true}]')
    assert out and out[0]["id"] == "a"


def test_parse_returns_none_on_non_list():
    assert _parse_gemini_json_array('{"id":"a"}') is None


def test_parse_returns_none_on_invalid_json():
    assert _parse_gemini_json_array("not json") is None


# ─── classify_discrepancies ──────────────────────────────────────────────────

def _make_items(n: int, prefix: str = "id") -> list[dict]:
    return [{"id": f"{prefix}{i}", "ai_text": f"a{i}", "stt_text": f"s{i}"} for i in range(n)]


def _fake_call_returns(items_per_call: list[list[dict]]):
    """Return a fake call_gemini_text that yields the next batched response each call."""
    calls = iter(items_per_call)

    def _fake(_system_prompt: str, _user_payload: str, model_id: str | None = None, **_kw) -> str:  # noqa: ARG001
        return json.dumps(next(calls))

    return _fake


def test_empty_items_returns_empty_list():
    assert classify_discrepancies([]) == []


def test_all_already_classified_returns_empty_list(monkeypatch):
    items = _make_items(5)
    # Should not call Gemini at all
    monkeypatch.setattr(
        llm_client, "call_gemini_text",
        lambda *a, **k: pytest.fail("should not call Gemini"),
    )
    out = classify_discrepancies(items, already_classified_ids={"id0", "id1", "id2", "id3", "id4"})
    assert out == []


def test_two_batches_of_15(monkeypatch):
    items = _make_items(30)
    # Each batch responds with the full verdict set for its 15 items
    batch1_resp = [{"id": f"id{i}", "category": "filler", "is_meaningful": False} for i in range(15)]
    batch2_resp = [{"id": f"id{i}", "category": "name", "is_meaningful": True} for i in range(15, 30)]
    monkeypatch.setattr(
        llm_client, "call_gemini_text", _fake_call_returns([batch1_resp, batch2_resp]),
    )
    out = classify_discrepancies(items)
    assert out is not None
    assert len(out) == 30
    assert {v["id"] for v in out} == {f"id{i}" for i in range(30)}


def test_batch_size_constant_matches_mic():
    assert DISCREPANCY_BATCH_SIZE == 15


def test_partial_success_one_batch_fails(monkeypatch):
    items = _make_items(30)
    batch1_resp = [{"id": f"id{i}", "category": "filler", "is_meaningful": False} for i in range(15)]

    call_count = {"n": 0}

    def _fake(_sys, _payload, model_id=None, **_kw):  # noqa: ARG001
        call_count["n"] += 1
        if call_count["n"] == 1:
            return json.dumps(batch1_resp)
        # Second batch fails — raise LLMError simulating Gemini error
        raise llm_client.LLMError("simulated 503", category="gemini_overloaded")

    monkeypatch.setattr(llm_client, "call_gemini_text", _fake)
    out = classify_discrepancies(items)
    # Partial: first 15 succeeded, second 15 dropped
    assert out is not None
    assert len(out) == 15
    assert {v["id"] for v in out} == {f"id{i}" for i in range(15)}


def test_all_batches_fail_returns_none(monkeypatch):
    items = _make_items(20)

    def _fail(*_a, **_kw):
        raise llm_client.LLMError("simulated 503", category="gemini_overloaded")

    monkeypatch.setattr(llm_client, "call_gemini_text", _fail)
    out = classify_discrepancies(items)
    assert out is None


def test_missing_ids_retry_recovers(monkeypatch):
    """Gemini returns only 13 of 15 items on first pass; engine retries 2 missing."""
    items = _make_items(15)
    # First pass: drop ids 13 and 14
    partial = [{"id": f"id{i}", "category": "filler", "is_meaningful": False} for i in range(13)]
    # Retry pass: returns the 2 missing
    retry = [{"id": f"id{i}", "category": "name", "is_meaningful": True} for i in (13, 14)]

    monkeypatch.setattr(
        llm_client, "call_gemini_text", _fake_call_returns([partial, retry]),
    )
    out = classify_discrepancies(items)
    assert out is not None
    assert {v["id"] for v in out} == {f"id{i}" for i in range(15)}


def test_invalid_category_falls_back_to_other(monkeypatch):
    items = _make_items(1)
    monkeypatch.setattr(
        llm_client, "call_gemini_text",
        _fake_call_returns([[{"id": "id0", "category": "bogus_cat", "is_meaningful": True}]]),
    )
    out = classify_discrepancies(items)
    assert out == [{"id": "id0", "category": "other", "is_meaningful": True}]


def test_non_bool_is_meaningful_dropped(monkeypatch):
    items = _make_items(2)
    monkeypatch.setattr(
        llm_client, "call_gemini_text",
        _fake_call_returns([[
            {"id": "id0", "category": "name", "is_meaningful": "yes"},  # bad — string not bool
            {"id": "id1", "category": "name", "is_meaningful": True},
        ], [
            # retry for id0 — engine retries the missing one
            {"id": "id0", "category": "name", "is_meaningful": True},
        ]]),
    )
    out = classify_discrepancies(items)
    assert out is not None
    assert {v["id"] for v in out} == {"id0", "id1"}


def test_vertex_routes_through_vertex_helper(monkeypatch):
    items = _make_items(2)
    called = {"vertex": False, "gemini": False}

    def _vertex(_sys, _payload, model_id=None, **_kw):  # noqa: ARG001
        called["vertex"] = True
        return json.dumps([
            {"id": "id0", "category": "name", "is_meaningful": True},
            {"id": "id1", "category": "filler", "is_meaningful": False},
        ])

    def _gemini(*_a, **_kw):
        called["gemini"] = True
        raise AssertionError("should not call gemini when use_vertex=True")

    monkeypatch.setattr(llm_client, "call_vertex_ai_text", _vertex)
    monkeypatch.setattr(llm_client, "call_gemini_text", _gemini)

    out = classify_discrepancies(items, use_vertex=True)
    assert out is not None and len(out) == 2
    assert called["vertex"] and not called["gemini"]
