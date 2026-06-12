"""
/v1/sessions/{id}/{slides,chat,polls,sources,speakers}

Sub-resources that the frontend views consume. Until ingest produces real
rows these endpoints return empty arrays — every list endpoint is safe to
call against an empty session and produces a clean "no data yet" state on
the UI.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import bindparam, text

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
    # ORDER BY name (not created_at — the speakers table has no created_at
    # column, see migrations/001_init.sql:69-76). Earlier code referenced
    # created_at and 500'd on every call; the fixture-fallback in the editor
    # silently masked it by showing demo speakers.
    rows = (
        await db.execute(
            text(
                """
                SELECT id, name AS short, name, role, avatar_color
                FROM speakers
                WHERE session_id = :sid
                ORDER BY name ASC
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


# ─── bulk reassign (speaker and/or slide) ───────────────────────────────
# Net-new feature (not in the React SSOT): reassign the speaker and/or slide
# for many selected segments in one set-based action instead of one-by-one.
# Deliberately decoupled from the correction_ledger pointer-undo (which reverts
# text edits + split/merge only, never speaker/slide). Batches of <= the undo
# cap snapshot prior (speaker_id, slide_id) into bulk_reassign_batches (mig 059)
# so a dedicated /undo can restore them; larger batches are not undoable and the
# UI warns first. Gated by BULK_REASSIGN_ENABLED (default off → 503).
class BulkReassignRequest(BaseModel):
    segment_ids: list[UUID]
    speaker_id: Optional[UUID] = None
    slide_id: Optional[UUID] = None


