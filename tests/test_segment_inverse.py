"""
Phase 3.5/4 (2026-06-06) — structural inverse round-trip tests for
split/merge corrections.

Plan ref:
docs/plans/2026-06-06-002-phase-3.5-split-merge-executor-v2.md §4.5 + §5.3.

These 6 tests pin the byte-identical undo/redo contract: after a forward
split or merge, an undo must restore the segments + word_alignment +
key_points_annotations rows EXACTLY as they were pre-op; a redo must
recreate the post-op state EXACTLY as the first apply produced it.

DB integration: each test opens its own AsyncSession, seeds a tiny
session + segment fixture, exercises the real `apply_correction` /
`undo_correction` / `redo_correction` routes from `app.api.corrections`,
and asserts via `_snapshot_session` — a flat dict capture of every
row in the three relevant tables so a single `==` covers field, type,
order, and FK structure.

Skipped at import-time if Postgres isn't reachable (matches the
test_segment_time_edit.py + test_help_api.py skip posture documented in
tests/conftest.py).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

# Force the split/merge feature flag on BEFORE app.config import. The
# dispatcher reads settings.SPLIT_MERGE_ENABLED at request time, so the
# env override needs to be in place before pydantic-settings constructs
# the Settings object.
os.environ["SPLIT_MERGE_ENABLED"] = "true"


# ─── DB reachability gate ───────────────────────────────────────────────
def _db_reachable() -> bool:
    """Probe the configured Postgres URL once; skip the module if down."""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        from app.config import settings

        async def _probe() -> bool:
            eng = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
            try:
                async with eng.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                return True
            finally:
                await eng.dispose()

        return asyncio.run(_probe())
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="No reachable Postgres at DATABASE_URL — DB-integration round-trip tests skipped.",
)


# ─── Fixtures ────────────────────────────────────────────────────────────
@pytest.fixture
async def db_session():
    """Yield a fresh AsyncSession bound to the app's engine."""
    # Re-import after env-var override so SPLIT_MERGE_ENABLED is picked up.
    from app.config import settings as _settings
    if not _settings.SPLIT_MERGE_ENABLED:
        # pydantic-settings v2 reads env at instance construction; force
        # reload in case the module was imported before our env edit.
        _settings.SPLIT_MERGE_ENABLED = True

    from app.db import SessionLocal

    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture
async def seeded_session(db_session):
    """Insert a minimal session + 1 segment + 4 word_alignment rows + 1 kp
    row, then yield (session_id, segment_id) and tear it all down on exit.

    The segment text is "alpha bravo charlie delta" (4 whitespace tokens)
    so we can split at any after_word_index in [0, 2].
    """
    sid = str(uuid4())
    seg_id = str(uuid4())

    # Session
    await db_session.execute(text("""
        INSERT INTO sessions (id, code, title, status)
        VALUES (CAST(:sid AS uuid), :code, :title, 'ready')
    """), {"sid": sid, "code": f"TEST-{sid[:8]}", "title": "inverse-test"})

    # Segment with content_hash forced (same recipe as mig 020).
    await db_session.execute(text("""
        INSERT INTO segments (
            id, session_id, slide_id, speaker_id, seq,
            start_ms, end_ms, text, confidence,
            flags, is_anchor, anchor_kind, metadata, content_hash
        ) VALUES (
            CAST(:seg AS uuid), CAST(:sid AS uuid), NULL, NULL, 0,
            1000, 5000, :t, 0.9,
            '["medication"]'::jsonb, FALSE, NULL,
            '{"origin": "test"}'::jsonb,
            encode(sha256((:sid || '1000')::bytea), 'hex')
        )
    """), {"seg": seg_id, "sid": sid, "t": "alpha bravo charlie delta"})

    # 4 word_alignment rows aligned 1-to-1 with the tokens.
    for idx, (start, end) in enumerate([(1000, 2000), (2000, 3000), (3000, 4000), (4000, 5000)]):
        await db_session.execute(text("""
            INSERT INTO word_alignment
                (segment_id, gemini_idx, stt_word_id, stt_start_ms, stt_end_ms, match_kind)
            VALUES (CAST(:seg AS uuid), :gi, NULL, :s, :e, 'exact')
        """), {"seg": seg_id, "gi": idx, "s": start, "e": end})

    # key_points_annotations row.
    await db_session.execute(text("""
        INSERT INTO key_points_annotations (
            id, session_id, segment_id, label, score, metadata, created_at,
            key_points, explanation, available, extraction_confidence
        )
        VALUES (
            gen_random_uuid(), CAST(:sid AS uuid), CAST(:seg AS uuid),
            NULL, 0.5, '{}'::jsonb, now(),
            '["the main point"]'::jsonb, 'because reasons', TRUE, 0.85
        )
    """), {"sid": sid, "seg": seg_id})

    # Pointer row.
    await db_session.execute(text("""
        INSERT INTO ledger_pointers (session_id, current_pointer, updated_at)
        VALUES (CAST(:sid AS uuid), -1, now())
    """), {"sid": sid})

    await db_session.commit()

    try:
        yield sid, seg_id
    finally:
        # Cascade on sessions wipes segments, word_alignment, kp rows,
        # correction_ledger, ledger_pointers. Use a fresh tx so a failed
        # test mid-transaction doesn't poison cleanup.
        try:
            await db_session.rollback()
        except Exception:  # noqa: BLE001
            pass
        try:
            await db_session.execute(
                text("DELETE FROM sessions WHERE id = CAST(:sid AS uuid)"),
                {"sid": sid},
            )
            await db_session.commit()
        except Exception:  # noqa: BLE001
            pass


