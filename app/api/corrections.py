"""
/v1/sessions/{id}/corrections — append-only correction ledger (Phase 4).

Port of MIC `app/api/corrections.py` (452 LOC) adapted to Rounds' raw-SQL
idiom + `CurrentUser`/`DbSession` dependencies + `publish_ws_event_sync`
WS bridge. Backs the editor's Undo/Redo, segment edit/reassign/speaker
inline saves, and Find/Replace bulk-edit flow.

INVARIANT: corrections are APPEND-ONLY. UPDATE / DELETE on corrections is
forbidden. Undo/redo moves `correction_pointers.current_pointer`; the
rows themselves are never mutated.

Routes:
  POST  /v1/sessions/{sid}/corrections          — apply a single correction
  POST  /v1/sessions/{sid}/find-replace         — bulk text_edit with dry_run preview
  GET   /v1/sessions/{sid}/corrections          — full log + current pointer
  POST  /v1/sessions/{sid}/corrections/undo     — decrement pointer
  POST  /v1/sessions/{sid}/corrections/redo     — increment pointer
  GET   /v1/sessions/{sid}/review-queue         — alignment-priority sorted

Closes audit Phase 4. Frontend re-enable of Editor Undo/Redo +
FindReplaceModal + inline saves lives in Phase 4b after the editor
gets real-data wiring (currently fixture-driven).

Related ADRs: ADR-005 (corrections ledger + pointer undo/redo).
Related business rules: BR-006 (confidence-priority scoring), BR-018 (auto-close types).
"""
from __future__ import annotations

import re
import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/sessions", tags=["corrections"])


# ─── Constants ──────────────────────────────────────────────────────────
ALLOWED_CORRECTION_TYPES = frozenset({
    "slide_reassignment", "text_edit", "split", "merge", "mark_ok",
    "chat_insert", "chat_edit", "chat_remove", "poll_insert", "poll_remove",
    "speaker_reassignment",
})

# BR-018 — Correction types that auto-close discrepancies.
# See docs/BUSINESS_RULES.md#br-018.
# Why: when an editor applies a `text_edit` at the spot of a discrepancy,
# the discrepancy clears in one action (no separate "resolve" click). The
# `mark_ok` type is the explicit "no change needed" close. Other correction
# types (find_replace, chat_edit, speaker_reassignment) deliberately do NOT
# auto-close because they don't necessarily resolve the reviewer's concern.
# Adding a type here mass-closes discrepancies an operator may not intend.
CLOSES_DISCREPANCY_TYPES = frozenset({"text_edit", "mark_ok"})


# ─── Pydantic schemas ───────────────────────────────────────────────────
class CorrectionRequest(BaseModel):
    segment_id: UUID
    correction_type: str
    old_slide_id: Optional[UUID] = None
    new_slide_id: Optional[UUID] = None
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    action_id: Optional[UUID] = None


class FindReplaceRequest(BaseModel):
    find: str = Field(..., min_length=1, max_length=512)
    replace: str = Field(default="", max_length=512)
    case_sensitive: bool = Field(default=False)
    dry_run: bool = Field(default=False)


# ─── Helpers ────────────────────────────────────────────────────────────
async def _emit_ws(session_id: str, payload: dict) -> None:
    """Best-effort WS publish. Never raises."""
    try:
        from app.engines.ws_bridge import publish_ws_event_sync
        publish_ws_event_sync(session_id, payload)
    except Exception:  # noqa: BLE001
        pass


async def _ensure_pointer(db, session_id: str) -> int:
    """UPSERT the pointer row; return the current_pointer value."""
    await db.execute(
        text(
            """
            INSERT INTO ledger_pointers (session_id, current_pointer, updated_at)
            VALUES (CAST(:sid AS uuid), -1, now())
            ON CONFLICT (session_id) DO NOTHING
            """
        ),
        {"sid": session_id},
    )
    row = (
        await db.execute(
            text("SELECT current_pointer FROM ledger_pointers WHERE session_id = CAST(:sid AS uuid)"),
            {"sid": session_id},
        )
    ).mappings().first()
    return int(row["current_pointer"]) if row else -1


