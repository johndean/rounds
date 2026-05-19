"""
/v1/audit — global audit ledger + per-session corrections.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("")
async def list_events(
    db: DbSession, _u: CurrentUser,
    session_id: Optional[UUID] = None,
    actor: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    where, params = [], {"limit": min(limit, 500), "offset": offset}
    if session_id is not None:
        where.append("session_id = :s"); params["s"] = str(session_id)
    if actor is not None:
        where.append("actor_email = :a"); params["a"] = actor.lower()
    if kind is not None:
        where.append("kind = :k"); params["k"] = kind
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = (await db.execute(text(
        f"SELECT id, session_id, actor_email, kind, summary, details, occurred_at "
        f"FROM audit_events {clause} ORDER BY occurred_at DESC LIMIT :limit OFFSET :offset"
    ), params)).mappings().all()
    return [
        {**dict(r), "occurred_at": r["occurred_at"].isoformat()}
        for r in rows
    ]


@router.get("/sessions/{session_id}/corrections")
async def list_corrections(session_id: UUID, db: DbSession, _u: CurrentUser, limit: int = 200) -> list[dict]:
    """Active corrections for the session, returned in the editor-frontend shape.

    Reads from `correction_ledger` (Phase 4) — the authoritative table where
    /find-replace and inline edits write. Filters by the undo pointer so
    redo-tail entries don't surface. Maps the row to the {id,t,type,actor,
    seg,prior,next,note} shape expected by AuditTabInline.vue + DecisionCard.vue.
    """
    sid = str(session_id)
    ptr_row = (await db.execute(text(
        "SELECT current_pointer FROM ledger_pointers WHERE session_id = CAST(:s AS uuid)"
    ), {"s": sid})).mappings().first()
    current_ptr = int(ptr_row["current_pointer"]) if ptr_row else -1

    rows = (await db.execute(text(
        """
        SELECT id, segment_id, applied_by, correction_type, old_text, new_text, applied_at
          FROM correction_ledger
         WHERE session_id = CAST(:s AS uuid)
           AND sequence_number <= :ptr
         ORDER BY applied_at DESC
         LIMIT :limit
        """
    ), {"s": sid, "ptr": current_ptr, "limit": min(limit, 1000)})).mappings().all()

    return [
        {
            "id":    str(r["id"]),
            "t":     r["applied_at"].isoformat() if r["applied_at"] else None,
            "type":  r["correction_type"],
            "actor": r["applied_by"] or "",
            "seg":   str(r["segment_id"]) if r["segment_id"] else "",
            "prior": r["old_text"],
            "next":  r["new_text"],
            "note":  None,
        }
        for r in rows
    ]
