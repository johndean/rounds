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
    f: Optional[str]     = None,    # free-text query     — ?f=… (TBD)
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """
    Lists non-deleted sessions, optionally filtered by SOP stage (via sop_state
    join) or AI processing stage (via sessions.status), or free-text.

    NOTE: Sessions table is empty in v1 (no ingest path yet) — this currently
    returns an empty list. Filtering logic is in place so the frontend's
    pipeline-circle navigation already lands here.
    """
    # SOP stage filter requires sop_state join — wire when Phase 7 / U48 lands.
    # AI stage filter maps to the `status` column (ingesting | ready | failed | archived).
    # For now: just return [] until ingest writes rows.
    return []


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