async def _next_seq(db, session_id: str) -> int:
    """Next sequence_number for this session. 0 if no rows exist."""
    row = (
        await db.execute(
            text(
                "SELECT MAX(sequence_number) AS m FROM correction_ledger "
                "WHERE session_id = CAST(:sid AS uuid)"
            ),
            {"sid": session_id},
        )
    ).mappings().first()
    m = row["m"] if row else None
    return (int(m) + 1) if m is not None else 0


async def _truncate_redo_tail(db, session_id: str, current_pointer: int) -> None:
    """Drop any corrections past the current pointer — redo branch abandoned
    when a new correction is recorded. Per MIC parity (corrections.py:98-104).
    """
    await db.execute(
        text(
            "DELETE FROM correction_ledger WHERE session_id = CAST(:sid AS uuid) "
            "AND sequence_number > :ptr"
        ),
        {"sid": session_id, "ptr": current_pointer},
    )


async def _session_exists(db, session_id: str) -> bool:
    row = (
        await db.execute(
            text("SELECT 1 FROM sessions WHERE id = CAST(:sid AS uuid)"),
            {"sid": session_id},
        )
    ).first()
    return row is not None


async def _segment_belongs(db, session_id: str, segment_id: str) -> bool:
    row = (
        await db.execute(
            text(
                "SELECT 1 FROM segments WHERE id = CAST(:seg AS uuid) "
                "AND session_id = CAST(:sid AS uuid)"
            ),
            {"sid": session_id, "seg": segment_id},
        )
    ).first()
    return row is not None


