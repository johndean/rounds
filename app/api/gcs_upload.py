"""
/v1/gcs — signed-URL endpoint + upload-complete with R7 scope-validation.

Ports MIC audit §2.7 / §8 (`app/api/gcs_upload.py:62-105` and `:287-362`).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession
from app.services.gcs import (
    find_out_of_scope_uri,
    make_signed_put_url,
    session_prefix,
)

router = APIRouter(prefix="/v1/gcs", tags=["gcs"])


# ─── /upload-url ────────────────────────────────────────────────────────
class UploadUrlRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    filename:   str = Field(..., min_length=1, max_length=512)
    role:       Optional[str] = Field(default=None, max_length=64)


class UploadUrlResponse(BaseModel):
    signed_url: str
    gcs_uri:    str
    blob_name:  str


@router.post("/upload-url", response_model=UploadUrlResponse)
async def signed_url(payload: UploadUrlRequest, _user: CurrentUser) -> UploadUrlResponse:
    """Returns a 60-minute v4 PUT signed URL for the given session/role/filename."""
    from app.middleware.rate_limit import check_user_quota

    check_user_quota(_user)
    try:
        signed, uri = make_signed_put_url(payload.session_id, payload.role, payload.filename)
    except Exception as exc:  # GCS SDK failures
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GCS sign failed: {exc.__class__.__name__}",
        ) from exc
    blob_name = uri.split("/", 3)[-1] if uri.count("/") >= 3 else uri
    return UploadUrlResponse(signed_url=signed, gcs_uri=uri, blob_name=blob_name)


# ─── /upload-complete ───────────────────────────────────────────────────
class UploadCompleteFile(BaseModel):
    gcs_uri:      str = Field(..., min_length=1)
    role:         Optional[str] = None
    filename:     Optional[str] = None
    content_type: Optional[str] = None
    size_bytes:   Optional[int] = None
    duration_sec: Optional[int] = None


class UploadCompleteRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    files:      list[UploadCompleteFile]


class UploadCompleteResponse(BaseModel):
    session_id: str
    accepted:   list[str]
    manifest:   Optional[dict] = None


@router.post("/upload-complete", response_model=UploadCompleteResponse)
async def upload_complete(
    payload: UploadCompleteRequest,
    db: DbSession,
    _user: CurrentUser,
) -> UploadCompleteResponse:
    """
    Confirm upload. Enforces R7: every gcs_uri MUST start with the session's
    scoped prefix. Out-of-scope uris are rejected with 400 VALIDATION_FAILED
    (matches MIC audit §2.7 / `_find_out_of_scope_uri`).

    Persists one row per uploaded file in the `sources` table. ON CONFLICT
    (gcs_uri) DO NOTHING — uploading the same blob twice is idempotent.

    After persisting sources, enqueues the Celery `ingest` task which
    fans out to transcribe + slide_extract + align + finalize. Enqueue
    failures are non-fatal — the upload still succeeded and the operator
    can re-trigger ingest via `/v1/diag/reingest/{session_id}` (Phase 6b).
    """
    from app.middleware.rate_limit import reserve_slot, validate_files

    validate_files(payload.files, payload.session_id)
    reserve_slot(_user.email, payload.session_id)

    files_as_dicts = [f.model_dump() for f in payload.files]
    out_of_scope = find_out_of_scope_uri(files_as_dicts, payload.session_id)
    if out_of_scope is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_FAILED",
                "message": "gcs_uri outside session scope",
                "expected_prefix": session_prefix(payload.session_id),
                "offending_uri": out_of_scope,
            },
        )

    accepted: list[str] = []
    for f in payload.files:
        await db.execute(
            text(
                """
                INSERT INTO sources (session_id, role, filename, gcs_uri, content_type, size_bytes, duration_sec)
                VALUES (CAST(:session_id AS uuid), :role, :filename, :gcs_uri, :content_type, :size_bytes, :duration_sec)
                ON CONFLICT (gcs_uri) DO NOTHING
                """
            ),
            {
                "session_id":   payload.session_id,
                "role":         f.role or "other",
                "filename":     f.filename or f.gcs_uri.rsplit("/", 1)[-1],
                "gcs_uri":      f.gcs_uri,
                "content_type": f.content_type,
                "size_bytes":   f.size_bytes,
                "duration_sec": f.duration_sec,
            },
        )
        accepted.append(f.gcs_uri)
    await db.commit()

    # Parse manifest + chat sources if present (Phase 6f). Non-fatal —
    # ingest still runs even if parsing returns an empty result.
    manifest_summary = await _parse_manifest_and_chat_sources(payload.session_id, payload.files, db)

    # Kick off the Celery ingest pipeline.
    try:
        from app.tasks.ingest import enqueue_ingest

        enqueue_ingest(payload.session_id)
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning(
            f"upload-complete: failed to enqueue ingest for {payload.session_id}: {exc}"
        )

    return UploadCompleteResponse(
        session_id=payload.session_id,
        accepted=accepted,
        manifest=manifest_summary,
    )


async def _parse_manifest_and_chat_sources(
    session_id: str, files: list[UploadCompleteFile], db,
) -> Optional[dict]:
    """
    Parse manifest (role='manifest') + chat (role='chat') sources.
    Writes session_speakers / session_slide_resources / sessions metadata for
    manifest, and chat_messages rows for chat. Returns a manifest summary dict.
    """
    import json
    import logging

    from app.engines.chat_parser import parse_chat_file
    from app.services.extras2_parser import parse_extras2

    logger = logging.getLogger(__name__)

    summary: Optional[dict] = None

    manifest_files = [f for f in files if f.role == "manifest"]
    chat_files = [f for f in files if f.role == "chat"]

    if manifest_files:
        try:
            raw = _read_gcs_text(manifest_files[0].gcs_uri)
            parsed = parse_extras2(raw)

            from sqlalchemy import text

            # Update session metadata
            updates = []
            params: dict = {"sid": session_id}
            if parsed.title_long:
                updates.append("title_long = :tl"); params["tl"] = parsed.title_long
            if parsed.title_short:
                updates.append("title_short = :ts"); params["ts"] = parsed.title_short
            if parsed.ce_broker_id:
                updates.append("ce_broker_id = :ce"); params["ce"] = parsed.ce_broker_id
            if parsed.class_id:
                updates.append("class_id = :cl"); params["cl"] = parsed.class_id
            if parsed.tags:
                updates.append("tags = CAST(:tg AS jsonb)"); params["tg"] = json.dumps(parsed.tags)
            if parsed.publishing_links:
                updates.append("publishing_links = CAST(:pl AS jsonb)"); params["pl"] = json.dumps(parsed.publishing_links)
            if parsed.polls:
                updates.append("polls_raw = :pr"); params["pr"] = parsed.polls
            if parsed.polls_parsed:
                updates.append("polls_parsed = CAST(:pp AS jsonb)"); params["pp"] = json.dumps(parsed.polls_parsed)
            if updates:
                await db.execute(
                    text(f"UPDATE sessions SET {', '.join(updates)}, updated_at = now() WHERE id = CAST(:sid AS uuid)"),
                    params,
                )

            # Write session_speakers
            for sp in parsed.speakers:
                await db.execute(
                    text(
                        """
                        INSERT INTO session_speakers (session_id, role, name, credentials, bio, sort_order)
                        VALUES (CAST(:sid AS uuid), :r, :n, :c, :b, :so)
                        """
                    ),
                    {"sid": session_id, "r": sp.role, "n": sp.name,
                     "c": sp.credentials, "b": sp.bio, "so": sp.sort_order},
                )

            # Write session_slide_resources
            for rs in parsed.slide_resources:
                await db.execute(
                    text(
                        """
                        INSERT INTO session_slide_resources (session_id, slide_number, label, url, sort_order)
                        VALUES (CAST(:sid AS uuid), :n, :l, :u, :so)
                        """
                    ),
                    {"sid": session_id, "n": rs.slide_number, "l": rs.label,
                     "u": rs.url, "so": rs.sort_order},
                )

            await db.commit()

            summary = {
                "parsed":              True,
                "code":                parsed.code,
                "title_long":          parsed.title_long,
                "title_short":         parsed.title_short,
                "speakers":            [{"role": s.role, "name": s.name, "credentials": s.credentials}
                                        for s in parsed.speakers],
                "slide_resource_count": len(parsed.slide_resources),
                "publishing_links":    list(parsed.publishing_links.keys()),
                "polls_parsed_count":  len(parsed.polls_parsed),
            }
        except Exception:
            logger.exception(f"manifest parse failed for session {session_id}")
            summary = {"parsed": False}

    if chat_files:
        try:
            raw = _read_gcs_text(chat_files[0].gcs_uri)
            messages = parse_chat_file(raw)
            from sqlalchemy import text
            for msg in messages:
                await db.execute(
                    text(
                        """
                        INSERT INTO chat_messages
                            (session_id, author, body, sent_at_ms, placed)
                        VALUES
                            (CAST(:sid AS uuid), :author, :body, :ts, FALSE)
                        """
                    ),
                    {
                        "sid":    session_id,
                        "author": msg["speaker"],
                        "body":   msg["message"],
                        "ts":     int(round((msg["timestamp"] or 0) * 1000)),
                    },
                )
            await db.commit()
            if summary is None:
                summary = {}
            summary["chat_messages"] = len(messages)
        except Exception:
            logger.exception(f"chat parse failed for session {session_id}")

    return summary


def _read_gcs_text(gcs_uri: str) -> str:
    """Download GCS object as utf-8 text."""
    from google.cloud import storage as gcs_lib

    from app.config import settings

    assert gcs_uri.startswith("gs://"), gcs_uri
    without = gcs_uri[5:]
    bucket_name, _, blob_name = without.partition("/")
    client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
    return client.bucket(bucket_name).blob(blob_name).download_as_text(encoding="utf-8")
