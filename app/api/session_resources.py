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

from fastapi import APIRouter, Body
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


class ReExtractRequest(BaseModel):
    page_indices: list[int]   # 1-based page numbers from the editor


@router.post("/slides/re-extract")
async def re_extract_slides(
    session_id: UUID,
    _user: CurrentUser,
    payload: ReExtractRequest = Body(...),
) -> dict:
    """Phase 7h — re-extract specific PDF pages on operator request."""
    try:
        from app.tasks.slide_extract import slide_extract_selected_pages_task

        slide_extract_selected_pages_task.apply_async(
            args=[str(session_id), payload.page_indices],
            queue="celery",
        )
        return {"enqueued": True, "page_indices": payload.page_indices}
    except Exception as exc:  # noqa: BLE001
        return {"enqueued": False, "error": f"{exc.__class__.__name__}: {exc}"}


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


# ─── captions burn-in (Phase 10.1) ─────────────────────────────────────
class BurnCaptionsRequest(BaseModel):
    """Optional ASS-style overrides forwarded to burn_captions_task.
    See app/tasks/burn_captions.py:style_config_to_ass for keys."""
    style_config: Optional[dict[str, Any]] = None


class CaptionedVideoArtifact(BaseModel):
    artifact_id: str
    gcs_uri: str
    download_url: Optional[str] = None
    bytes: Optional[int] = None
    version: int
    is_current: bool
    generated_at: Optional[str] = None
    style_config: Optional[dict[str, Any]] = None


