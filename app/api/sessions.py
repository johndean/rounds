"""
/v1/sessions — list / get / create / delete sessions.

Supports the frontend's ?stage / ?ai / ?f query params for filtered lists
(IMPLEMENTATION.md §6 + §9 Pipeline circles → /sessions?ai=… or ?stage=…).
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


# ─── Pydantic schemas ──────────────────────────────────────────────────
class PipelineConfig(BaseModel):
    """
    Pipeline routing captured at upload. Persisted to `session_templates`.
    The 7 UploadView form fields all live here.
    """
    ai_pipeline: str = Field(default="enhanced")             # direct | enhanced
    ai_mode: str     = Field(default="transcript")           # transcript | summary | key-moments | structured-notes | custom-prompt
    ai_model: str    = Field(default="gemini-2.5-pro")
    prompt_mode: str = Field(default="transcript")
    custom_prompt: Optional[str] = None
    stt_backend: str = Field(default="google_latest_long")
    template_id: str = Field(default="lecture_v1")
    iil_config: dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "tier1": True, "tier2": True, "tier3": True})


class SessionIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=512)
    presenter: Optional[str] = None
    duration_sec: Optional[int] = None
    attendee_count: Optional[int] = None
    taxonomy: list[str] = Field(default_factory=list)
    pipeline_config: Optional[PipelineConfig] = None


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
    Create a session row + the matching `session_templates` row that carries
    the pipeline routing chosen on Upload. The two writes happen in the same
    transaction so `ingest_task` always finds a config row.

    Code collision handling: a prior failed/abandoned session leaves a row
    with the same code. Frontend genCode() now appends a 4-char random
    suffix to make collisions astronomically unlikely — but if one still
    happens (e.g. legacy clients without the suffix), surface it as a clean
    409 CONFLICT envelope rather than letting the IntegrityError bubble up
    as a 500.
    """
    import json

    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.middleware.envelope import ConflictError

    try:
        row = (
            await db.execute(
                text(
                    """
                    INSERT INTO sessions (code, title, presenter, duration_sec, attendee_count, taxonomy, status)
                    VALUES (:code, :title, :presenter, :duration_sec, :attendee_count, CAST(:taxonomy AS jsonb), 'uploading')
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
    except IntegrityError as exc:
        await db.rollback()
        # Detect the specific sessions_code_key UNIQUE constraint violation.
        msg = str(exc.orig).lower() if getattr(exc, "orig", None) else str(exc).lower()
        if "sessions_code_key" in msg or ("code" in msg and "duplicate" in msg):
            raise ConflictError(
                message="A session with that code already exists. Retry — the upload form generates a fresh code on each submit.",
                details={"code": payload.code, "constraint": "sessions_code_key"},
            ) from exc
        raise

    # Pipeline config — fall back to defaults if not supplied (legacy clients).
    cfg = payload.pipeline_config or PipelineConfig()
    await db.execute(
        text(
            """
            INSERT INTO session_templates
                (session_id, ai_pipeline, ai_mode, ai_model, prompt_mode, custom_prompt,
                 stt_backend, template_id, iil_config)
            VALUES
                (:sid, :ai_pipeline, :ai_mode, :ai_model, :prompt_mode, :custom_prompt,
                 :stt_backend, :template_id, CAST(:iil_config AS jsonb))
            """
        ),
        {
            "sid":           str(row["id"]),
            "ai_pipeline":   cfg.ai_pipeline,
            "ai_mode":       cfg.ai_mode,
            "ai_model":      cfg.ai_model,
            "prompt_mode":   cfg.prompt_mode,
            "custom_prompt": cfg.custom_prompt,
            "stt_backend":   cfg.stt_backend,
            "template_id":   cfg.template_id,
            "iil_config":    json.dumps(cfg.iil_config),
        },
    )
    await db.commit()
    return dict(row)


# ─── /v1/sessions/{id}/pipeline-config ────────────────────────────────
class PipelineConfigOut(PipelineConfig):
    auto_detected_template_id: Optional[str] = None
    auto_detected_confidence: Optional[float] = None


@router.get("/{session_id}/audit-log")
async def get_audit_log(session_id: UUID, db: DbSession, _u: CurrentUser) -> list[dict]:
    """Returns the append-only state-transition log written by the state machine."""
    from sqlalchemy import text

    row = (
        await db.execute(
            text("SELECT processing_log FROM session_audit WHERE session_id = :sid"),
            {"sid": str(session_id)},
        )
    ).mappings().first()
    if not row:
        return []
    log = row["processing_log"]
    return log if isinstance(log, list) else []


@router.get("/{session_id}/pipeline-config", response_model=PipelineConfigOut)
async def get_pipeline_config(session_id: UUID, db: DbSession, _u: CurrentUser) -> dict:
    from sqlalchemy import text

    row = (
        await db.execute(
            text(
                """
                SELECT ai_pipeline, ai_mode, ai_model, prompt_mode, custom_prompt,
                       stt_backend, template_id, iil_config,
                       auto_detected_template_id, auto_detected_confidence
                FROM session_templates WHERE session_id = :sid
                """
            ),
            {"sid": str(session_id)},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="No pipeline config for session")
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