@router.post("/segments/bulk-reassign")
async def bulk_reassign_segments(
    session_id: UUID, body: BulkReassignRequest, db: DbSession, user: CurrentUser,
) -> dict:
    from app.config import settings
    if not settings.BULK_REASSIGN_ENABLED:
        raise HTTPException(status_code=503, detail={"code": "BULK_REASSIGN_DISABLED"})
    if body.speaker_id is None and body.slide_id is None:
        raise HTTPException(status_code=400, detail="speaker_id or slide_id is required")

    sid = str(session_id)
    ids = list(dict.fromkeys(str(s) for s in body.segment_ids))  # de-dupe, keep order
    if not ids:
        raise HTTPException(status_code=400, detail="segment_ids must be non-empty")
    if len(ids) > settings.BULK_REASSIGN_MAX_SEGMENTS:
        raise HTTPException(
            status_code=400,
            detail={"code": "BULK_REASSIGN_TOO_MANY", "max": settings.BULK_REASSIGN_MAX_SEGMENTS},
        )

    # Targets must belong to this session (no cross-session moves).
    if body.speaker_id is not None:
        ok = (await db.execute(
            text("SELECT 1 FROM speakers WHERE id = CAST(:sp AS uuid) AND session_id = CAST(:sid AS uuid)"),
            {"sp": str(body.speaker_id), "sid": sid},
        )).first()
        if not ok:
            raise HTTPException(status_code=404, detail=f"Speaker {body.speaker_id} not in session {session_id}")
    if body.slide_id is not None:
        ok = (await db.execute(
            text("SELECT 1 FROM slides WHERE id = CAST(:sl AS uuid) AND session_id = CAST(:sid AS uuid)"),
            {"sl": str(body.slide_id), "sid": sid},
        )).first()
        if not ok:
            raise HTTPException(status_code=404, detail=f"Slide {body.slide_id} not in session {session_id}")

    id_uuids = [uuid.UUID(x) for x in ids]
    # Restrict to segments that actually belong to this session; capture prior state.
    rows = (await db.execute(
        text(
            "SELECT id, speaker_id, slide_id FROM segments "
            "WHERE session_id = CAST(:sid AS uuid) AND id IN :ids"
        ).bindparams(bindparam("ids", expanding=True)),
        {"sid": sid, "ids": id_uuids},
    )).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No matching segments in this session")

    matched_uuids = [r["id"] if isinstance(r["id"], uuid.UUID) else uuid.UUID(str(r["id"])) for r in rows]
    undoable = len(rows) <= settings.BULK_REASSIGN_UNDO_MAX_SEGMENTS
    prior_values = (
        [
            {
                "segment_id": str(r["id"]),
                "prior_speaker_id": str(r["speaker_id"]) if r["speaker_id"] else None,
                "prior_slide_id": str(r["slide_id"]) if r["slide_id"] else None,
            }
            for r in rows
        ]
        if undoable
        else None
    )

    set_sp = body.speaker_id is not None
    set_sl = body.slide_id is not None
    await db.execute(
        text(
            "UPDATE segments SET "
            "  speaker_id = CASE WHEN :set_sp THEN CAST(:sp AS uuid) ELSE speaker_id END, "
            "  slide_id   = CASE WHEN :set_sl THEN CAST(:sl AS uuid) ELSE slide_id END, "
            "  updated_at = now() "
            "WHERE session_id = CAST(:sid AS uuid) AND id IN :ids"
        ).bindparams(bindparam("ids", expanding=True)),
        {
            "set_sp": set_sp, "sp": str(body.speaker_id) if set_sp else None,
            "set_sl": set_sl, "sl": str(body.slide_id) if set_sl else None,
            "sid": sid, "ids": matched_uuids,
        },
    )

    kind = "+".join(k for k, on in (("speaker", set_sp), ("slide", set_sl)) if on)
    batch = (await db.execute(
        text(
            "INSERT INTO bulk_reassign_batches "
            "  (session_id, actor_email, kind, target_speaker_id, target_slide_id, "
            "   segment_count, undoable, prior_values) "
            "VALUES (CAST(:sid AS uuid), :actor, :kind, CAST(:tsp AS uuid), CAST(:tsl AS uuid), "
            "        :cnt, :undoable, CAST(:pv AS jsonb)) "
            "RETURNING id"
        ),
        {
            "sid": sid, "actor": user.email, "kind": kind,
            "tsp": str(body.speaker_id) if set_sp else None,
            "tsl": str(body.slide_id) if set_sl else None,
            "cnt": len(rows), "undoable": undoable,
            "pv": json.dumps(prior_values) if prior_values is not None else None,
        },
    )).first()
    batch_id = str(batch[0])

    await db.execute(
        text(
            "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
            "VALUES (CAST(:sid AS uuid), :actor, 'segment.bulk_reassign', :sum, CAST(:d AS jsonb))"
        ),
        {
            "sid": sid, "actor": user.email,
            "sum": f"bulk {kind} reassign of {len(rows)} segments",
            "d": json.dumps({"batch_id": batch_id, "kind": kind, "count": len(rows), "undoable": undoable}),
        },
    )
    await db.commit()
    return {
        "batch_id": batch_id,
        "reassigned": len(rows),
        "kind": kind,
        "undoable": undoable,
        "undo_max": settings.BULK_REASSIGN_UNDO_MAX_SEGMENTS,
    }


