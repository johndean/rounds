"""
/v1/sessions/{session_id}/discrepancies — list + resolve discrepancies.
Editor Discrepancies tab (IMPLEMENTATION.md §6).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/sessions/{session_id}/discrepancies", tags=["discrepancies"])


class DiscrepancyOut(BaseModel):
    id: UUID
    segment_id: Optional[UUID]
    slide_id: Optional[UUID]
    kind: str
    severity: str
    ai_text: Optional[str]
    stt_text: Optional[str]
    is_resolved: bool


@router.get("", response_model=list[DiscrepancyOut])
async def list_discrepancies(session_id: UUID, db: DbSession, _u: CurrentUser,
                              kind: Optional[str] = None, severity: Optional[str] = None,
                              open_only: bool = False) -> list[dict]:
    where, params = ["session_id = :s"], {"s": str(session_id)}
    if kind:
        where.append("kind = :k"); params["k"] = kind
    if severity:
        where.append("severity = :sev"); params["sev"] = severity
    if open_only:
        where.append("is_resolved = FALSE")
    rows = (await db.execute(text(
        "SELECT id, segment_id, slide_id, kind, severity, ai_text, stt_text, is_resolved "
        f"FROM discrepancies WHERE {' AND '.join(where)} ORDER BY created_at DESC"
    ), params)).mappings().all()
    return [dict(r) for r in rows]


@router.post("/{discrepancy_id}/resolve", response_model=DiscrepancyOut)
async def resolve(session_id: UUID, discrepancy_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    row = (await db.execute(text(
        "UPDATE discrepancies SET is_resolved = TRUE, resolved_by = :a, resolved_at = now() "
        "WHERE id = :id AND session_id = :s "
        "RETURNING id, segment_id, slide_id, kind, severity, ai_text, stt_text, is_resolved"
    ), {"id": str(discrepancy_id), "s": str(session_id), "a": user.email})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Discrepancy not found")
    await db.execute(text(
        "INSERT INTO audit_events (session_id, actor_email, kind, summary) "
        "VALUES (:s, :a, 'discrepancy.resolve', :sum)"
    ), {"s": str(session_id), "a": user.email, "sum": f"resolved {discrepancy_id}"})
    await db.commit()
    return dict(row)
