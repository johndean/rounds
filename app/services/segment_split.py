"""
app/services/segment_split.py — split executor + structural inverse.

Phase 3.5/4 (2026-06-06). Plan ref:
docs/plans/2026-06-06-002-phase-3.5-split-merge-executor-v2.md §4.3 + §4.5.

execute_split splits one segments row into two adjacent rows at the
word boundary identified by `after_word_index`. word_alignment rows
above the cut are reparented to the new segment with gemini_idx
resequenced 0..N-1. key_points_annotations are cloned to both halves.
invert_split is the round-trip inverse used by undo.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text


async def execute_split(db, session_id: str, body, user) -> dict:
    """Split segment at after_word_index. Returns affected ids + invert payload."""
    seg_id = str(body.segment_id)
    if body.after_word_index is None:
        raise HTTPException(status_code=400, detail={"code": "SPLIT_INVALID_WORD_INDEX"})
    after_word_index = int(body.after_word_index)
    if after_word_index < 0:
        raise HTTPException(status_code=400, detail={"code": "SPLIT_INVALID_WORD_INDEX"})

    # 1. SELECT ... FOR UPDATE — locks the row + re-reads text after any
    #    racing autosave UPDATE has either committed before us or now
    #    sits behind our row lock.
    seg = (await db.execute(text("""
        SELECT id, session_id, slide_id, speaker_id, seq, start_ms, end_ms,
               text AS seg_text, confidence, flags, is_anchor, anchor_kind,
               metadata, content_hash
          FROM segments
         WHERE id = CAST(:seg AS uuid) AND session_id = CAST(:sid AS uuid)
         FOR UPDATE
    """), {"sid": session_id, "seg": seg_id})).mappings().first()
    if not seg:
        raise HTTPException(status_code=404, detail={"code": "SPLIT_SEGMENT_NOT_FOUND"})
    if seg["is_anchor"]:
        raise HTTPException(status_code=400, detail={"code": "SPLIT_ANCHOR_SEGMENT"})

    # 2. Load word_alignment rows for this segment.
    wa_rows = (await db.execute(text("""
        SELECT gemini_idx, stt_word_id, stt_start_ms, stt_end_ms, match_kind
          FROM word_alignment
         WHERE segment_id = CAST(:seg AS uuid)
         ORDER BY gemini_idx
    """), {"seg": seg_id})).mappings().all()
    if not wa_rows:
        raise HTTPException(status_code=422, detail={"code": "SPLIT_NO_WORD_ALIGNMENT"})

    n_words = len(wa_rows)
    if after_word_index >= n_words - 1:
        raise HTTPException(status_code=400, detail={"code": "SPLIT_INVALID_WORD_INDEX"})

    # 3. Compute split_ms.
    left_last = wa_rows[after_word_index]
    right_first = wa_rows[after_word_index + 1]
    split_ms: int
    if right_first["stt_start_ms"] is not None:
        split_ms = int(right_first["stt_start_ms"])
    elif left_last["stt_end_ms"] is not None:
        split_ms = int(left_last["stt_end_ms"]) + 1
    else:
        # Final fallback: proportional inside the segment span.
        span = int(seg["end_ms"]) - int(seg["start_ms"])
        split_ms = int(seg["start_ms"]) + int(span * (after_word_index + 1) / n_words)

    # 4. Tokenize the segment text the same way lcs_discrepancies_task did
    #    (whitespace .split()), then rebuild halves.
    tokens = (seg["seg_text"] or "").split()
    if len(tokens) != n_words:
        # Soft-protection: alignment count doesn't match tokenized text.
        # We still proceed using the smaller of the two so we never index
        # out of range. The frontend / realign endpoint can repair drift.
        n_words = min(len(tokens), n_words)
        if after_word_index >= n_words - 1:
            raise HTTPException(status_code=400, detail={"code": "SPLIT_INVALID_WORD_INDEX"})
    text_a = " ".join(tokens[: after_word_index + 1])
    text_b = " ".join(tokens[after_word_index + 1 :])

    # 5. Snapshot the original state for the invert payload BEFORE mutating.
    original_text_before = seg["seg_text"]
    original_end_ms_before = int(seg["end_ms"])
    original_content_hash_before = seg["content_hash"]

    # 6. UPDATE original segment — only text + end_ms move. content_hash,
    #    seq, slide_id, speaker_id, flags, metadata are unchanged.
    await db.execute(text("""
        UPDATE segments
           SET text = :t, end_ms = :end_ms, updated_at = now()
         WHERE id = CAST(:seg AS uuid)
    """), {"t": text_a, "end_ms": split_ms, "seg": seg_id})

    # 7. INSERT new segment for the right half.
    #
    #    Bug fix (H1, 2026-06-06): mig 022 dropped the UNIQUE(session_id, seq)
    #    constraint so we can technically insert at seq = orig_seq + 1, but
    #    that creates ambiguous ordering against whatever previously held
    #    that seq value. Compounded by C1's neighbor-lookup bug, the merge
    #    path could then pick the wrong neighbor. Shift later segments up
    #    by 1 first — single bulk UPDATE per split, negligible cost.
    #
    #    Bug fix (H2, 2026-06-06): the original content_hash recipe
    #    encode(sha256((session_id || split_ms)::bytea), 'hex') is keyed
    #    only on (session_id, split_ms). If split_ms ever lands on an
    #    existing segment's start_ms in the same session, the UNIQUE
    #    (session_id, content_hash) constraint from mig 020 blocks the
    #    INSERT. Mixing the to-be-generated UUID into the recipe makes
    #    collisions impossible by construction while keeping the recipe
    #    deterministic per-row.
    orig_seq = int(seg["seq"])
    await db.execute(text("""
        UPDATE segments
           SET seq = seq + 1
         WHERE session_id = CAST(:sid AS uuid)
           AND seq > :orig_seq
    """), {"sid": session_id, "orig_seq": orig_seq})

    new_seg_row = (await db.execute(text("""
        WITH new_id AS (SELECT gen_random_uuid() AS id)
        INSERT INTO segments (
            id, session_id, slide_id, speaker_id, seq,
            start_ms, end_ms, text, confidence,
            flags, is_anchor, anchor_kind,
            metadata, content_hash
        )
        SELECT new_id.id,
               CAST(:sid AS uuid),
               CAST(:slide_id AS uuid),
               CAST(:speaker_id AS uuid),
               :seq_b,
               :split_ms,
               :end_ms,
               :text_b,
               :confidence,
               CAST(:flags AS jsonb),
               FALSE,
               NULL,
               (CAST(:meta AS jsonb)
                   || jsonb_build_object('split_from', :orig_id, 'split_at_ms', :split_ms)),
               -- Bug fix 2026-06-06: was `:split_ms::text` / `new_id.id::text` / `(...)::bytea`.
               -- SQLAlchemy's text() bind-param regex requires `:name` NOT be followed by `:`,
               -- so `:split_ms::text` left `:split_ms` literally unsubstituted in the SQL sent
               -- to asyncpg → PostgresSyntaxError. Rewrite with explicit CAST() form so the
               -- only `:` characters are real bind markers.
               encode(sha256(CAST(:sid || CAST(:split_ms AS text) || CAST(new_id.id AS text) AS bytea)), 'hex')
          FROM new_id
        RETURNING id
    """), {
        "sid": session_id,
        "slide_id": str(seg["slide_id"]) if seg["slide_id"] else None,
        "speaker_id": str(seg["speaker_id"]) if seg["speaker_id"] else None,
        "seq_b": orig_seq + 1,
        "split_ms": split_ms,
        "end_ms": original_end_ms_before,
        "text_b": text_b,
        "confidence": seg["confidence"],
        "flags": json.dumps(seg["flags"]) if seg["flags"] is not None else "[]",
        "meta": json.dumps(seg["metadata"]) if seg["metadata"] is not None else "{}",
        "orig_id": seg_id,
    })).mappings().one()
    new_id = str(new_seg_row["id"])

    # 8. Reparent word_alignment for the right half. gemini_idx is shifted
    #    so the new segment starts at 0.
    first_moved_idx = after_word_index + 1
    moved_count_row = (await db.execute(text("""
        UPDATE word_alignment
           SET segment_id = CAST(:new AS uuid),
               gemini_idx = gemini_idx - :shift
         WHERE segment_id = CAST(:orig AS uuid)
           AND gemini_idx > :after
        RETURNING gemini_idx
    """), {
        "new": new_id, "shift": first_moved_idx, "orig": seg_id, "after": after_word_index,
    })).mappings().all()
    moved_count = len(moved_count_row)

    # 9. Clone key_points_annotations row (if any) to new segment.
    kp_existing = (await db.execute(text("""
        SELECT 1 FROM key_points_annotations WHERE segment_id = CAST(:seg AS uuid)
    """), {"seg": seg_id})).first()
    kp_cloned = False
    if kp_existing:
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
        """), {"new": new_id, "orig": seg_id})
        kp_cloned = True

    invert_payload: dict[str, Any] = {
        "kind": "split_invert",
        "original_segment_id": seg_id,
        "new_segment_id": new_id,
        "split_at_word_index": after_word_index,
        "split_at_ms": split_ms,
        "original_text_before": original_text_before,
        "original_end_ms_before": original_end_ms_before,
        "original_content_hash_before": original_content_hash_before,
        "moved_word_alignment_count": moved_count,
        "kp_cloned": kp_cloned,
    }

    return {
        "affected_segment_ids": [seg_id, new_id],
        "invert_payload": invert_payload,
    }


