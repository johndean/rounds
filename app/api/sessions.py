"""
/v1/sessions — list / get / create / delete sessions.

Supports the frontend's ?stage / ?ai / ?f query params for filtered lists
(IMPLEMENTATION.md §6 + §9 Pipeline circles → /sessions?ai=… or ?stage=…).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


# ─── Pydantic schemas ──────────────────────────────────────────────────
class SessionIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=512)
    presenter: Optional[str] = None
    duration_sec: Optional[int] = None
    attendee_count: Optional[int] = None
    taxonomy: list[str] = Field(default_factory=list)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    title: str
    presenter: Optional[str]
    status: str
    duration_sec: Optional[int]
    word_count: Optional[int]
    segment_count: Optional[int]
    attendee_count: Optional[int]
    taxonomy: list[str]


# ─── Endpoints ─────────────────────────────────────────────────────────
@router.get("", response_model=list[SessionOut])
async def list_sessions(
    db: DbSession,
    _user: CurrentUser,
    stage: Optional[str] = None,    # SOP stage filter — ?stage=medical
    ai: Optional[str]    = None,    # AI pipeline stage   — ?ai=transcribe
    f: Optional[str]     = None,    # free-text query     — ?f=…
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """
    Lists non-deleted sessions, optionally filtered by SOP stage (via sop_state
    join), AI processing stage (via sessions.status), or free-text on code/title.
    """
    from sqlalchemy import text
    where = ["deleted_at IS NULL"]
    params: dict[str, object] = {"limit": limit, "offset": offset}
    if ai:
        where.append("status = :ai")
        params["ai"] = ai
    if f:
        where.append("(LOWER(code) LIKE :f OR LOWER(title) LIKE :f)")
        params["f"] = f"%{f.lower()}%"
    sql = f"""
        SELECT s.id, s.code, s.title, s.presenter, s.status, s.duration_sec,
               s.word_count, s.segment_count, s.attendee_count, s.taxonomy
        FROM sessions s
        {"JOIN sop_state st ON st.session_id = s.id AND st.stage = :stage" if stage else ""}
        WHERE {' AND '.join(where)}
        ORDER BY s.created_at DESC NULLS LAST, s.code DESC
        LIMIT :limit OFFSET :offset
    """
    if stage:
        params["stage"] = stage
    rows = (await db.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(payload: SessionIn, db: DbSession, user: CurrentUser) -> dict:
    """
    Create a placeholder session row. Real ingest path (manifest parse +
    Celery enqueue) lands in Phase 6 / U37-U40.
    """
    # Direct SQL insert until ORM models land in Phase 7.
    from sqlalchemy import text
    row = (
        await db.execute(
            text(
                """
                INSERT INTO sessions (code, title, presenter, duration_sec, attendee_count, taxonomy, status)
                VALUES (:code, :title, :presenter, :duration_sec, :attendee_count, CAST(:taxonomy AS jsonb), 'ingesting')
                RETURNING id, code, title, presenter, status, duration_sec, word_count, segment_count, attendee_count, taxonomy
                """
            ),
            {
                "code": payload.code,
                "title": payload.title,
                "presenter": payload.presenter,
                "duration_sec": payload.duration_sec,
                "attendee_count": payload.attendee_count,
                "taxonomy": '["' + '","'.join(payload.taxonomy) + '"]' if payload.taxonomy else '[]',
            },
        )
    ).mappings().one()
    await db.commit()
    return dict(row)


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: UUID, db: DbSession, _user: CurrentUser) -> dict:
    from sqlalchemy import text
    row = (
        await db.execute(
            text(
                """
                SELECT id, code, title, presenter, status, duration_sec, word_count, segment_count, attendee_count, taxonomy
                FROM sessions
                WHERE id = :id AND deleted_at IS NULL
                """
            ),
            {"id": str(session_id)},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return dict(row)