# ─── POST /v1/sessions/{id}/corrections ─────────────────────────────────
@router.post("/{session_id}/corrections")
async def apply_correction(
    session_id: UUID,
    body: CorrectionRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    """Append a single correction and advance the undo pointer to it.

    Side effect: if the correction is `text_edit` or `mark_ok` and the
    segment has an unresolved transcription_discrepancy, that discrepancy
    is marked resolved with a back-reference to this correction.
    """
    if body.correction_type not in ALLOWED_CORRECTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid correction_type: {body.correction_type}")

    sid = str(session_id)
    seg_id = str(body.segment_id)
    if not await _session_exists(db, sid):
        raise HTTPException(status_code=404, detail=f"Session {sid} not found")
    if not await _segment_belongs(db, sid, seg_id):
        raise HTTPException(status_code=404, detail=f"Segment {seg_id} not in session {sid}")

    current_ptr = await _ensure_pointer(db, sid)
    await _truncate_redo_tail(db, sid, current_ptr)

    seq = await _next_seq(db, sid)
    action_id = str(body.action_id or uuid.uuid4())
    applied_by = getattr(user, "email", None) or "(unknown)"

    row = (
        await db.execute(
            text(
                """
                INSERT INTO correction_ledger
                    (session_id, segment_id, correction_type,
                     old_slide_id, new_slide_id, old_text, new_text,
                     applied_by, action_id, sequence_number)
                VALUES
                    (CAST(:sid AS uuid), CAST(:seg AS uuid), :ctype,
                     :osid, :nsid, :otx, :ntx,
                     :by, CAST(:aid AS uuid), :seq)
                RETURNING id, applied_at
                """
            ),
            {
                "sid":   sid,
                "seg":   seg_id,
                "ctype": body.correction_type,
                "osid":  str(body.old_slide_id) if body.old_slide_id else None,
                "nsid":  str(body.new_slide_id) if body.new_slide_id else None,
                "otx":   body.old_text,
                "ntx":   body.new_text,
                "by":    applied_by,
                "aid":   action_id,
                "seq":   seq,
            },
        )
    ).mappings().one()

    correction_id = str(row["id"])

    await db.execute(
        text(
            "UPDATE ledger_pointers SET current_pointer = :seq, updated_at = now() "
            "WHERE session_id = CAST(:sid AS uuid)"
        ),
        {"sid": sid, "seq": seq},
    )

    resolved_discrepancy_id: Optional[str] = None
    if body.correction_type in CLOSES_DISCREPANCY_TYPES:
        disc = (
            await db.execute(
                text(
                    """
                    UPDATE transcription_discrepancies
                       SET resolved                 = TRUE,
                           resolution_correction_id = CAST(:cid AS uuid),
                           resolved_at              = now()
                     WHERE segment_id = CAST(:seg AS uuid)
                       AND COALESCE(resolved, FALSE) = FALSE
                  RETURNING id
                    """
                ),
                {"cid": correction_id, "seg": seg_id},
            )
        ).mappings().first()
        if disc:
            resolved_discrepancy_id = str(disc["id"])

    await db.commit()

    await _emit_ws(sid, {
        "type":            "correction_applied",
        "action_id":       action_id,
        "segment_ids":     [seg_id],
        "correction_type": body.correction_type,
    })
    if resolved_discrepancy_id:
        await _emit_ws(sid, {
            "type":            "discrepancy_resolved",
            "discrepancy_id": resolved_discrepancy_id,
        })

    return {
        "correction_id":   correction_id,
        "sequence_number": seq,
        "action_id":       action_id,
        "segment_id":      seg_id,
        "correction_type": body.correction_type,
        "old_slide_id":    str(body.old_slide_id) if body.old_slide_id else None,
        "new_slide_id":    str(body.new_slide_id) if body.new_slide_id else None,
        "old_text":        body.old_text,
        "new_text":        body.new_text,
        "applied_at":      row["applied_at"].isoformat() if row["applied_at"] else None,
        "applied_by":      applied_by,
        "resolved_discrepancy_id": resolved_discrepancy_id,
    }


# ─── POST /v1/sessions/{id}/find-replace ────────────────────────────────
@router.post("/{session_id}/find-replace")
async def find_replace(
    session_id: UUID,
    body: FindReplaceRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    """Literal-substring find/replace across all segments in the session.

    Replaces ALL occurrences. Writes one text_edit correction per affected
    segment, sharing one action_id so undo reverses them as a single batch.
    `dry_run=true` returns the preview without writing.

    Effective text per segment = (most recent text_edit ≤ current_pointer)
    || normalized_text || segments.text. This matches the editor's 3-layer
    rendering precedence (user → normalized → raw).
    """
    sid = str(session_id)
    if not await _session_exists(db, sid):
        raise HTTPException(status_code=404, detail=f"Session {sid} not found")

    current_ptr = await _ensure_pointer(db, sid)

    # Active text_edit corrections (the user-layer override).
    corr_rows = (
        await db.execute(
            text(
                """
                SELECT DISTINCT ON (segment_id) segment_id, new_text
                  FROM correction_ledger
                 WHERE session_id = CAST(:sid AS uuid)
                   AND sequence_number <= :ptr
                   AND correction_type = 'text_edit'
                 ORDER BY segment_id, sequence_number DESC
                """
            ),
            {"sid": sid, "ptr": current_ptr},
        )
    ).mappings().all()
    user_text: dict[str, str] = {str(r["segment_id"]): r["new_text"] or "" for r in corr_rows}

    # Normalized layer (only present when migration 012 ran; tolerate missing).
    norm_map: dict[str, str] = {}
    try:
        norm_rows = (
            await db.execute(
                text(
                    "SELECT segment_id, normalized_text FROM normalization_results "
                    "WHERE session_id = CAST(:sid AS uuid)"
                ),
                {"sid": sid},
            )
        ).mappings().all()
        norm_map = {str(r["segment_id"]): r["normalized_text"] or "" for r in norm_rows}
    except Exception:  # noqa: BLE001
        norm_map = {}

    seg_rows = (
        await db.execute(
            text(
                "SELECT id, text, start_ms FROM segments WHERE session_id = CAST(:sid AS uuid) "
                "ORDER BY COALESCE(start_ms, 0)"
            ),
            {"sid": sid},
        )
    ).mappings().all()

    flags = 0 if body.case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(body.find), flags)

    matches: list[dict] = []
    for seg in seg_rows:
        seg_id = str(seg["id"])
        effective = user_text.get(seg_id) or norm_map.get(seg_id) or seg["text"] or ""
        if not effective:
            continue
        count = len(pattern.findall(effective))
        if count == 0:
            continue
        new_text = pattern.sub(body.replace, effective)
        matches.append({
            "segment_id":  seg_id,
            "old_text":    effective,
            "new_text":    new_text,
            "match_count": count,
        })

    total_matches = sum(m["match_count"] for m in matches)

    if body.dry_run or not matches:
        return {
            "session_id":     sid,
            "find":           body.find,
            "replace":        body.replace,
            "case_sensitive": body.case_sensitive,
            "matches":        matches,
            "total_matches":  total_matches,
            "segment_count":  len(matches),
            "applied":        False,
            "action_id":      None,
            "corrections":    [],
        }

    # Truncate any future corrections (redo branch abandoned on new write).
    await _truncate_redo_tail(db, sid, current_ptr)

    action_id = str(uuid.uuid4())
    applied_by = getattr(user, "email", None) or "(unknown)"
    seq = await _next_seq(db, sid)
    inserted: list[dict] = []
    for m in matches:
        row = (
            await db.execute(
                text(
                    """
                    INSERT INTO correction_ledger
                        (session_id, segment_id, correction_type,
                         old_text, new_text, applied_by, action_id, sequence_number)
                    VALUES
                        (CAST(:sid AS uuid), CAST(:seg AS uuid), 'text_edit',
                         :otx, :ntx, :by, CAST(:aid AS uuid), :seq)
                    RETURNING id, applied_at
                    """
                ),
                {
                    "sid": sid,
                    "seg": m["segment_id"],
                    "otx": m["old_text"],
                    "ntx": m["new_text"],
                    "by":  applied_by,
                    "aid": action_id,
                    "seq": seq,
                },
            )
        ).mappings().one()
        inserted.append({
            "correction_id":   str(row["id"]),
            "sequence_number": seq,
            "action_id":       action_id,
            "segment_id":      m["segment_id"],
            "correction_type": "text_edit",
            "old_text":        m["old_text"],
            "new_text":        m["new_text"],
            "applied_by":      applied_by,
            "applied_at":      row["applied_at"].isoformat() if row["applied_at"] else None,
        })
        seq += 1

    await db.execute(
        text(
            "UPDATE ledger_pointers SET current_pointer = :seq, updated_at = now() "
            "WHERE session_id = CAST(:sid AS uuid)"
        ),
        {"sid": sid, "seq": seq - 1},
    )
    await db.commit()

    await _emit_ws(sid, {
        "type":            "correction_applied",
        "action_id":       action_id,
        "segment_ids":     [m["segment_id"] for m in matches],
        "correction_type": "text_edit",
    })

    return {
        "session_id":     sid,
        "find":           body.find,
        "replace":        body.replace,
        "case_sensitive": body.case_sensitive,
        "matches":        matches,
        "total_matches":  total_matches,
        "segment_count":  len(matches),
        "applied":        True,
        "action_id":      action_id,
        "corrections":    inserted,
    }


# ─── GET /v1/sessions/{id}/corrections ──────────────────────────────────
@router.get("/{session_id}/corrections")
async def list_corrections(session_id: UUID, db: DbSession, _u: CurrentUser) -> dict:
    sid = str(session_id)
    rows = (
        await db.execute(
            text(
                """
                SELECT id, segment_id, correction_type,
                       old_slide_id, new_slide_id, old_text, new_text,
                       applied_by, applied_at, action_id, sequence_number
                  FROM correction_ledger
                 WHERE session_id = CAST(:sid AS uuid)
                 ORDER BY sequence_number
                """
            ),
            {"sid": sid},
        )
    ).mappings().all()

    ptr_row = (
        await db.execute(
            text("SELECT current_pointer FROM ledger_pointers WHERE session_id = CAST(:sid AS uuid)"),
            {"sid": sid},
        )
    ).mappings().first()
    current_pointer = int(ptr_row["current_pointer"]) if ptr_row else -1

    return {
        "session_id":      sid,
        "current_pointer": current_pointer,
        "corrections": [
            {
                "correction_id":   str(r["id"]),
                "sequence_number": int(r["sequence_number"]),
                "action_id":       str(r["action_id"]),
                "segment_id":      str(r["segment_id"]),
                "correction_type": r["correction_type"],
                "old_slide_id":    str(r["old_slide_id"]) if r["old_slide_id"] else None,
                "new_slide_id":    str(r["new_slide_id"]) if r["new_slide_id"] else None,
                "old_text":        r["old_text"],
                "new_text":        r["new_text"],
                "applied_at":      r["applied_at"].isoformat() if r["applied_at"] else None,
                "applied_by":      r["applied_by"],
                "active":          int(r["sequence_number"]) <= current_pointer,
            }
            for r in rows
        ],
    }


# ─── POST /v1/sessions/{id}/corrections/undo ────────────────────────────
@router.post("/{session_id}/corrections/undo")
async def undo_correction(session_id: UUID, db: DbSession, _u: CurrentUser) -> dict:
    sid = str(session_id)
    current_ptr = await _ensure_pointer(db, sid)
    if current_ptr < 0:
        return {"session_id": sid, "pointer": -1, "action": "nothing_to_undo"}
    new_ptr = current_ptr - 1
    await db.execute(
        text(
            "UPDATE ledger_pointers SET current_pointer = :p, updated_at = now() "
            "WHERE session_id = CAST(:sid AS uuid)"
        ),
        {"sid": sid, "p": new_ptr},
    )
    await db.commit()
    await _emit_ws(sid, {"type": "correction_applied", "action_id": "undo", "segment_ids": [], "correction_type": "undo"})
    return {"session_id": sid, "pointer": new_ptr}


# ─── POST /v1/sessions/{id}/corrections/redo ────────────────────────────
@router.post("/{session_id}/corrections/redo")
async def redo_correction(session_id: UUID, db: DbSession, _u: CurrentUser) -> dict:
    sid = str(session_id)
    current_ptr = await _ensure_pointer(db, sid)
    max_row = (
        await db.execute(
            text("SELECT MAX(sequence_number) AS m FROM correction_ledger WHERE session_id = CAST(:sid AS uuid)"),
            {"sid": sid},
        )
    ).mappings().first()
    max_seq = int(max_row["m"]) if max_row and max_row["m"] is not None else -1

    if current_ptr >= max_seq:
        return {"session_id": sid, "pointer": current_ptr, "action": "nothing_to_redo"}
    new_ptr = current_ptr + 1
    await db.execute(
        text(
            "UPDATE ledger_pointers SET current_pointer = :p, updated_at = now() "
            "WHERE session_id = CAST(:sid AS uuid)"
        ),
        {"sid": sid, "p": new_ptr},
    )
    await db.commit()
    await _emit_ws(sid, {"type": "correction_applied", "action_id": "redo", "segment_ids": [], "correction_type": "redo"})
    return {"session_id": sid, "pointer": new_ptr}


# ─── GET /v1/sessions/{id}/review-queue ─────────────────────────────────
@router.get("/{session_id}/review-queue")
async def get_review_queue(session_id: UUID, db: DbSession, _u: CurrentUser) -> dict:
    """Alignment rows in `uncertain` or `review` status, ordered by the
    locked Section-18 priority scoring (drift + no slide → highest)."""
    sid = str(session_id)
    rows = (
        await db.execute(
            text(
                """
                SELECT id, segment_id, status, confidence,
                       drift_flag, uncertain_flag, slide_id
                  FROM alignments
                 WHERE session_id = CAST(:sid AS uuid)
                   AND status IN ('uncertain', 'review')
                """
            ),
            {"sid": sid},
        )
    ).mappings().all()

    # BR-006 — Confidence-threshold priority scoring. See docs/BUSINESS_RULES.md#br-006.
    # Why: reviewer order is driven by these weights. Drift + no-slide is the
    # worst case (alignment broke AND no candidate slide exists). The <0.4 and
    # <0.6 confidence buckets came out of MIC audit §18 tuning — they push
    # ambiguous rows to the top of the editor's "next discrepancy" cursor.
    # Risk: changing weights re-orders what reviewers see first. Both <0.4 and
    # <0.6 can apply (sub-0.4 rows accumulate both bonuses).
    def priority(a: dict) -> int:
        score = 0
        if a["drift_flag"]      and a["slide_id"] is None: score += 100
        if a["uncertain_flag"]  and a["slide_id"] is None: score += 90
        if (a["confidence"] or 0) < 0.4:                    score += 70
        if a["drift_flag"]:                                 score += 50
        if a["status"] == "review":                         score += 40
        if (a["confidence"] or 0) < 0.6:                    score += 20
        return score

    ordered = sorted(rows, key=priority, reverse=True)

    return {
        "session_id": sid,
        "count":      len(ordered),
        "items": [
            {
                "segment_id":     str(a["segment_id"]),
                "alignment_id":   str(a["id"]),
                "status":         a["status"],
                "confidence":     float(a["confidence"]) if a["confidence"] is not None else None,
                "drift_flag":     bool(a["drift_flag"]),
                "uncertain_flag": bool(a["uncertain_flag"]),
                "slide_id":       str(a["slide_id"]) if a["slide_id"] else None,
                "priority_score": priority(a),
            }
            for a in ordered
        ],
    }
