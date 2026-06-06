"""
app/services/segment_merge.py — merge executor + structural inverse.

Phase 3.5/4 (2026-06-06). Plan ref:
docs/plans/2026-06-06-002-phase-3.5-split-merge-executor-v2.md §4.4 + §4.5.

execute_merge collapses two adjacent same-speaker segments into the left
row and DELETEs the right row. word_alignment rows reparent to left
with gemini_idx shifted past left's word count. key_points_annotations
are merged (key_points capped at 5, left explanation wins).
invert_merge restores the right row + word_alignment + kp from a saved
payload.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text


async def execute_merge(db, session_id: str, body, user) -> dict:
    """Merge segment_id (left) with its right neighbor. Returns invert payload."""
    left_id = str(body.segment_id)
    if body.expected_right_segment_id is None:
        raise HTTPException(status_code=400, detail={"code": "MERGE_NO_NEIGHBOR"})
    expected_right_id = str(body.expected_right_segment_id)

    # 1. Lock LEFT row.
    left = (await db.execute(text("""
        SELECT id, session_id, slide_id, speaker_id, seq, start_ms, end_ms,
               text AS seg_text, confidence, flags, is_anchor, anchor_kind,
               metadata, content_hash
          FROM segments
         WHERE id = CAST(:seg AS uuid) AND session_id = CAST(:sid AS uuid)
         FOR UPDATE
    """), {"sid": session_id, "seg": left_id})).mappings().first()
    if not left:
        raise HTTPException(status_code=404, detail={"code": "MERGE_LEFT_NOT_FOUND"})
    if left["is_anchor"]:
        raise HTTPException(status_code=400, detail={"code": "MERGE_ANCHOR_SEGMENT"})

    # 2. Find right neighbor by ordering on (seq, start_ms). After a split,
    #    two segments can share the same `seq` value (mig 022 dropped the
    #    UNIQUE constraint), so we must compare on the (seq, start_ms) tuple
    #    to break ties — Postgres-native row-value comparison handles this.
    right = (await db.execute(text("""
        SELECT id, session_id, slide_id, speaker_id, seq, start_ms, end_ms,
               text AS seg_text, confidence, flags, is_anchor, anchor_kind,
               metadata, content_hash
          FROM segments
         WHERE session_id = CAST(:sid AS uuid)
           AND (seq, start_ms) > (:left_seq, :left_start_ms)
         ORDER BY seq, start_ms
         LIMIT 1
         FOR UPDATE
    """), {
        "sid": session_id,
        "left_seq": int(left["seq"]),
        "left_start_ms": int(left["start_ms"]),
    })).mappings().first()
    if not right:
        raise HTTPException(status_code=400, detail={"code": "MERGE_NO_NEIGHBOR"})
    if str(right["id"]) != expected_right_id:
        raise HTTPException(status_code=409, detail={"code": "MERGE_NEIGHBOR_CHANGED"})
    if str(left["speaker_id"] or "") != str(right["speaker_id"] or ""):
        raise HTTPException(status_code=400, detail={"code": "MERGE_SPEAKER_MISMATCH"})
    if right["is_anchor"]:
        raise HTTPException(status_code=400, detail={"code": "MERGE_ANCHOR_NEIGHBOR"})

    right_id = str(right["id"])

    # 3. Soft warn on slide mismatch (left's slide_id wins).
    if str(left["slide_id"] or "") != str(right["slide_id"] or ""):
        await db.execute(text("""
            INSERT INTO audit_events (session_id, actor_email, kind, summary, details)
            VALUES (CAST(:sid AS uuid), :who, 'merge.slide_mismatch', :sm, CAST(:d AS jsonb))
        """), {
            "sid": session_id,
            "who": getattr(user, "email", None) or "(unknown)",
            "sm": f"Merge across slide boundary: left={left['slide_id']} right={right['slide_id']}",
            "d": json.dumps({
                "left_id": left_id, "right_id": right_id,
                "left_slide_id": str(left["slide_id"]) if left["slide_id"] else None,
                "right_slide_id": str(right["slide_id"]) if right["slide_id"] else None,
            }),
        })

    # 4. Build merged state.
    merged_text = (left["seg_text"] or "").rstrip() + " " + (right["seg_text"] or "").lstrip()
    merged_end_ms = int(right["end_ms"])
    # Flags union: dedupe by string identity (JSONB arrays of strings).
    left_flags = list(left["flags"]) if left["flags"] else []
    right_flags = list(right["flags"]) if right["flags"] else []
    seen: set = set()
    merged_flags: list = []
    for f in left_flags + right_flags:
        key = json.dumps(f, sort_keys=True) if not isinstance(f, str) else f
        if key in seen:
            continue
        seen.add(key)
        merged_flags.append(f)
    # Metadata: left || jsonb_build_object(...) — done in SQL below.

    # Snapshot pre-merge state for the invert payload.
    left_text_before = left["seg_text"]
    left_end_ms_before = int(left["end_ms"])
    left_flags_before = left["flags"]
    left_metadata_before = left["metadata"]

    right_full_row = {
        "id": right_id,
        "session_id": session_id,
        "slide_id": str(right["slide_id"]) if right["slide_id"] else None,
        "speaker_id": str(right["speaker_id"]) if right["speaker_id"] else None,
        "seq": int(right["seq"]),
        "start_ms": int(right["start_ms"]),
        "end_ms": int(right["end_ms"]),
        "text": right["seg_text"],
        "confidence": float(right["confidence"]) if right["confidence"] is not None else None,
        "flags": right["flags"],
        "is_anchor": bool(right["is_anchor"]),
        "anchor_kind": right["anchor_kind"],
        "metadata": right["metadata"],
        "content_hash": right["content_hash"],
    }

    # Snapshot right word_alignment rows for invert.
    right_wa = (await db.execute(text("""
        SELECT gemini_idx, stt_word_id, stt_start_ms, stt_end_ms, match_kind
          FROM word_alignment
         WHERE segment_id = CAST(:seg AS uuid)
         ORDER BY gemini_idx
    """), {"seg": right_id})).mappings().all()
    right_word_alignment = [
        {
            "gemini_idx": int(r["gemini_idx"]),
            "stt_word_id": str(r["stt_word_id"]) if r["stt_word_id"] else None,
            "stt_start_ms": int(r["stt_start_ms"]) if r["stt_start_ms"] is not None else None,
            "stt_end_ms": int(r["stt_end_ms"]) if r["stt_end_ms"] is not None else None,
            "match_kind": r["match_kind"],
        }
        for r in right_wa
    ]

    # Snapshot right kp row for invert.
    right_kp = (await db.execute(text("""
        SELECT id, session_id, segment_id, label, score, metadata, created_at,
               key_points, explanation, available, extraction_confidence
          FROM key_points_annotations
         WHERE segment_id = CAST(:seg AS uuid)
    """), {"seg": right_id})).mappings().first()
    right_kp_row: dict | None = None
    if right_kp:
        right_kp_row = {
            "session_id": str(right_kp["session_id"]),
            "segment_id": str(right_kp["segment_id"]),
            "label": right_kp["label"],
            "score": float(right_kp["score"]) if right_kp["score"] is not None else None,
            "metadata": right_kp["metadata"],
            "key_points": right_kp["key_points"],
            "explanation": right_kp["explanation"],
            "available": bool(right_kp["available"]),
            "extraction_confidence": float(right_kp["extraction_confidence"])
            if right_kp["extraction_confidence"] is not None else 0.0,
        }

    # 5. UPDATE left.
    await db.execute(text("""
        UPDATE segments
           SET text = :t,
               end_ms = :end_ms,
               flags = CAST(:flags AS jsonb),
               metadata = (CAST(:meta AS jsonb)
                   || jsonb_build_object('merged_from', :rid, 'merged_at_ms', :rstart)),
               updated_at = now()
         WHERE id = CAST(:lid AS uuid)
    """), {
        "t": merged_text,
        "end_ms": merged_end_ms,
        "flags": json.dumps(merged_flags),
        "meta": json.dumps(left_metadata_before) if left_metadata_before is not None else "{}",
        "rid": right_id,
        "rstart": int(right["start_ms"]),
        "lid": left_id,
    })

    # 6. Reparent word_alignment: right rows shift past left's word count.
    left_count_row = (await db.execute(text("""
        SELECT COALESCE(MAX(gemini_idx), -1) + 1 AS n
          FROM word_alignment WHERE segment_id = CAST(:seg AS uuid)
    """), {"seg": left_id})).mappings().first()
    left_count = int(left_count_row["n"]) if left_count_row else 0
    await db.execute(text("""
        UPDATE word_alignment
           SET segment_id = CAST(:lid AS uuid),
               gemini_idx = gemini_idx + :shift
         WHERE segment_id = CAST(:rid AS uuid)
    """), {"lid": left_id, "rid": right_id, "shift": left_count})

    # 7. key_points UPSERT.
    left_kp = (await db.execute(text("""
        SELECT key_points, explanation, available, extraction_confidence
          FROM key_points_annotations
         WHERE segment_id = CAST(:seg AS uuid)
    """), {"seg": left_id})).mappings().first()
    if left_kp or right_kp:
        l_pts: list = list(left_kp["key_points"]) if left_kp and left_kp["key_points"] else []
        r_pts: list = list(right_kp["key_points"]) if right_kp and right_kp["key_points"] else []
        # Concat preserving order, cap at 5, dedupe by JSON identity.
        merged_pts: list = []
        seen_pt: set = set()
        for p in l_pts + r_pts:
            key = json.dumps(p, sort_keys=True) if not isinstance(p, str) else p
            if key in seen_pt:
                continue
            seen_pt.add(key)
            merged_pts.append(p)
            if len(merged_pts) >= 5:
                break
        explanation = (left_kp["explanation"] if left_kp else None) or (
            right_kp["explanation"] if right_kp else "")
        available = bool(
            (left_kp["available"] if left_kp else False)
            or (right_kp["available"] if right_kp else False)
        )
        l_conf = float(left_kp["extraction_confidence"]) if left_kp and left_kp["extraction_confidence"] is not None else 0.0
        r_conf = float(right_kp["extraction_confidence"]) if right_kp and right_kp["extraction_confidence"] is not None else 0.0
        ext_conf = max(l_conf, r_conf)
        await db.execute(text("""
            INSERT INTO key_points_annotations (
                id, session_id, segment_id, label, score, metadata, created_at,
                key_points, explanation, available, extraction_confidence
            )
            VALUES (
                gen_random_uuid(), CAST(:sid AS uuid), CAST(:seg AS uuid),
                NULL, 0.5, '{}'::jsonb, now(),
                CAST(:kp AS jsonb), :exp, :avail, :ec
            )
            ON CONFLICT (session_id, segment_id) DO UPDATE
               SET key_points = EXCLUDED.key_points,
                   explanation = EXCLUDED.explanation,
                   available = EXCLUDED.available,
                   extraction_confidence = EXCLUDED.extraction_confidence
        """), {
            "sid": session_id, "seg": left_id,
            "kp": json.dumps(merged_pts), "exp": explanation,
            "avail": available, "ec": ext_conf,
        })
        # Delete right's kp row (if it still exists).
        await db.execute(text("""
            DELETE FROM key_points_annotations WHERE segment_id = CAST(:seg AS uuid)
        """), {"seg": right_id})

    # 8. DELETE right segment (CASCADE handles dependent FK rows).
    await db.execute(text("""
        DELETE FROM segments WHERE id = CAST(:rid AS uuid)
    """), {"rid": right_id})

    invert_payload: dict[str, Any] = {
        "kind": "merge_invert",
        "kept_segment_id": left_id,
        "deleted_segment_id": right_id,
        "left_text_before": left_text_before,
        "left_end_ms_before": left_end_ms_before,
        "left_flags_before": left_flags_before,
        "left_metadata_before": left_metadata_before,
        "left_word_count_before_merge": left_count,
        "right_full_row": right_full_row,
        "right_word_alignment": right_word_alignment,
        "right_kp_row": right_kp_row,
    }

    return {
        "affected_segment_ids": [left_id],
        "deleted_segment_id": right_id,
        "invert_payload": invert_payload,
    }


async def invert_merge(db, payload: dict) -> None:
    """Undo a prior merge: re-insert right + roll back left state."""
    left_id = payload["kept_segment_id"]
    right_id = payload["deleted_segment_id"]
    right_full = payload["right_full_row"]
    right_wa = payload.get("right_word_alignment", []) or []
    right_kp = payload.get("right_kp_row")
    left_count = int(payload.get("left_word_count_before_merge", 0))
    left_text_before = payload["left_text_before"]
    left_end_ms_before = int(payload["left_end_ms_before"])
    left_flags_before = payload.get("left_flags_before")
    left_metadata_before = payload.get("left_metadata_before")

    # 1. Re-insert the deleted right segment row.
    await db.execute(text("""
        INSERT INTO segments (
            id, session_id, slide_id, speaker_id, seq,
            start_ms, end_ms, text, confidence,
            flags, is_anchor, anchor_kind, metadata, content_hash
        ) VALUES (
            CAST(:id AS uuid),
            CAST(:sid AS uuid),
            CAST(:slide_id AS uuid),
            CAST(:speaker_id AS uuid),
            :seq,
            :start_ms, :end_ms, :t, :confidence,
            CAST(:flags AS jsonb),
            :is_anchor, :anchor_kind,
            CAST(:meta AS jsonb), :content_hash
        )
    """), {
        "id": right_full["id"],
        "sid": right_full["session_id"],
        "slide_id": right_full.get("slide_id"),
        "speaker_id": right_full.get("speaker_id"),
        "seq": int(right_full["seq"]),
        "start_ms": int(right_full["start_ms"]),
        "end_ms": int(right_full["end_ms"]),
        "t": right_full["text"],
        "confidence": right_full.get("confidence"),
        "flags": json.dumps(right_full.get("flags") or []),
        "is_anchor": bool(right_full.get("is_anchor", False)),
        "anchor_kind": right_full.get("anchor_kind"),
        "meta": json.dumps(right_full.get("metadata") or {}),
        "content_hash": right_full["content_hash"],
    })

    # 2. Roll back left.
    await db.execute(text("""
        UPDATE segments
           SET text = :t, end_ms = :end_ms,
               flags = CAST(:flags AS jsonb),
               metadata = CAST(:meta AS jsonb),
               updated_at = now()
         WHERE id = CAST(:lid AS uuid)
    """), {
        "t": left_text_before, "end_ms": left_end_ms_before,
        "flags": json.dumps(left_flags_before if left_flags_before is not None else []),
        "meta": json.dumps(left_metadata_before if left_metadata_before is not None else {}),
        "lid": left_id,
    })

    # 3. Move right's word_alignment rows back: those currently on left
    #    with gemini_idx >= left_count are right's, shift down by left_count.
    await db.execute(text("""
        UPDATE word_alignment
           SET segment_id = CAST(:rid AS uuid),
               gemini_idx = gemini_idx - :shift
         WHERE segment_id = CAST(:lid AS uuid)
           AND gemini_idx >= :shift
    """), {"rid": right_id, "lid": left_id, "shift": left_count})

    # 4. If right had a kp row, restore it (delete the merged left kp first
    #    so the UNIQUE(session_id, segment_id) doesn't conflict on left
    #    re-insert below — left's kp is intentionally re-merged at
    #    re-merge time; we drop any merged-state row here and let the
    #    next forward op recompute. Simpler: do nothing to left kp; just
    #    INSERT right's saved row).
    if right_kp:
        await db.execute(text("""
            INSERT INTO key_points_annotations (
                id, session_id, segment_id, label, score, metadata, created_at,
                key_points, explanation, available, extraction_confidence
            )
            VALUES (
                gen_random_uuid(), CAST(:sid AS uuid), CAST(:seg AS uuid),
                :label, :score, CAST(:md AS jsonb), now(),
                CAST(:kp AS jsonb), :exp, :avail, :ec
            )
            ON CONFLICT (session_id, segment_id) DO UPDATE
               SET key_points = EXCLUDED.key_points,
                   explanation = EXCLUDED.explanation,
                   available = EXCLUDED.available,
                   extraction_confidence = EXCLUDED.extraction_confidence
        """), {
            "sid": right_kp["session_id"],
            "seg": right_kp["segment_id"],
            "label": right_kp.get("label"),
            "score": right_kp.get("score") or 0.5,
            "md": json.dumps(right_kp.get("metadata") or {}),
            "kp": json.dumps(right_kp.get("key_points") or []),
            "exp": right_kp.get("explanation") or "",
            "avail": bool(right_kp.get("available", False)),
            "ec": float(right_kp.get("extraction_confidence") or 0.0),
        })

    _ = right_wa  # retained in payload for diagnostics; alignments above
                  # were already reparented via UPDATE not INSERT.