# ─── Helpers ─────────────────────────────────────────────────────────────
async def _snapshot_session(db, session_id: str) -> dict[str, Any]:
    """Capture every row across segments + word_alignment + key_points_annotations
    for the given session, normalized to plain-Python dicts in a stable order.

    Returned dict is suitable for a single `==` comparison: any field that
    drifts between two snapshots — text, end_ms, content_hash, gemini_idx,
    key_points JSON, flags, metadata, slide_id, speaker_id — produces a
    diff. updated_at + created_at are excluded (now()-driven; not part of
    the structural-inverse contract).
    """
    segs_rows = (await db.execute(text("""
        SELECT id, session_id, slide_id, speaker_id, seq,
               start_ms, end_ms, text, confidence,
               flags, is_anchor, anchor_kind, metadata, content_hash
          FROM segments
         WHERE session_id = CAST(:sid AS uuid)
         ORDER BY seq, start_ms, id
    """), {"sid": session_id})).mappings().all()
    segments = [
        {
            "id": str(r["id"]),
            "slide_id": str(r["slide_id"]) if r["slide_id"] else None,
            "speaker_id": str(r["speaker_id"]) if r["speaker_id"] else None,
            "seq": int(r["seq"]),
            "start_ms": int(r["start_ms"]),
            "end_ms": int(r["end_ms"]),
            "text": r["text"],
            "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
            "flags": list(r["flags"]) if r["flags"] is not None else [],
            "is_anchor": bool(r["is_anchor"]),
            "anchor_kind": r["anchor_kind"],
            "metadata": dict(r["metadata"]) if r["metadata"] is not None else {},
            "content_hash": r["content_hash"],
        }
        for r in segs_rows
    ]

    wa_rows = (await db.execute(text("""
        SELECT wa.segment_id, wa.gemini_idx, wa.stt_word_id,
               wa.stt_start_ms, wa.stt_end_ms, wa.match_kind
          FROM word_alignment wa
          JOIN segments s ON s.id = wa.segment_id
         WHERE s.session_id = CAST(:sid AS uuid)
         ORDER BY wa.segment_id, wa.gemini_idx
    """), {"sid": session_id})).mappings().all()
    word_alignment = [
        {
            "segment_id": str(r["segment_id"]),
            "gemini_idx": int(r["gemini_idx"]),
            "stt_word_id": str(r["stt_word_id"]) if r["stt_word_id"] else None,
            "stt_start_ms": int(r["stt_start_ms"]) if r["stt_start_ms"] is not None else None,
            "stt_end_ms": int(r["stt_end_ms"]) if r["stt_end_ms"] is not None else None,
            "match_kind": r["match_kind"],
        }
        for r in wa_rows
    ]

    kp_rows = (await db.execute(text("""
        SELECT segment_id, label, score, metadata,
               key_points, explanation, available, extraction_confidence
          FROM key_points_annotations
         WHERE session_id = CAST(:sid AS uuid)
         ORDER BY segment_id
    """), {"sid": session_id})).mappings().all()
    kp = [
        {
            "segment_id": str(r["segment_id"]) if r["segment_id"] else None,
            "label": r["label"],
            "score": float(r["score"]) if r["score"] is not None else None,
            "metadata": dict(r["metadata"]) if r["metadata"] is not None else {},
            "key_points": list(r["key_points"]) if r["key_points"] is not None else [],
            "explanation": r["explanation"],
            "available": bool(r["available"]),
            "extraction_confidence": float(r["extraction_confidence"])
            if r["extraction_confidence"] is not None else 0.0,
        }
        for r in kp_rows
    ]

    return {"segments": segments, "word_alignment": word_alignment, "kp": kp}


