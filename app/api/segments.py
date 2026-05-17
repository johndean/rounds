"""
/v1/sessions/{session_id}/segments — segment list + inline edits.

Backs the editor's AI / STT / Discrepancies tabs and the inline edit /
reassign / speaker actions (IMPLEMENTATION.md §6 segment cards).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/sessions/{session_id}/segments", tags=["segments"])


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    seq: int
    start_ms: int
    end_ms: int
    text: str
    confidence: Optional[float]
    flags: list[str]
    is_anchor: bool
    anchor_kind: Optional[str]
    slide_id: Optional[UUID]
    speaker_id: Optional[UUID]


class SegmentPatch(BaseModel):
    text: Optional[str] = None
    slide_id: Optional[UUID] = None
    speaker_id: Optional[UUID] = None
    flags: Optional[list[str]] = None


class ReassignPayload(BaseModel):
    slide_id: UUID


def _audit_event(db, session_id: str, actor: str, kind: str, summary: str, details: dict) -> None:
    import json
    db.execute(text(
        "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
        "VALUES (:s, :a, :k, :sum, CAST(:d AS jsonb))"
    ), {"s": session_id, "a": actor, "k": kind, "sum": summary, "d": json.dumps(details)})


@router.get("", response_model=list[SegmentOut])
async def list_segments(session_id: UUID, db: DbSession, _u: CurrentUser) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT id, seq, start_ms, end_ms, text, confidence, flags, is_anchor, anchor_kind, "
        "       slide_id, speaker_id "
        "FROM segments WHERE session_id = :s ORDER BY seq"
    ), {"s": str(session_id)})).mappings().all()
    return [dict(r) for r in rows]


@router.patch("/{segment_id}", response_model=SegmentOut)
async def edit_segment(session_id: UUID, segment_id: UUID, payload: SegmentPatch, db: DbSession, user: CurrentUser) -> dict:
    import json
    prior = (await db.execute(text(
        "SELECT text, flags, slide_id, speaker_id FROM segments "
        "WHERE id = :id AND session_id = :s"
    ), {"id": str(segment_id), "s": str(session_id)})).mappings().first()
    if not prior:
        raise HTTPException(status_code=404, detail="Segment not found")

    sets, params = [], {"id": str(segment_id), "s": str(session_id)}
    if payload.text is not None:
        sets.append("text = :text"); params["text"] = payload.text
    if payload.slide_id is not None:
        sets.append("slide_id = :slide_id"); params["slide_id"] = str(payload.slide_id)
    if payload.speaker_id is not None:
        sets.append("speaker_id = :speaker_id"); params["speaker_id"] = str(payload.speaker_id)
    if payload.flags is not None:
        sets.append("flags = CAST(:flags AS jsonb)"); params["flags"] = json.dumps(payload.flags)
    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets.append("updated_at = now()")

    row = (await db.execute(text(
        f"UPDATE segments SET {', '.join(sets)} "
        "WHERE id = :id AND session_id = :s "
        "RETURNING id, seq, start_ms, end_ms, text, confidence, flags, is_anchor, anchor_kind, slide_id, speaker_id"
    ), params)).mappings().one()

    # Correction ledger + audit event
    await db.execute(text(
        "INSERT INTO corrections (session_id, segment_id, actor_email, kind, was, now_, note) "
        "VALUES (:s, :seg, :a, 'edited', CAST(:was AS jsonb), CAST(:now AS jsonb), :note)"
    ), {
        "s": str(session_id),
        "seg": str(segment_id),
        "a": user.email,
        "was": json.dumps({k: (str(v) if hasattr(v, 'hex') else v) for k, v in dict(prior).items()}),
        "now": json.dumps(payload.model_dump(exclude_none=True, mode="json")),
        "note": None,
    })
    await db.execute(text(
        "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
        "VALUES (:s, :a, 'segment.edit', :sum, CAST(:d AS jsonb))"
    ), {"s": str(session_id), "a": user.email,
        "sum": f"edited segment {segment_id}",
        "d": json.dumps(payload.model_dump(exclude_none=True, mode="json"))})
    await db.commit()
    return dict(row)


@router.post("/{segment_id}/reassign", response_model=SegmentOut)
async def reassign_segment(session_id: UUID, segment_id: UUID, payload: ReassignPayload, db: DbSession, user: CurrentUser) -> dict:
    import json
    prior = (await db.execute(text(
        "SELECT slide_id FROM segments WHERE id = :id AND session_id = :s"
    ), {"id": str(segment_id), "s": str(session_id)})).mappings().first()
    if not prior:
        raise HTTPException(status_code=404, detail="Segment not found")

    row = (await db.execute(text(
        "UPDATE segments SET slide_id = :sl, updated_at = now() "
        "WHERE id = :id AND session_id = :s "
        "RETURNING id, seq, start_ms, end_ms, text, confidence, flags, is_anchor, anchor_kind, slide_id, speaker_id"
    ), {"sl": str(payload.slide_id), "id": str(segment_id), "s": str(session_id)})).mappings().one()

    await db.execute(text(
        "INSERT INTO corrections (session_id, segment_id, actor_email, kind, was, now_) "
        "VALUES (:s, :seg, :a, 'slide_reassigned', CAST(:was AS jsonb), CAST(:now AS jsonb))"
    ), {
        "s": str(session_id), "seg": str(segment_id), "a": user.email,
        "was": json.dumps({"slide_id": str(prior["slide_id"]) if prior["slide_id"] else None}),
        "now": json.dumps({"slide_id": str(payload.slide_id)}),
    })
    await db.execute(text(
        "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
        "VALUES (:s, :a, 'segment.reassign', :sum, CAST(:d AS jsonb))"
    ), {"s": str(session_id), "a": user.email,
        "sum": f"reassigned segment {segment_id} to slide {payload.slide_id}",
        "d": json.dumps({"slide_id": str(payload.slide_id)})})
    await db.commit()
    return dict(row)
