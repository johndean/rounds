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
    rows = (await db.execute(text(
        "SELECT id, segment_id, actor_email, kind, was, now_, note, occurred_at "
        "FROM corrections WHERE session_id = :s "
        "ORDER BY occurred_at DESC LIMIT :limit"
    ), {"s": str(session_id), "limit": min(limit, 1000)})).mappings().all()
    return [{**dict(r), "occurred_at": r["occurred_at"].isoformat()} for r in rows]