class _StubUser:
    """Stand-in for `CurrentUser` so we can call route functions directly."""
    email = "test@vin.com"


async def _apply_split(db, sid: str, seg_id: str, after_word_index: int) -> dict:
    from app.api.corrections import CorrectionRequest, apply_correction
    body = CorrectionRequest(
        segment_id=UUID(seg_id),
        correction_type="split",
        after_word_index=after_word_index,
        action_id=uuid4(),
    )
    return await apply_correction(UUID(sid), body, db, _StubUser())


async def _apply_merge(db, sid: str, left_id: str, right_id: str) -> dict:
    from app.api.corrections import CorrectionRequest, apply_correction
    body = CorrectionRequest(
        segment_id=UUID(left_id),
        correction_type="merge",
        expected_right_segment_id=UUID(right_id),
        action_id=uuid4(),
    )
    return await apply_correction(UUID(sid), body, db, _StubUser())


async def _apply_text_edit(db, sid: str, seg_id: str, old_text: str, new_text: str) -> dict:
    from app.api.corrections import CorrectionRequest, apply_correction
    body = CorrectionRequest(
        segment_id=UUID(seg_id),
        correction_type="text_edit",
        old_text=old_text,
        new_text=new_text,
        action_id=uuid4(),
    )
    return await apply_correction(UUID(sid), body, db, _StubUser())


async def _undo(db, sid: str) -> dict:
    from app.api.corrections import undo_correction
    return await undo_correction(UUID(sid), db, _StubUser())


async def _redo(db, sid: str) -> dict:
    from app.api.corrections import redo_correction
    return await redo_correction(UUID(sid), db, _StubUser())


# ─── 1. Split → undo → byte-identical ────────────────────────────────────
async def test_split_then_undo_restores_pre_split_state(db_session, seeded_session):
    """Split a 4-word segment, then undo. Every row in segments +
    word_alignment + key_points_annotations must match the pre-split
    snapshot byte-for-byte."""
    sid, seg_id = seeded_session

    pre = await _snapshot_session(db_session, sid)

    await _apply_split(db_session, sid, seg_id, after_word_index=1)
    # Sanity: the split actually produced 2 segments.
    mid = await _snapshot_session(db_session, sid)
    assert len(mid["segments"]) == 2, "split did not produce 2 segments"

    await _undo(db_session)

    post = await _snapshot_session(db_session, sid)
    assert post == pre, (
        f"Undo did not restore pre-split state.\n"
        f"PRE: {pre}\nPOST: {post}"
    )


# ─── 2. Split → undo → redo → matches first split result ────────────────
async def test_split_then_undo_then_redo_matches_first_split(db_session, seeded_session):
    """Forward split, capture mid-state, undo, redo, then assert the redo
    result matches the original split mid-state byte-for-byte."""
    sid, seg_id = seeded_session

    await _apply_split(db_session, sid, seg_id, after_word_index=1)
    after_first_split = await _snapshot_session(db_session, sid)

    await _undo(db_session)
    await _redo(db_session)

    after_redo = await _snapshot_session(db_session, sid)
    assert after_redo == after_first_split, (
        f"Redo state diverged from first split.\n"
        f"FIRST: {after_first_split}\nREDO: {after_redo}"
    )