@router.post("/segments/bulk-reassign/{batch_id}/undo")
async def undo_bulk_reassign(
    session_id: UUID, batch_id: UUID, db: DbSession, user: CurrentUser,
) -> dict:
    from app.config import settings
    # Shared undo for both bulk reassign and reorder batches — allowed when
    # either feature is enabled (undo is inherently safe; it only restores
    # snapshotted prior values).
    if not (settings.BULK_REASSIGN_ENABLED or settings.SEGMENT_REORDER_ENABLED):
        raise HTTPException(status_code=503, detail={"code": "BULK_REASSIGN_DISABLED"})
    sid = str(session_id)
    batch = (await db.execute(
        text(
            "SELECT id, kind, undoable, undone, prior_values FROM bulk_reassign_batches "
            "WHERE id = CAST(:b AS uuid) AND session_id = CAST(:sid AS uuid)"
        ),
        {"b": str(batch_id), "sid": sid},
    )).mappings().first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    if not batch["undoable"]:
        raise HTTPException(status_code=409, detail={"code": "BULK_REASSIGN_NOT_UNDOABLE"})
    if batch["undone"]:
        raise HTTPException(status_code=409, detail={"code": "BULK_REASSIGN_ALREADY_UNDONE"})

    prior = batch["prior_values"]
    if isinstance(prior, str):
        prior = json.loads(prior)
    restored = 0
    for entry in (prior or []):
        # Restore ONLY the columns this batch snapshotted. A reorder batch
        # carries prior_seq only (so it never NULLs speaker_id/slide_id); a
        # reassign batch carries prior_speaker_id + prior_slide_id (so it never
        # touches seq). Column fragments are fixed literals; values are bound.
        sets: list[str] = []
        params: dict[str, object] = {"seg": entry["segment_id"], "sid": sid}
        if "prior_speaker_id" in entry:
            sets.append("speaker_id = CAST(:sp AS uuid)"); params["sp"] = entry["prior_speaker_id"]
        if "prior_slide_id" in entry:
            sets.append("slide_id = CAST(:sl AS uuid)"); params["sl"] = entry["prior_slide_id"]
        if "prior_seq" in entry:
            sets.append("seq = :sq"); params["sq"] = entry["prior_seq"]
        if not sets:
            continue
        await db.execute(
            text(
                f"UPDATE segments SET {', '.join(sets)}, updated_at = now() "
                "WHERE id = CAST(:seg AS uuid) AND session_id = CAST(:sid AS uuid)"
            ),
            params,
        )
        restored += 1

    await db.execute(
        text("UPDATE bulk_reassign_batches SET undone = TRUE, undone_at = now() WHERE id = CAST(:b AS uuid)"),
        {"b": str(batch_id)},
    )
    await db.execute(
        text(
            "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
            "VALUES (CAST(:sid AS uuid), :actor, 'segment.bulk_reassign_undo', :sum, CAST(:d AS jsonb))"
        ),
        {"sid": sid, "actor": user.email,
         "sum": f"undo {batch['kind']} batch {batch_id} ({restored} segments)",
         "d": json.dumps({"batch_id": str(batch_id), "kind": batch["kind"], "restored": restored})},
    )
    await db.commit()
    return {"batch_id": str(batch_id), "restored": restored}


# ─── bulk reorder (vertical drag-drop) — gated by SEGMENT_REORDER_ENABLED ──
# Rewrites segments.seq to match a client-supplied FULL permutation of the
# session's segment IDs. seq-only: never touches timing, slide, speaker, text,
# or the corrections ledger. Always undoable via a cheap prior-seq snapshot
# reused into bulk_reassign_batches (kind='reorder'). Plan:
# docs/plans/2026-06-12-001-segment-drag-drop-reorder.md.
def _reorder_changes(current_seq: dict[str, int], ordered_ids: list[str]) -> list[tuple[str, int]]:
    """Pure: given current {segment_id: seq} and the desired full order, return
    the (segment_id, new_seq) pairs whose seq actually changes. Caller must have
    validated that ordered_ids is an exact permutation of current_seq.keys().
    Unit-tested without a DB (tests/test_segment_reorder.py)."""
    return [(sid, i) for i, sid in enumerate(ordered_ids) if current_seq.get(sid) != i]


class SegmentReorderRequest(BaseModel):
    ordered_segment_ids: list[UUID]


