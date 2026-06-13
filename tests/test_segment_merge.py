"""
Phase 3.5/4 — segment_merge.execute_merge unit tests.

Plan ref: docs/plans/2026-06-06-002-phase-3.5-split-merge-executor-v2.md §5.2.
Audit IDs prep-closed: E13, E25, E42 (merge half of split/merge executor).

These are pure-Python tests against the executor with a scripted
mock DB. They exercise the 10 merge-side cases from the v2 plan:

  1. Happy path: 2 adjacent same-speaker rows merge to 1, text concat
     single space, word_alignment shifted by left word count.
  2. Last segment (no right neighbor) -> 400 MERGE_NO_NEIGHBOR.
  3. Cross-speaker -> 400 MERGE_SPEAKER_MISMATCH.
  4. expected_right_segment_id mismatch -> 409 MERGE_NEIGHBOR_CHANGED.
  5. Left is_anchor -> 400 MERGE_ANCHOR_SEGMENT.
  6. Right is_anchor -> 400 MERGE_ANCHOR_NEIGHBOR.
  7. Both sides have key_points -> concat capped at 5, max confidence wins.
  8. Slide mismatch -> 200 + audit_events row written
     (kind='merge.slide_mismatch').
  9. flags JSONB union, dedupe (no duplicates).
 10. metadata gets merged_from + merged_at_ms breadcrumb.

Full DB-integration of execute_merge + ledger append + WS event lives
in the staging smoke documented in the plan's verification checklist.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from fastapi import HTTPException


# ─── Mock DB scaffolding ────────────────────────────────────────────────
class _Result:
    """Minimal stand-in for an async SQLAlchemy Result."""

    def __init__(self, rows: list[dict] | None):
        self._rows = list(rows) if rows else []

    def mappings(self) -> "_Result":
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def one(self):
        return self._rows[0]

    def all(self) -> list[dict]:
        return list(self._rows)


class MockDB:
    """Records every execute() call and returns scripted results in order.

    Pass `results` as a list of either:
      - list[dict] -> wrapped in _Result
      - None -> empty result
      - _Result -> used as-is
      - HTTPException -> raised when that call fires (rare)
    """

    def __init__(self, results: list[Any]):
        self._results = list(results)
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, clause, params: dict | None = None):
        # `clause` is a sqlalchemy.sql.elements.TextClause — stringify it
        # so test assertions can grep for keywords without depending on
        # the exact compilation.
        sql = str(getattr(clause, "text", clause))
        self.calls.append((sql, dict(params or {})))
        if not self._results:
            raise AssertionError(
                f"MockDB ran out of scripted results at call #{len(self.calls)}; "
                f"last SQL was: {sql[:120]}"
            )
        nxt = self._results.pop(0)
        if isinstance(nxt, HTTPException):
            raise nxt
        if isinstance(nxt, _Result):
            return nxt
        return _Result(nxt)

    async def commit(self) -> None:  # pragma: no cover — not used in executor
        pass


class _Body:
    """Stand-in for app.api.corrections.CorrectionRequest with only
    the merge-relevant fields the executor reads."""

    def __init__(self, segment_id: uuid.UUID, expected_right_segment_id: uuid.UUID | None):
        self.segment_id = segment_id
        self.expected_right_segment_id = expected_right_segment_id


class _User:
    def __init__(self, email: str = "tester@vin.com"):
        self.email = email


# Common UUIDs (deterministic for assertion clarity).
LEFT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
RIGHT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
OTHER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SESSION_ID = "ssssssss-ssss-ssss-ssss-ssssssssssss"
SPEAKER_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
SPEAKER_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
SLIDE_X = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SLIDE_Y = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


def _left_row(
    *,
    is_anchor: bool = False,
    speaker_id: uuid.UUID | None = SPEAKER_A,
    slide_id: uuid.UUID | None = SLIDE_X,
    seg_text: str = "Left half  ",
    flags: list | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "id": LEFT_ID,
        "session_id": SESSION_ID,
        "slide_id": slide_id,
        "speaker_id": speaker_id,
        "seq": 1,
        "start_ms": 1000,
        "end_ms": 2000,
        "seg_text": seg_text,
        "confidence": 0.9,
        "flags": flags if flags is not None else [],
        "is_anchor": is_anchor,
        "anchor_kind": None,
        "metadata": metadata if metadata is not None else {},
        "content_hash": "left-hash",
    }


def _right_row(
    *,
    is_anchor: bool = False,
    speaker_id: uuid.UUID | None = SPEAKER_A,
    slide_id: uuid.UUID | None = SLIDE_X,
    seg_id: uuid.UUID = RIGHT_ID,
    seg_text: str = "  right half",
    flags: list | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "id": seg_id,
        "session_id": SESSION_ID,
        "slide_id": slide_id,
        "speaker_id": speaker_id,
        "seq": 2,
        "start_ms": 2000,
        "end_ms": 3000,
        "seg_text": seg_text,
        "confidence": 0.8,
        "flags": flags if flags is not None else [],
        "is_anchor": is_anchor,
        "anchor_kind": None,
        "metadata": metadata if metadata is not None else {},
        "content_hash": "right-hash",
    }


@pytest.fixture(autouse=True)
def _enable_split_merge_flag():
    """Per task requirement: SPLIT_MERGE_ENABLED=True for all merge tests.

    execute_merge itself does not read this flag (the dispatcher in
    corrections.py does), but flipping it on keeps the per-suite
    environment honest if a future test routes through the API.
    """
    from app.config import settings
    prev = settings.SPLIT_MERGE_ENABLED
    settings.SPLIT_MERGE_ENABLED = True
    try:
        yield
    finally:
        settings.SPLIT_MERGE_ENABLED = prev


# ─── 1. Happy path ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_happy_path_merge_two_same_speaker_segments():
    from app.services.segment_merge import execute_merge

    # Scripted execute() responses, in the order the executor fires them:
    db = MockDB([
        [_left_row()],                                   # SELECT left FOR UPDATE
        [_right_row()],                                  # SELECT right neighbor FOR UPDATE
        # (no slide mismatch -> no audit_events INSERT)
        [],                                              # SELECT right word_alignment rows
        [],                                              # SELECT right key_points row -> none
        None,                                            # UPDATE left segments
        [{"n": 2}],                                      # SELECT left word count
        None,                                            # UPDATE word_alignment (reparent)
        [],                                              # SELECT left key_points -> none
        # both kp empty -> no UPSERT/DELETE kp branch fires
        None,                                            # DELETE right segment
    ])
    result = await execute_merge(
        db, SESSION_ID,
        _Body(segment_id=LEFT_ID, expected_right_segment_id=RIGHT_ID),
        _User(),
    )

    # Returned shape.
    assert result["affected_segment_ids"] == [str(LEFT_ID)]
    assert result["deleted_segment_id"] == str(RIGHT_ID)
    payload = result["invert_payload"]
    assert payload["kind"] == "merge_invert"
    assert payload["kept_segment_id"] == str(LEFT_ID)
    assert payload["deleted_segment_id"] == str(RIGHT_ID)

    # Locate the UPDATE-left and the reparent-word_alignment calls.
    update_left = next(
        (sql, p) for sql, p in db.calls
        if "UPDATE segments" in sql and "merged_from" in sql
    )
    sql_u, params_u = update_left
    # Text concat: rstrip + single space + lstrip.
    assert params_u["t"] == "Left half right half"
    assert params_u["end_ms"] == 3000
    assert params_u["lid"] == str(LEFT_ID)
    assert params_u["rid"] == str(RIGHT_ID)

    # word_alignment reparent shifts gemini_idx by left's word count (2).
    wa_update = next(
        (sql, p) for sql, p in db.calls
        if "UPDATE word_alignment" in sql and "gemini_idx + :shift" in sql
    )
    _, params_wa = wa_update
    assert params_wa["shift"] == 2
    assert params_wa["lid"] == str(LEFT_ID)
    assert params_wa["rid"] == str(RIGHT_ID)

    # DELETE on right segment fired.
    assert any(
        "DELETE FROM segments" in sql and p.get("rid") == str(RIGHT_ID)
        for sql, p in db.calls
    )


# ─── 2. Last segment / no right neighbor ────────────────────────────────
@pytest.mark.asyncio
async def test_no_right_neighbor_returns_400():
    from app.services.segment_merge import execute_merge

    db = MockDB([
        [_left_row()],   # SELECT left
        [],              # SELECT right -> empty
    ])
    with pytest.raises(HTTPException) as exc:
        await execute_merge(
            db, SESSION_ID,
            _Body(segment_id=LEFT_ID, expected_right_segment_id=RIGHT_ID),
            _User(),
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == {"code": "MERGE_NO_NEIGHBOR"}


# ─── 3. Cross-speaker reject ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_cross_speaker_returns_400():
    from app.services.segment_merge import execute_merge

    db = MockDB([
        [_left_row(speaker_id=SPEAKER_A)],
        [_right_row(speaker_id=SPEAKER_B)],
    ])
    with pytest.raises(HTTPException) as exc:
        await execute_merge(
            db, SESSION_ID,
            _Body(segment_id=LEFT_ID, expected_right_segment_id=RIGHT_ID),
            _User(),
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == {"code": "MERGE_SPEAKER_MISMATCH"}


# ─── 4. expected_right_segment_id mismatch ──────────────────────────────
@pytest.mark.asyncio
async def test_neighbor_changed_returns_409():
    from app.services.segment_merge import execute_merge

    db = MockDB([
        [_left_row()],
        # Actual right neighbor in DB is OTHER_ID, but caller passed RIGHT_ID.
        [_right_row(seg_id=OTHER_ID)],
    ])
    with pytest.raises(HTTPException) as exc:
        await execute_merge(
            db, SESSION_ID,
            _Body(segment_id=LEFT_ID, expected_right_segment_id=RIGHT_ID),
            _User(),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail == {"code": "MERGE_NEIGHBOR_CHANGED"}


# ─── 5. Left is_anchor reject ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_left_anchor_returns_400():
    from app.services.segment_merge import execute_merge

    db = MockDB([
        [_left_row(is_anchor=True)],
        # No further queries — executor short-circuits before fetching right.
    ])
    with pytest.raises(HTTPException) as exc:
        await execute_merge(
            db, SESSION_ID,
            _Body(segment_id=LEFT_ID, expected_right_segment_id=RIGHT_ID),
            _User(),
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == {"code": "MERGE_ANCHOR_SEGMENT"}


# ─── 6. Right is_anchor reject ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_right_anchor_returns_400():
    from app.services.segment_merge import execute_merge

    db = MockDB([
        [_left_row()],
        [_right_row(is_anchor=True)],
    ])
    with pytest.raises(HTTPException) as exc:
        await execute_merge(
            db, SESSION_ID,
            _Body(segment_id=LEFT_ID, expected_right_segment_id=RIGHT_ID),
            _User(),
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == {"code": "MERGE_ANCHOR_NEIGHBOR"}


# ─── 7. Both sides have key_points -> concat capped at 5 ────────────────
@pytest.mark.asyncio
async def test_both_key_points_concat_capped_at_5_and_max_confidence():
    from app.services.segment_merge import execute_merge

    left_kp_row = {
        "key_points": ["a", "b", "c"],
        "explanation": "from left",
        "available": True,
        "extraction_confidence": 0.6,
    }
    right_kp_row = {
        "id": uuid.uuid4(),
        "session_id": SESSION_ID,
        "segment_id": RIGHT_ID,
        "label": None,
        "score": 0.5,
        "metadata": {},
        "created_at": None,
        "key_points": ["d", "e", "f", "g"],
        "explanation": "from right",
        "available": False,
        "extraction_confidence": 0.92,
    }
    db = MockDB([
        [_left_row()],                  # SELECT left
        [_right_row()],                 # SELECT right neighbor
        [],                             # right word_alignment rows
        [right_kp_row],                 # right key_points snapshot
        None,                           # UPDATE left segments
        [{"n": 2}],                     # left word count
        None,                           # UPDATE word_alignment
        [left_kp_row],                  # SELECT left key_points
        None,                           # INSERT/UPSERT key_points_annotations
        None,                           # DELETE right key_points
        None,                           # DELETE right segment
    ])
    result = await execute_merge(
        db, SESSION_ID,
        _Body(segment_id=LEFT_ID, expected_right_segment_id=RIGHT_ID),
        _User(),
    )
    assert result["affected_segment_ids"] == [str(LEFT_ID)]

    # Locate the kp UPSERT call.
    kp_upsert = next(
        (sql, p) for sql, p in db.calls
        if "INSERT INTO key_points_annotations" in sql and "ON CONFLICT" in sql
    )
    _, params_kp = kp_upsert
    merged_pts = json.loads(params_kp["kp"])
    # Concat preserves order, dedupes by identity, caps at 5.
    assert merged_pts == ["a", "b", "c", "d", "e"]
    assert len(merged_pts) == 5
    # Max confidence wins (0.92 > 0.6).
    assert params_kp["ec"] == pytest.approx(0.92)
    # Left explanation wins; right's is dropped.
    assert params_kp["exp"] == "from left"
    # available = OR of both sides.
    assert params_kp["avail"] is True


# ─── 8. Slide mismatch -> audit_events row written ──────────────────────
@pytest.mark.asyncio
async def test_slide_mismatch_writes_audit_event_but_succeeds():
    from app.services.segment_merge import execute_merge

    db = MockDB([
        [_left_row(slide_id=SLIDE_X)],
        [_right_row(slide_id=SLIDE_Y)],
        None,                           # INSERT audit_events
        [],                             # right word_alignment
        [],                             # right key_points -> none
        None,                           # UPDATE left segments
        [{"n": 2}],                     # left word count
        None,                           # UPDATE word_alignment
        [],                             # left key_points -> none
        None,                           # DELETE right segment
    ])
    result = await execute_merge(
        db, SESSION_ID,
        _Body(segment_id=LEFT_ID, expected_right_segment_id=RIGHT_ID),
        _User(email="auditor@vin.com"),
    )
    # Merge still returns normally.
    assert result["affected_segment_ids"] == [str(LEFT_ID)]
    assert result["deleted_segment_id"] == str(RIGHT_ID)

    # audit_events insert with kind='merge.slide_mismatch' fired.
    audit_call = next(
        (sql, p) for sql, p in db.calls
        if "INSERT INTO audit_events" in sql
    )
    sql_a, params_a = audit_call
    assert "merge.slide_mismatch" in sql_a
    assert params_a["who"] == "auditor@vin.com"
    # Details JSON carries both slide ids.
    details = json.loads(params_a["d"])
    assert details["left_id"] == str(LEFT_ID)
    assert details["right_id"] == str(RIGHT_ID)
    assert details["left_slide_id"] == str(SLIDE_X)
    assert details["right_slide_id"] == str(SLIDE_Y)


# ─── 9. flags JSONB union (no duplicates) ───────────────────────────────
@pytest.mark.asyncio
async def test_flags_jsonb_union_dedupes():
    from app.services.segment_merge import execute_merge

    db = MockDB([
        [_left_row(flags=["needs_review", "low_conf"])],
        [_right_row(flags=["low_conf", "speaker_uncertain"])],
        [],                             # right word_alignment
        [],                             # right key_points
        None,                           # UPDATE left segments
        [{"n": 2}],                     # left word count
        None,                           # UPDATE word_alignment
        [],                             # left key_points
        None,                           # DELETE right segment
    ])
    await execute_merge(
        db, SESSION_ID,
        _Body(segment_id=LEFT_ID, expected_right_segment_id=RIGHT_ID),
        _User(),
    )

    update_left = next(
        (sql, p) for sql, p in db.calls
        if "UPDATE segments" in sql and "merged_from" in sql
    )
    _, params_u = update_left
    merged_flags = json.loads(params_u["flags"])
    # Order preserved (left first, new right entries appended), no duplicates.
    assert merged_flags == ["needs_review", "low_conf", "speaker_uncertain"]
    # Sanity: 'low_conf' appears exactly once.
    assert merged_flags.count("low_conf") == 1


# ─── 10. metadata breadcrumb (merged_from + merged_at_ms) ───────────────
@pytest.mark.asyncio
async def test_metadata_breadcrumb_merged_from_and_merged_at_ms():
    from app.services.segment_merge import execute_merge

    db = MockDB([
        [_left_row(metadata={"origin": "stt", "edited_count": 1})],
        [_right_row()],                 # default right.start_ms = 2000
        [],                             # right word_alignment
        [],                             # right key_points
        None,                           # UPDATE left segments
        [{"n": 2}],                     # left word count
        None,                           # UPDATE word_alignment
        [],                             # left key_points
        None,                           # DELETE right segment
    ])
    await execute_merge(
        db, SESSION_ID,
        _Body(segment_id=LEFT_ID, expected_right_segment_id=RIGHT_ID),
        _User(),
    )

    update_left = next(
        (sql, p) for sql, p in db.calls
        if "UPDATE segments" in sql and "merged_from" in sql
    )
    sql_u, params_u = update_left
    # The breadcrumb keys appear in the SQL (composed via jsonb_build_object).
    # Binds may be wrapped in CAST(...) for asyncpg type inference, so assert on
    # the keys + that the binds are referenced, not the exact pre-CAST text.
    assert "jsonb_build_object(" in sql_u
    assert "'merged_from'" in sql_u and "'merged_at_ms'" in sql_u
    assert ":rid" in sql_u and ":rstart" in sql_u
    assert params_u["rid"] == str(RIGHT_ID)
    assert params_u["rstart"] == 2000
    # Pre-existing left.metadata is preserved alongside (the SQL uses `||`).
    preserved = json.loads(params_u["meta"])
    assert preserved == {"origin": "stt", "edited_count": 1}