# ─── 3. Merge → undo → byte-identical ────────────────────────────────────
async def test_merge_then_undo_restores_pre_merge_state(db_session, seeded_session):
    """Set up two adjacent same-speaker segments via a split, capture
    state, merge them back, then undo. The merge-undo must restore the
    right segment + its word_alignment + its kp row exactly."""
    sid, seg_id = seeded_session

    # Stage two adjacent segments by splitting first.
    result = await _apply_split(db_session, sid, seg_id, after_word_index=1)
    left_id, right_id = result["affected_segment_ids"]

    pre_merge = await _snapshot_session(db_session, sid)
    assert len(pre_merge["segments"]) == 2, "pre-merge setup failed"

    await _apply_merge(db_session, sid, left_id, right_id)
    mid = await _snapshot_session(db_session, sid)
    assert len(mid["segments"]) == 1, "merge did not collapse to 1 segment"

    await _undo(db_session)

    post = await _snapshot_session(db_session, sid)
    assert post == pre_merge, (
        f"Undo did not restore pre-merge state.\n"
        f"PRE: {pre_merge}\nPOST: {post}"
    )


# ─── 4. Merge → undo → redo → matches first merge result ────────────────
async def test_merge_then_undo_then_redo_matches_first_merge(db_session, seeded_session):
    """After two segments are merged, undo + redo must reproduce the
    merge mid-state byte-for-byte (text concat, word_alignment shifted,
    right row deleted)."""
    sid, seg_id = seeded_session

    result = await _apply_split(db_session, sid, seg_id, after_word_index=1)
    left_id, right_id = result["affected_segment_ids"]

    await _apply_merge(db_session, sid, left_id, right_id)
    after_first_merge = await _snapshot_session(db_session, sid)

    await _undo(db_session)
    await _redo(db_session)

    after_redo = await _snapshot_session(db_session, sid)
    assert after_redo == after_first_merge, (
        f"Redo state diverged from first merge.\n"
        f"FIRST: {after_first_merge}\nREDO: {after_redo}"
    )


# ─── 5. Split + text_edit interplay ──────────────────────────────────────
async def test_split_then_text_edit_then_undo_undo_restores_original(
    db_session, seeded_session
):
    """Split, then text_edit the left half, then undo (the text_edit),
    then undo (the split). The original pre-split state must be back —
    this exercises the ledger pointer walking text_edit AND structural
    inverses in the right order."""
    sid, seg_id = seeded_session

    pre = await _snapshot_session(db_session, sid)

    result = await _apply_split(db_session, sid, seg_id, after_word_index=1)
    left_id, _right_id = result["affected_segment_ids"]

    # Read the post-split left text so old_text matches what the
    # materializer wrote.
    left_text_row = (await db_session.execute(text("""
        SELECT text FROM segments WHERE id = CAST(:sid AS uuid)
    """), {"sid": left_id})).mappings().one()
    left_text = left_text_row["text"]

    await _apply_text_edit(db_session, sid, left_id, left_text, "edited left")

    # First undo: rolls back the text_edit only. The split is still
    # in effect — should still see 2 segments.
    await _undo(db_session)
    after_first_undo = await _snapshot_session(db_session, sid)
    assert len(after_first_undo["segments"]) == 2, (
        "first undo collapsed the split; should only roll back text_edit"
    )

    # Second undo: rolls back the split. Original state recovered.
    await _undo(db_session)
    post = await _snapshot_session(db_session, sid)
    assert post == pre, (
        f"Two-step undo did not restore the original state.\n"
        f"PRE: {pre}\nPOST: {post}"
    )