@router.post("/segments/reorder")
async def reorder_segments(
    session_id: UUID, body: SegmentReorderRequest, db: DbSession, user: CurrentUser,
) -> dict:
    from app.config import settings
    if not settings.SEGMENT_REORDER_ENABLED:
        raise HTTPException(status_code=503, detail={"code": "SEGMENT_REORDER_DISABLED"})
    sid = str(session_id)
    ordered = [str(s) for s in body.ordered_segment_ids]
    if len(ordered) != len(set(ordered)):
        raise HTTPException(status_code=400, detail="ordered_segment_ids contains duplicates")

    rows = (await db.execute(
        text("SELECT id, seq FROM segments WHERE session_id = CAST(:sid AS uuid)"),
        {"sid": sid},
    )).mappings().all()
    current = {str(r["id"]): r["seq"] for r in rows}
    # Must be an EXACT permutation of the session's segments — guarantees no
    # segment is lost, added, or duplicated (the core safety property).
    if set(ordered) != set(current.keys()):
        raise HTTPException(status_code=409, detail={"code": "REORDER_STALE"})

    # Only rows whose seq actually changes are touched / snapshotted.
    changed = _reorder_changes(current, ordered)
    if not changed:
        return {"batch_id": None, "reordered": 0, "kind": "reorder", "undoable": True}
    prior_values = [{"segment_id": seg_id, "prior_seq": current[seg_id]} for seg_id, _ in changed]

    from app.services import db_locks
    async with db_locks.try_advisory_lock_async(db, session_id=sid, stage="split_merge") as acquired:
        if not acquired:
            raise HTTPException(status_code=409, detail={"code": "SPLIT_MERGE_BUSY"})
        # Single-statement seq rewrite via jsonb_to_recordset with DECLARED
        # column types (id uuid, new_seq int). Declaring the types is the whole
        # safety property: a bare (VALUES ...) derived table infers each column's
        # type from its bind expression, and asyncpg sends untyped binds as text,
        # so v.new_seq came out text and Postgres rejected "seq = v.new_seq"
        # (integer) with a DatatypeMismatchError — the original 500. Mirrors
        # reorder_chat / reorder_polls. seq is non-unique (migration 022) so no
        # interim-collision constraint exists; the permutation guarantees the
        # final state is a clean 0..N-1. One jsonb payload, not N binds.
        pairs = [{"id": seg_id, "new_seq": new_seq} for seg_id, new_seq in changed]
        await db.execute(
            text(
                "UPDATE segments AS s SET seq = v.new_seq, updated_at = now() "
                "FROM (SELECT * FROM jsonb_to_recordset(CAST(:pairs AS jsonb)) "
                "      AS x(id uuid, new_seq int)) AS v "
                "WHERE s.id = v.id AND s.session_id = CAST(:sid AS uuid)"
            ),
            {"sid": sid, "pairs": json.dumps(pairs)},
        )
        batch = (await db.execute(
            text(
                "INSERT INTO bulk_reassign_batches "
                "  (session_id, actor_email, kind, segment_count, undoable, prior_values) "
                "VALUES (CAST(:sid AS uuid), :actor, 'reorder', :cnt, TRUE, CAST(:pv AS jsonb)) "
                "RETURNING id"
            ),
            {"sid": sid, "actor": user.email, "cnt": len(changed), "pv": json.dumps(prior_values)},
        )).first()
        batch_id = str(batch[0])
        await db.execute(
            text(
                "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
                "VALUES (CAST(:sid AS uuid), :actor, 'segment.reorder', :sum, CAST(:d AS jsonb))"
            ),
            {"sid": sid, "actor": user.email,
             "sum": f"reordered {len(changed)} segments",
             "d": json.dumps({"batch_id": batch_id, "changed": len(changed)})},
        )
        await db.commit()
    return {"batch_id": batch_id, "reordered": len(changed), "kind": "reorder", "undoable": True}


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


# ─── media playback URL ────────────────────────────────────────────────
class MediaUrlOut(BaseModel):
    role: str
    filename: Optional[str]
    content_type: Optional[str]
    duration_sec: Optional[int]
    url: str        # signed v4 GET URL, 24h TTL