@router.post("/captions/burn")
async def burn_captions(
    session_id: UUID, body: BurnCaptionsRequest, db: DbSession, _user: CurrentUser,
) -> dict:
    """Phase 10.1: kick off `burn_captions_task` which produces a captioned
    MP4 in GCS. Frontend listens for `captioned_video_ready` WS event with
    the signed download URL (24h expiry). Non-critical: failure does NOT
    mark the session as failed — the original transcript remains the
    canonical output.
    """
    from fastapi import HTTPException
    # Verify a video source exists before enqueueing
    row = (
        await db.execute(
            text(
                "SELECT COUNT(*) AS n FROM sources WHERE session_id = CAST(:sid AS uuid) "
                "AND role = 'video'"
            ),
            {"sid": str(session_id)},
        )
    ).mappings().first()
    if not row or int(row["n"]) == 0:
        raise HTTPException(
            status_code=400,
            detail="No video source available — captions can only be burned into video sessions.",
        )

    try:
        from app.tasks.burn_captions import burn_captions_task
        burn_captions_task.apply_async(
            kwargs={"session_id": str(session_id), "style_config": body.style_config or {}},
            queue="celery",
        )
        return {"enqueued": True, "session_id": str(session_id)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to enqueue burn task: {exc.__class__.__name__}: {exc}")


@router.get("/captioned-video", response_model=Optional[CaptionedVideoArtifact])
async def get_captioned_video(
    session_id: UUID, db: DbSession, _user: CurrentUser,
) -> Optional[dict]:
    """Phase 10.1: returns the current captioned-video artifact for this
    session (or null if none has been burned yet). Generates a fresh 1-hour
    signed URL on every call so links don't expire silently between page
    loads.
    """
    row = (
        await db.execute(
            text(
                """
                SELECT id, gcs_uri, bytes, version, is_current, style_config,
                       generated_at
                  FROM artifacts
                 WHERE session_id = CAST(:sid AS uuid)
                   AND kind = 'captioned_video'
                   AND is_current = TRUE
                 ORDER BY generated_at DESC
                 LIMIT 1
                """
            ),
            {"sid": str(session_id)},
        )
    ).mappings().first()
    if not row:
        return None

    # Generate a short-lived signed URL (1h) on the fly so the link is
    # always fresh per page load.
    signed_url: Optional[str] = None
    try:
        from app.tasks.burn_captions import _generate_signed_url
        signed_url = _generate_signed_url(row["gcs_uri"], hours=1)
    except Exception:  # noqa: BLE001
        pass

    return {
        "artifact_id":  str(row["id"]),
        "gcs_uri":      row["gcs_uri"],
        "download_url": signed_url,
        "bytes":        int(row["bytes"]) if row["bytes"] is not None else None,
        "version":      int(row["version"]),
        "is_current":   bool(row["is_current"]),
        "generated_at": row["generated_at"].isoformat() if row["generated_at"] else None,
        "style_config": row["style_config"],
    }


# ─── speakers ──────────────────────────────────────────────────────────
class SpeakerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    short: Optional[str]
    name: Optional[str]
    role: Optional[str]
    avatar_color: Optional[str] = None


class SpeakerCreate(BaseModel):
    name: str
    role: Optional[str] = None
    avatar_color: Optional[str] = None


class SpeakerPatch(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    avatar_color: Optional[str] = None


class SpeakerReassignRequest(BaseModel):
    speaker_id: UUID


@router.get("/speakers", response_model=list[SpeakerOut])
async def list_speakers(session_id: UUID, db: DbSession, _user: CurrentUser) -> list[dict]:
    rows = (
        await db.execute(
            text(
                """
                SELECT id, name AS short, name, role, avatar_color
                FROM speakers
                WHERE session_id = :sid
                ORDER BY created_at ASC
                """
            ),
            {"sid": str(session_id)},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


@router.post("/speakers", response_model=SpeakerOut, status_code=201)
async def add_speaker(
    session_id: UUID, body: SpeakerCreate, db: DbSession, _user: CurrentUser,
) -> dict:
    """Phase 9: add a speaker to a session. Operators use this to fix
    speaker-roster mistakes post-ingest (e.g. when manifest was missing or
    AI MODE direct only picked "Presenter")."""
    row = (
        await db.execute(
            text(
                """
                INSERT INTO speakers (session_id, name, role, avatar_color)
                VALUES (CAST(:sid AS uuid), :n, :r, :ac)
                RETURNING id, name AS short, name, role, avatar_color
                """
            ),
            {
                "sid": str(session_id),
                "n":   body.name,
                "r":   body.role,
                "ac":  body.avatar_color or "#2563eb",
            },
        )
    ).mappings().one()
    await db.commit()
    return dict(row)


@router.patch("/speakers/{speaker_id}", response_model=SpeakerOut)
async def edit_speaker(
    session_id: UUID, speaker_id: UUID, body: SpeakerPatch,
    db: DbSession, _user: CurrentUser,
) -> dict:
    """Phase 9: edit a speaker. Only the supplied fields are updated;
    omitted fields are preserved via COALESCE."""
    row = (
        await db.execute(
            text(
                """
                UPDATE speakers
                   SET name         = COALESCE(:n,  name),
                       role         = COALESCE(:r,  role),
                       avatar_color = COALESCE(:ac, avatar_color)
                 WHERE id = CAST(:id AS uuid)
                   AND session_id = CAST(:sid AS uuid)
             RETURNING id, name AS short, name, role, avatar_color
                """
            ),
            {
                "id":  str(speaker_id),
                "sid": str(session_id),
                "n":   body.name,
                "r":   body.role,
                "ac":  body.avatar_color,
            },
        )
    ).mappings().first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Speaker {speaker_id} not in session {session_id}")
    await db.commit()
    return dict(row)


@router.delete("/speakers/{speaker_id}", status_code=204)
async def remove_speaker(
    session_id: UUID, speaker_id: UUID, db: DbSession, _user: CurrentUser,
):
    """Phase 9: remove a speaker. Segments referencing this speaker have
    their `speaker_id` set to NULL via the FK's ON DELETE SET NULL. The
    audit ledger (correction with type=speaker_reassignment) is the
    historical record — speaker rows can be deleted without losing edit
    history.

    Returns 204 No Content per FastAPI envelope convention."""
    from fastapi import HTTPException, Response

    result = await db.execute(
        text(
            "DELETE FROM speakers WHERE id = CAST(:id AS uuid) "
            "AND session_id = CAST(:sid AS uuid) RETURNING id"
        ),
        {"id": str(speaker_id), "sid": str(session_id)},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Speaker {speaker_id} not in session {session_id}")
    await db.commit()
    return Response(status_code=204)


@router.post("/segments/{segment_id}/speaker-reassign", response_model=SpeakerOut)
async def reassign_segment_speaker(
    session_id: UUID, segment_id: UUID, body: SpeakerReassignRequest,
    db: DbSession, _user: CurrentUser,
) -> dict:
    """Phase 9: change which speaker a segment is attributed to. Validates
    that both the segment and target speaker belong to the session (so
    operators can't accidentally reassign across sessions).

    Per the Phase 4 corrections plan, callers should ALSO record a
    speaker_reassignment correction in the same flow so undo works.
    """
    from fastapi import HTTPException

    # Validate speaker belongs to session
    speaker = (
        await db.execute(
            text(
                "SELECT id, name AS short, name, role, avatar_color FROM speakers "
                "WHERE id = CAST(:sp AS uuid) AND session_id = CAST(:sid AS uuid)"
            ),
            {"sp": str(body.speaker_id), "sid": str(session_id)},
        )
    ).mappings().first()
    if not speaker:
        raise HTTPException(status_code=404, detail=f"Speaker {body.speaker_id} not in session {session_id}")

    # Validate segment belongs to session
    seg = (
        await db.execute(
            text(
                "SELECT id FROM segments WHERE id = CAST(:seg AS uuid) "
                "AND session_id = CAST(:sid AS uuid)"
            ),
            {"seg": str(segment_id), "sid": str(session_id)},
        )
    ).first()
    if not seg:
        raise HTTPException(status_code=404, detail=f"Segment {segment_id} not in session {session_id}")

    await db.execute(
        text(
            "UPDATE segments SET speaker_id = CAST(:sp AS uuid), updated_at = now() "
            "WHERE id = CAST(:seg AS uuid)"
        ),
        {"sp": str(body.speaker_id), "seg": str(segment_id)},
    )
    await db.commit()
    return dict(speaker)


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


# ─── words (real STT data from `words` table) ──────────────────────────
class WordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    segment_id: UUID
    seq: int
    word: str
    start_ms: int
    end_ms: int
    confidence: float


@router.get("/words", response_model=list[WordOut])
async def list_words(session_id: UUID, db: DbSession, _user: CurrentUser) -> list[dict[str, Any]]:
    """
    Return real per-word Google STT tokens for this session, ordered along
    the timeline. Populated by `stt_background_task` after AI mode direct
    upload (or in-line by `transcribe_task` for enhanced pipeline). Returns
    [] if STT hasn't run yet — frontend STT pane should fall back to its
    placeholder UI in that case.
    """
    rows = (
        await db.execute(
            text(
                """
                SELECT w.id, w.segment_id, w.seq, w.word,
                       w.start_ms, w.end_ms, w.confidence
                  FROM words w
                  JOIN segments s ON s.id = w.segment_id
                 WHERE s.session_id = CAST(:sid AS uuid)
                 ORDER BY s.start_ms ASC, w.seq ASC
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