# ─── 6. 3 splits → 3 undos in reverse order ──────────────────────────────
async def test_three_splits_three_undos_recovers_at_each_step(db_session, seeded_session):
    """Apply 3 splits in sequence on the segment chain, then undo 3 times
    in reverse order. After each undo, the state must equal the snapshot
    captured BEFORE the corresponding forward split."""
    sid, _seg_id = seeded_session

    # Widen the seed to a 6-token segment so we can split 3 times safely
    # (each split needs ≥1 word on each side; 6 tokens → splits at 0/1/2).
    # We rewrite the seeded segment + alignments in-place; the conftest
    # cleanup still works because it keys on session_id cascade.
    (await db_session.execute(text(
        "DELETE FROM word_alignment WHERE segment_id IN "
        "(SELECT id FROM segments WHERE session_id = CAST(:sid AS uuid))"
    ), {"sid": sid}))
    (await db_session.execute(text(
        "DELETE FROM key_points_annotations WHERE session_id = CAST(:sid AS uuid)"
    ), {"sid": sid}))
    (await db_session.execute(text(
        "DELETE FROM segments WHERE session_id = CAST(:sid AS uuid)"
    ), {"sid": sid}))
    new_seg_id = str(uuid.uuid4())
    await db_session.execute(text("""
        INSERT INTO segments (
            id, session_id, slide_id, speaker_id, seq,
            start_ms, end_ms, text, confidence,
            flags, is_anchor, anchor_kind, metadata, content_hash
        ) VALUES (
            CAST(:seg AS uuid), CAST(:sid AS uuid), NULL, NULL, 0,
            1000, 7000, :t, 0.9,
            '[]'::jsonb, FALSE, NULL, '{}'::jsonb,
            encode(sha256((:sid || '1000')::bytea), 'hex')
        )
    """), {"seg": new_seg_id, "sid": sid, "t": "a b c d e f"})
    for idx, (s, e) in enumerate(
        [(1000, 2000), (2000, 3000), (3000, 4000),
         (4000, 5000), (5000, 6000), (6000, 7000)]
    ):
        await db_session.execute(text("""
            INSERT INTO word_alignment
                (segment_id, gemini_idx, stt_word_id, stt_start_ms, stt_end_ms, match_kind)
            VALUES (CAST(:seg AS uuid), :gi, NULL, :s, :e, 'exact')
        """), {"seg": new_seg_id, "gi": idx, "s": s, "e": e})
    await db_session.commit()

    # Capture snapshots BEFORE each forward split. After all 3 undos we
    # expect snap_0 (the original 1-segment state) to come back; after 2
    # undos we expect snap_1; after 1 undo we expect snap_2.
    snap_before_1 = await _snapshot_session(db_session, sid)

    # Split #1: cut the chain after word 2 → left "a b c" (3 words),
    # right "d e f" (3 words).
    r1 = await _apply_split(db_session, sid, new_seg_id, after_word_index=2)
    left_1, right_1 = r1["affected_segment_ids"]
    snap_before_2 = await _snapshot_session(db_session, sid)

    # Split #2: cut the LEFT half after word 0 → "a" + "b c".
    r2 = await _apply_split(db_session, sid, left_1, after_word_index=0)
    _left_2, _right_2 = r2["affected_segment_ids"]
    snap_before_3 = await _snapshot_session(db_session, sid)

    # Split #3: cut the original RIGHT half after word 1 → "d e" + "f".
    await _apply_split(db_session, sid, right_1, after_word_index=1)

    # Undo #1 → state should match snap_before_3.
    await _undo(db_session)
    after_undo_1 = await _snapshot_session(db_session, sid)
    assert after_undo_1 == snap_before_3, (
        f"After 1st undo, state does not match snap_before_3.\n"
        f"EXPECT: {snap_before_3}\nGOT: {after_undo_1}"
    )

    # Undo #2 → state should match snap_before_2.
    await _undo(db_session)
    after_undo_2 = await _snapshot_session(db_session, sid)
    assert after_undo_2 == snap_before_2, (
        f"After 2nd undo, state does not match snap_before_2.\n"
        f"EXPECT: {snap_before_2}\nGOT: {after_undo_2}"
    )

    # Undo #3 → state should match snap_before_1 (original 1-segment).
    await _undo(db_session)
    after_undo_3 = await _snapshot_session(db_session, sid)
    assert after_undo_3 == snap_before_1, (
        f"After 3rd undo, state does not match snap_before_1.\n"
        f"EXPECT: {snap_before_1}\nGOT: {after_undo_3}"
    )
