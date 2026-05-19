"""
/v1/sessions/{session_id}/discrepancies — list LCS-detected diffs between
AI normalized text and raw STT, classified as meaningful vs noise by the
classify task.

Reads from `transcription_discrepancies` (the table lcs_discrepancies_task
writes to and classify_task updates). Earlier the endpoint pointed at the
unused `discrepancies` table and always returned [] — see PR/commit history
for the audit trail.

Shape mirrors MIC `app/api/discrepancies.py:26-93` so the editor can render
the side-by-side AI ↔ STT comparison from the same response contract.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/sessions/{session_id}/discrepancies", tags=["discrepancies"])


class DiscrepancyOut(BaseModel):
    id:               UUID
    segment_id:       Optional[UUID]
    ai_text:          Optional[str]
    stt_text:         Optional[str]
    category:         Optional[str]
    is_meaningful:    Optional[bool]
    classifier_model: Optional[str]
    classified_at:    Optional[str]
    created_at:       Optional[str]


class DiscrepancyListResponse(BaseModel):
    session_id:            UUID
    count:                 int
    classified_count:      int
    classification_status: str  # 'complete' | 'partial' | 'pending'
    discrepancies:         list[DiscrepancyOut]


@router.get("", response_model=DiscrepancyListResponse)
async def list_discrepancies(
    session_id: UUID,
    db: DbSession,
    _u: CurrentUser,
    category: Optional[str] = None,
    meaningful_only: bool = False,
) -> dict:
    """
    Return all per-segment LCS diffs for this session. Optional filters:
      - category: medication | terminology | filler | punctuation | drift | low_confidence | other
      - meaningful_only: true → exclude rows where is_meaningful = false (noise)

    Each row carries the AI fragment (ai_text), the raw STT fragment (stt_text),
    the classifier's category + meaningful flag, and segment_id so the editor
    can anchor the side-by-side render to a specific segment.
    """
    where, params = ["session_id = CAST(:s AS uuid)"], {"s": str(session_id)}
    if category:
        where.append("category = :cat"); params["cat"] = category
    if meaningful_only:
        where.append("is_meaningful = TRUE")

    rows = (await db.execute(text(
        "SELECT id, segment_id, ai_text, stt_text, category, is_meaningful, "
        "       classifier_model, classified_at, created_at "
        "FROM transcription_discrepancies "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY created_at ASC"
    ), params)).mappings().all()

    out_rows = [
        {
            "id":               r["id"],
            "segment_id":       r["segment_id"],
            "ai_text":          r["ai_text"],
            "stt_text":         r["stt_text"],
            "category":         r["category"],
            "is_meaningful":    r["is_meaningful"],
            "classifier_model": r["classifier_model"],
            "classified_at":    r["classified_at"].isoformat() if r["classified_at"] else None,
            "created_at":       r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    total = len(out_rows)
    classified = sum(1 for r in out_rows if r["is_meaningful"] is not None)
    if total == 0:
        status_label = "complete"
    elif classified == total:
        status_label = "complete"
    elif classified > 0:
        status_label = "partial"
    else:
        status_label = "pending"

    return {
        "session_id":            session_id,
        "count":                 total,
        "classified_count":      classified,
        "classification_status": status_label,
        "discrepancies":         out_rows,
    }
