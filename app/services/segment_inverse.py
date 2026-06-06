"""
app/services/segment_inverse.py — undo/redo dispatch for split/merge.

Phase 3.5/4 (2026-06-06). Plan ref:
docs/plans/2026-06-06-002-phase-3.5-split-merge-executor-v2.md §4.5.

Implementation choice: we replay structural ops from the persisted
invert_payload (stored in correction_ledger.new_text as JSON). Forward
re-execution (redo) does NOT call back into execute_split / execute_merge
— that would re-validate against a now-mutated DB (the segment after a
prior undo may already match the forward target) and would also try to
write a fresh ledger row. Instead we use the same payload to drive raw
DB mutations symmetrically:

  - invert_split: undo a split by merging the two halves back.
  - apply_forward_split: redo a split by mutating original + re-inserting
    new segment using saved hash + restoring the alignment shift.
  - invert_merge: undo a merge by re-inserting right + rolling back left.
  - apply_forward_merge: redo a merge by re-applying the same UPDATE +
    DELETE we did the first time.

Both directions read state from the saved invert_payload, so the DB
mutations stay tight and don't depend on body validation that already
happened at first-apply time.
"""
from __future__ import annotations

import json

from sqlalchemy import text

from app.services import segment_merge, segment_split


def _parse_payload(correction_row) -> dict | None:
    """Pull the JSON invert payload off correction_ledger.new_text."""
    raw = correction_row.get("new_text") if isinstance(correction_row, dict) else correction_row["new_text"]
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return None


async def apply_inverse_for_correction(db, correction_row) -> None:
    """Reverse the structural mutation captured by this ledger row."""
    ctype = correction_row["correction_type"]
    if ctype not in ("split", "merge"):
        return
    payload = _parse_payload(correction_row)
    if not payload:
        return
    kind = payload.get("kind")
    if kind == "split_invert":
        await segment_split.invert_split(db, payload)
    elif kind == "merge_invert":
        await segment_merge.invert_merge(db, payload)


async def apply_forward_for_correction(db, correction_row) -> None:
    """Re-apply the structural mutation captured by this ledger row."""
    ctype = correction_row["correction_type"]
    if ctype not in ("split", "merge"):
        return
    payload = _parse_payload(correction_row)
    if not payload:
        return
    kind = payload.get("kind")
    if kind == "split_invert":
        await _redo_split(db, payload)
    elif kind == "merge_invert":
        await _redo_merge(db, payload)