@router.get("/media-url", response_model=MediaUrlOut)
async def session_media_url(
    session_id: UUID,
    db: DbSession,
    _user: CurrentUser,
    role: str = "audio",
) -> dict:
    """Return a 24h signed GET URL for the session's primary playback source.

    Defaults to `role=audio`; pass `?role=video` for the video file if you
    want the visual track. Falls through to `audio` if the requested role
    is missing. 404 if neither exists.
    """
    from app.tasks.burn_captions import _generate_signed_url

    rows = (
        await db.execute(
            text(
                """
                SELECT role, filename, gcs_uri, content_type, duration_sec
                  FROM sources
                 WHERE session_id = :sid AND role IN ('audio', 'video')
                 ORDER BY (role = :preferred) DESC, created_at ASC
                """
            ),
            {"sid": str(session_id), "preferred": role},
        )
    ).mappings().all()

    if not rows:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No audio/video source for this session.")

    chosen = rows[0]
    return {
        "role":         chosen["role"],
        "filename":     chosen["filename"],
        "content_type": chosen["content_type"],
        "duration_sec": chosen["duration_sec"],
        "url":          _generate_signed_url(chosen["gcs_uri"], hours=24),
    }


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
    # Phase 6 (2026-06-05) — COALESCE order_index, sent_at_ms so
    # operator-reordered rows surface in their new positions while
    # un-reordered rows still appear in chronological order. Pre-fix
    # this ORDER BY was just sent_at_ms ASC.
    rows = (
        await db.execute(
            text(
                """
                SELECT id, author, body, sent_at_ms, anchor_segment, placed
                FROM chat_messages WHERE session_id = :sid
                ORDER BY (order_index IS NULL) ASC, order_index ASC, sent_at_ms ASC
                """
            ),
            {"sid": str(session_id)},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


class ReorderRequest(BaseModel):
    """Body for the bulk reorder endpoints. ``ids`` is the new desired
    order of the rows in the session's chat or polls list. Positions
    are 1-indexed (matches how operators think about list order)."""
    ids: list[UUID]


@router.patch("/chat/order")
async def reorder_chat(session_id: UUID, body: ReorderRequest, db: DbSession, user: CurrentUser) -> dict:
    """Bulk-reorder chat messages within a session.

    Accepts the new desired order of rows as an array of UUIDs. Sets
    ``order_index = position`` (1-indexed) for every row in the array.
    Rows NOT in the array keep their existing order_index (or NULL),
    which is the right behavior when the operator partial-reorders
    only the top of a long thread.

    Validation: every UUID must already exist in this session's
    chat_messages, else a 400 is returned (prevents accidentally
    inserting a foreign row's id). All-or-nothing transaction so a
    bad request can't leave a partially-renumbered list.

    Phase 6 of the 2026-06-04 stakeholder remediation."""
    if not body.ids:
        raise HTTPException(status_code=400, detail={
            "code": "EMPTY_REORDER",
            "message": "ids array must contain at least one chat message id",
        })
    # Sanity-check membership: every requested id must belong to this session.
    existing = (
        await db.execute(
            text("SELECT id FROM chat_messages WHERE session_id = CAST(:sid AS uuid)"),
            {"sid": str(session_id)},
        )
    ).scalars().all()
    existing_set = {str(uid) for uid in existing}
    bad = [str(uid) for uid in body.ids if str(uid) not in existing_set]
    if bad:
        raise HTTPException(status_code=400, detail={
            "code": "UNKNOWN_CHAT_IDS",
            "message": f"{len(bad)} id(s) not in this session",
            "ids": bad[:5],
        })
    # Phase 6.2 hardening (2026-06-05) — collapse N per-row UPDATEs into
    # a single statement. With ~100-row chat threads the old loop did
    # 100 network round-trips per reorder (operator-interactive hot
    # path). The jsonb_to_recordset construct keeps the wire payload
    # to one PATCH with one query.
    import json
    pairs = [{"id": str(mid), "pos": pos} for pos, mid in enumerate(body.ids, start=1)]
    await db.execute(
        text(
            "UPDATE chat_messages t SET order_index = v.pos "
            "FROM (SELECT * FROM jsonb_to_recordset(CAST(:pairs AS jsonb)) AS x(id uuid, pos int)) AS v "
            "WHERE t.id = v.id AND t.session_id = CAST(:sid AS uuid)"
        ),
        {"pairs": json.dumps(pairs), "sid": str(session_id)},
    )
    await db.execute(
        text(
            "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
            "VALUES (CAST(:sid AS uuid), :a, 'chat.reorder', :s, CAST(:d AS jsonb))"
        ),
        {
            "sid": str(session_id),
            "a":   user.email,
            "s":   f"reordered {len(body.ids)} chat message(s)",
            "d":   json.dumps({"count": len(body.ids), "first_3": [str(i) for i in body.ids[:3]]}),
        },
    )
    await db.commit()
    return {"reordered": len(body.ids), "ids": [str(i) for i in body.ids]}


class AnchorPatch(BaseModel):
    anchor_segment: Optional[UUID] = None  # null clears placement


@router.patch("/chat/{message_id}", response_model=ChatMessageOut)
async def patch_chat_anchor(
    session_id: UUID, message_id: UUID, body: AnchorPatch,
    db: DbSession, _user: CurrentUser,
) -> dict:
    """Persist drag-to-place: set or clear anchor_segment + placed flag.
    Idempotent. 404 if the message doesn't belong to the session."""
    row = (
        await db.execute(
            text(
                """
                UPDATE chat_messages
                   SET anchor_segment = CAST(:anc AS uuid),
                       placed         = (:anc IS NOT NULL)
                 WHERE id = :mid AND session_id = :sid
             RETURNING id, author, body, sent_at_ms, anchor_segment, placed
                """
            ),
            {
                "mid": str(message_id),
                "sid": str(session_id),
                "anc": str(body.anchor_segment) if body.anchor_segment else None,
            },
        )
    ).mappings().first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Chat message not found in this session.")
    await db.commit()
    return dict(row)


# ─── chat participants tally (Phase 3 of 2026-06-04 stakeholder remediation) ──
class ChatParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    speaker:       str
    message_count: int
    first_seen_ms: int
    last_seen_ms:  int


@router.get("/chat-participants", response_model=list[ChatParticipantOut])
async def list_chat_participants(
    session_id: UUID, db: DbSession, _user: CurrentUser,
) -> list[dict]:
    """
    Aggregate ``chat_messages`` by author for a session.

    Returns one row per distinct speaker with the count of messages they
    posted and their first/last message timestamps (ms offset from
    session start). Ordered by message count descending, then by
    speaker name ascending for deterministic tie-breaking. Returns an
    empty list when the session has no chat — every call is safe even
    for sessions ingested before chat extraction landed.

    Powers SessionDetailView's Chat Participants tally widget.
    Authorization mirrors the existing ``/chat`` endpoint (any
    authenticated user). Reads only; no mutations.
    """
    rows = (
        await db.execute(
            text(
                "SELECT author               AS speaker, "
                "       COUNT(*)::int        AS message_count, "
                "       MIN(sent_at_ms)::int AS first_seen_ms, "
                "       MAX(sent_at_ms)::int AS last_seen_ms "
                "FROM chat_messages "
                "WHERE session_id = :sid "
                "GROUP BY author "
                "ORDER BY COUNT(*) DESC, author ASC"
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
    # JSONB metadata blob from the extras2 manifest parse — carries
    # `slide_n` (1-based slide the poll was opened on) and `q_n`. The
    # editor's client-side _inferAnchor() uses metadata.slide_n as a
    # fallback when anchor_segment is null (sessions ingested before
    # poll_autoplace ran). Without this field on the wire, the fallback
    # silently no-ops and polls show as unplaced.
    metadata: Optional[dict[str, Any]] = None
    options: list[PollOptionOut]


@router.get("/polls", response_model=list[PollOut])
async def list_polls(session_id: UUID, db: DbSession, _user: CurrentUser) -> list[dict[str, Any]]:
    # Phase 6 (2026-06-05) — COALESCE order_index, opened_at_ms so
    # operator-reordered polls surface in their new positions while
    # un-reordered polls still appear in chronological order.
    polls = (
        await db.execute(
            text(
                """
                SELECT id, question, status, opened_at_ms, closed_at_ms,
                       total_votes, anchor_segment, placed, metadata
                FROM polls WHERE session_id = :sid
                ORDER BY (order_index IS NULL) ASC, order_index ASC, opened_at_ms ASC
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


@router.patch("/polls/order")
async def reorder_polls(session_id: UUID, body: ReorderRequest, db: DbSession, user: CurrentUser) -> dict:
    """Bulk-reorder polls within a session. Mirror of /chat/order.

    Sets ``order_index = position`` (1-indexed) for every poll id in
    the supplied list. Validation + transaction semantics match the
    chat variant: every id must belong to this session; all-or-nothing
    update so a bad request can't half-renumber the list.

    Phase 6 of the 2026-06-04 stakeholder remediation."""
    if not body.ids:
        raise HTTPException(status_code=400, detail={
            "code": "EMPTY_REORDER",
            "message": "ids array must contain at least one poll id",
        })
    existing = (
        await db.execute(
            text("SELECT id FROM polls WHERE session_id = CAST(:sid AS uuid)"),
            {"sid": str(session_id)},
        )
    ).scalars().all()
    existing_set = {str(uid) for uid in existing}
    bad = [str(uid) for uid in body.ids if str(uid) not in existing_set]
    if bad:
        raise HTTPException(status_code=400, detail={
            "code": "UNKNOWN_POLL_IDS",
            "message": f"{len(bad)} id(s) not in this session",
            "ids": bad[:5],
        })
    # Phase 6.2 hardening — single-statement renumber (see reorder_chat).
    import json
    pairs = [{"id": str(pid), "pos": pos} for pos, pid in enumerate(body.ids, start=1)]
    await db.execute(
        text(
            "UPDATE polls t SET order_index = v.pos "
            "FROM (SELECT * FROM jsonb_to_recordset(CAST(:pairs AS jsonb)) AS x(id uuid, pos int)) AS v "
            "WHERE t.id = v.id AND t.session_id = CAST(:sid AS uuid)"
        ),
        {"pairs": json.dumps(pairs), "sid": str(session_id)},
    )
    await db.execute(
        text(
            "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
            "VALUES (CAST(:sid AS uuid), :a, 'polls.reorder', :s, CAST(:d AS jsonb))"
        ),
        {
            "sid": str(session_id),
            "a":   user.email,
            "s":   f"reordered {len(body.ids)} poll(s)",
            "d":   json.dumps({"count": len(body.ids), "first_3": [str(i) for i in body.ids[:3]]}),
        },
    )
    await db.commit()
    return {"reordered": len(body.ids), "ids": [str(i) for i in body.ids]}


@router.patch("/polls/{poll_id}/anchor")
async def patch_poll_anchor(
    session_id: UUID, poll_id: UUID, body: AnchorPatch,
    db: DbSession, _user: CurrentUser,
) -> dict:
    """Persist drag-to-place for polls: set or clear anchor_segment + placed.
    Idempotent. 404 if the poll doesn't belong to the session."""
    row = (
        await db.execute(
            text(
                """
                UPDATE polls
                   SET anchor_segment = CAST(:anc AS uuid),
                       placed         = (:anc IS NOT NULL)
                 WHERE id = :pid AND session_id = :sid
             RETURNING id, question, status, opened_at_ms, closed_at_ms,
                       total_votes, anchor_segment, placed
                """
            ),
            {
                "pid": str(poll_id),
                "sid": str(session_id),
                "anc": str(body.anchor_segment) if body.anchor_segment else None,
            },
        )
    ).mappings().first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Poll not found in this session.")
    await db.commit()
    return dict(row)