async def invert_split(db, payload: dict) -> None:
    """Undo a prior split: merge new_segment back into original_segment."""
    orig_id = payload["original_segment_id"]
    new_id = payload["new_segment_id"]
    original_text_before = payload["original_text_before"]
    original_end_ms_before = int(payload["original_end_ms_before"])
    moved_count = int(payload.get("moved_word_alignment_count", 0))

    # 1. Restore original segment text + end_ms.
    await db.execute(text("""
        UPDATE segments
           SET text = :t, end_ms = :end_ms, updated_at = now()
         WHERE id = CAST(:seg AS uuid)
    """), {"t": original_text_before, "end_ms": original_end_ms_before, "seg": orig_id})

    # 2. Move word_alignment rows back. The right-half rows currently sit
    #    at gemini_idx 0..moved-1 on new_id; their pre-split positions
    #    were (orig word count) onwards. Compute that count from what
    #    remains on orig.
    left_count_row = (await db.execute(text("""
        SELECT COALESCE(MAX(gemini_idx), -1) + 1 AS n
          FROM word_alignment WHERE segment_id = CAST(:seg AS uuid)
    """), {"seg": orig_id})).mappings().first()
    left_count = int(left_count_row["n"]) if left_count_row else 0
    await db.execute(text("""
        UPDATE word_alignment
           SET segment_id = CAST(:orig AS uuid),
               gemini_idx = gemini_idx + :shift
         WHERE segment_id = CAST(:new AS uuid)
    """), {"orig": orig_id, "new": new_id, "shift": left_count})

    # 3. Delete the cloned key_points_annotations row on new (if any).
    await db.execute(text("""
        DELETE FROM key_points_annotations WHERE segment_id = CAST(:new AS uuid)
    """), {"new": new_id})

    # 4. Delete the new segment itself.
    await db.execute(text("""
        DELETE FROM segments WHERE id = CAST(:new AS uuid)
    """), {"new": new_id})
    # moved_count retained in payload for diagnostics; not used here.
    _ = moved_count