async def _redo_split(db, payload: dict) -> None:
    """Re-apply a split from a saved invert payload (the original split)."""
    orig_id = payload["original_segment_id"]
    new_id = payload["new_segment_id"]
    split_ms = int(payload["split_at_ms"])
    after_word_index = int(payload["split_at_word_index"])
    original_text_before = payload["original_text_before"]
    original_end_ms_before = int(payload["original_end_ms_before"])

    # Recompute text_a / text_b from the saved pre-split text.
    tokens = (original_text_before or "").split()
    text_a = " ".join(tokens[: after_word_index + 1])
    text_b = " ".join(tokens[after_word_index + 1 :])

    # Fetch original row to inherit fields for re-insert of right half.
    seg = (await db.execute(text("""
        SELECT slide_id, speaker_id, seq, confidence, flags, metadata
          FROM segments WHERE id = CAST(:seg AS uuid)
    """), {"seg": orig_id})).mappings().one()

    # Update original to the post-split left half.
    await db.execute(text("""
        UPDATE segments
           SET text = :t, end_ms = :end_ms, updated_at = now()
         WHERE id = CAST(:seg AS uuid)
    """), {"t": text_a, "end_ms": split_ms, "seg": orig_id})

    # Re-insert the right-half segment using the same new_id so any
    # downstream references (alignments etc.) stay coherent.
    # Note (H1+H2, 2026-06-06): symmetry with execute_split's fixes — we
    # shift later segments first (to keep seq unambiguous), and the
    # content_hash recipe mixes in the new segment's UUID so the hash
    # can't collide with any other segment's content_hash for this
    # session.
    await db.execute(text("""
        UPDATE segments
           SET seq = seq + 1
         WHERE session_id = (SELECT session_id FROM segments WHERE id = CAST(:orig AS uuid))
           AND seq > :orig_seq
    """), {"orig": orig_id, "orig_seq": int(seg["seq"])})
    await db.execute(text("""
        INSERT INTO segments (
            id, session_id, slide_id, speaker_id, seq,
            start_ms, end_ms, text, confidence,
            flags, is_anchor, anchor_kind, metadata, content_hash
        )
        SELECT CAST(:new AS uuid), s.session_id, s.slide_id, s.speaker_id,
               :seq_b, CAST(:split_ms AS integer), :end_ms, :text_b, s.confidence,
               s.flags, FALSE, NULL,
               (s.metadata || jsonb_build_object('split_from', CAST(:orig AS text), 'split_at_ms', CAST(:split_ms AS integer))),
               encode(sha256(CAST(CAST(s.session_id AS text) || :split_ms_text || CAST(:new AS text) AS bytea)), 'hex')
          FROM segments s
         WHERE s.id = CAST(:orig AS uuid)
    """), {
        "new": new_id, "seq_b": int(seg["seq"]) + 1,
        "split_ms": split_ms, "split_ms_text": str(split_ms),
        "end_ms": original_end_ms_before,
        "text_b": text_b, "orig": orig_id,
    })

    # Reparent right-half word_alignment rows back over to the new segment.
    # Bug fix (C3, 2026-06-06): the forward path in execute_split shifts by
    # a fixed (after_word_index + 1). We previously recomputed the shift
    # via MAX(gemini_idx) on remaining rows, which drifts if rows were
    # deleted out from under us. The payload already carries
    # split_at_word_index, so we use it directly — symmetric with forward.
    shift = int(payload["split_at_word_index"]) + 1
    await db.execute(text("""
        UPDATE word_alignment
           SET segment_id = CAST(:new AS uuid),
               gemini_idx = gemini_idx - :shift
         WHERE segment_id = CAST(:orig AS uuid)
           AND gemini_idx > :after
    """), {"new": new_id, "shift": shift, "orig": orig_id, "after": after_word_index})

    # Re-clone kp row if it had been cloned originally.
    if payload.get("kp_cloned"):
        await db.execute(text("""
            INSERT INTO key_points_annotations (
                id, session_id, segment_id, label, score, metadata, created_at,
                key_points, explanation, available, extraction_confidence
            )
            SELECT gen_random_uuid(), session_id, CAST(:new AS uuid),
                   label, score, metadata, now(),
                   key_points, explanation, available, extraction_confidence
              FROM key_points_annotations
             WHERE segment_id = CAST(:orig AS uuid)
            ON CONFLICT (session_id, segment_id) DO NOTHING
        """), {"new": new_id, "orig": orig_id})


async def _redo_merge(db, payload: dict) -> None:
    """Re-apply a merge from a saved invert payload (the original merge)."""
    left_id = payload["kept_segment_id"]
    right_id = payload["deleted_segment_id"]
    right_full = payload["right_full_row"]
    left_count = int(payload.get("left_word_count_before_merge", 0))
    left_text_before = payload["left_text_before"]

    # Build merged text deterministically (same recipe as forward).
    merged_text = (left_text_before or "").rstrip() + " " + (right_full.get("text") or "").lstrip()
    merged_end_ms = int(right_full["end_ms"])

    # Re-apply UPDATE left.
    await db.execute(text("""
        UPDATE segments
           SET text = :t, end_ms = :end_ms, updated_at = now()
         WHERE id = CAST(:lid AS uuid)
    """), {"t": merged_text, "end_ms": merged_end_ms, "lid": left_id})

    # Re-reparent word_alignment rows from right to left.
    await db.execute(text("""
        UPDATE word_alignment
           SET segment_id = CAST(:lid AS uuid),
               gemini_idx = gemini_idx + :shift
         WHERE segment_id = CAST(:rid AS uuid)
    """), {"lid": left_id, "rid": right_id, "shift": left_count})

    # Re-delete right kp + right segment.
    await db.execute(text("""
        DELETE FROM key_points_annotations WHERE segment_id = CAST(:rid AS uuid)
    """), {"rid": right_id})
    await db.execute(text("""
        DELETE FROM segments WHERE id = CAST(:rid AS uuid)
    """), {"rid": right_id})
