"""
/v1/sessions/{id}/{slides,chat,polls,sources,speakers}

Sub-resources that the frontend views consume. Until ingest produces real
rows these endpoints return empty arrays — every list endpoint is safe to
call against an empty session and produces a clean "no data yet" state on
the UI.
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/sessions/{session_id}", tags=["sessions"])


# ─── slides ────────────────────────────────────────────────────────────
class SlideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    slide_index: int
    title: Optional[str]
    image_uri: Optional[str]
    start_ms: Optional[int]
    end_ms: Optional[int]


@router.get("/slides", response_model=list[SlideOut])
async def list_slides(session_id: UUID, db: DbSession, _user: CurrentUser) -> list[dict]:
    rows = (
        await db.execute(
            text(
                """
                SELECT id, slide_index, title, image_uri, start_ms, end_ms
                FROM slides WHERE session_id = :sid ORDER BY slide_index ASC
                """
            ),
            {"sid": str(session_id)},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


# ─── speakers ──────────────────────────────────────────────────────────
class SpeakerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    short: Optional[str]
    name: Optional[str]
    role: Optional[str]


@router.get("/speakers", response_model=list[SpeakerOut])
async def list_speakers(session_id: UUID, db: DbSession, _user: CurrentUser) -> list[dict]:
    rows = (
        await db.execute(
            text(
                """
                SELECT id, name AS short, name, role
                FROM speakers
                WHERE session_id = :sid
                """
            ),
            {"sid": str(session_id)},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


# ─── sources (uploaded files) ──────────────────────────────────────────
class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    role: str
    filename: str
    gcs_uri: str
    content_type: Optional[str]
    size_bytes: Optional[int]
    duration_sec: Optional[int]


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(session_id: UUID, db: DbSession, _user: CurrentUser) -> list[dict]:
    rows = (
        await db.execute(
            text(
                """
                SELECT id, role, filename, gcs_uri, content_type, size_bytes, duration_sec
                FROM sources WHERE session_id = :sid ORDER BY created_at ASC
                """
            ),
            {"sid": str(session_id)},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


# ─── chat ──────────────────────────────────────────────────────────────
class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    author: str
    body: str
    sent_at_ms: int
    anchor_segment: Optional[UUID]
    placed: bool


@router.get("/chat", response_model=list[ChatMessageOut])
async def list_chat(session_id: UUID, db: DbSession, _user: CurrentUser) -> list[dict]:
    rows = (
        await db.execute(
            text(
                """
                SELECT id, author, body, sent_at_ms, anchor_segment, placed
                FROM chat_messages WHERE session_id = :sid ORDER BY sent_at_ms ASC
                """
            ),
            {"sid": str(session_id)},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


# ─── polls ─────────────────────────────────────────────────────────────
class PollOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    label: str
    seq: int
    votes: int


class PollOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    question: str
    status: str
    opened_at_ms: int
    closed_at_ms: Optional[int]
    total_votes: int
    anchor_segment: Optional[UUID]
    placed: bool
    options: list[PollOptionOut]


@router.get("/polls", response_model=list[PollOut])
async def list_polls(session_id: UUID, db: DbSession, _user: CurrentUser) -> list[dict[str, Any]]:
    polls = (
        await db.execute(
            text(
                """
                SELECT id, question, status, opened_at_ms, closed_at_ms,
                       total_votes, anchor_segment, placed
                FROM polls WHERE session_id = :sid ORDER BY opened_at_ms ASC
                """
            ),
            {"sid": str(session_id)},
        )
    ).mappings().all()
    out: list[dict[str, Any]] = []
    for p in polls:
        opts = (
            await db.execute(
                text(
                    """
                    SELECT id, label, seq, votes
                    FROM poll_options WHERE poll_id = :pid ORDER BY seq ASC
                    """
                ),
                {"pid": str(p["id"])},
            )
        ).mappings().all()
        out.append({**dict(p), "options": [dict(o) for o in opts]})
    return out
