"""
/v1/sessions/{id}/missing|add/* — admin file management for a live session.

Ports MIC `app/api/add_to_session.py` (1187 LOC) to Rounds raw-SQL idiom.

Endpoints:
  GET  /v1/sessions/{id}/missing
  POST /v1/sessions/{id}/add/signed-url
  POST /v1/sessions/{id}/add/slides     (multipart `slide_file` OR JSON {gcs_uri})
  POST /v1/sessions/{id}/add/chat       (multipart `chat_file`  OR JSON {gcs_uri})
  POST /v1/sessions/{id}/add/manifest   (multipart `manifest_file` OR JSON {gcs_uri})

Phase 6-style staging path keeps the surface self-contained:
  gs://<bucket>/sessions/{id}/staging/phase6/<uuid>/<filename>

The bucket lifecycle reaps abandoned uploads at 48h — no Redis, no token table.

Critical invariant: every signed PUT URL is scoped to the session's
gs://<bucket>/sessions/<id>/staging/phase6/ prefix (R7 invariant — see
app/services/gcs.py). A leaked URL has limited blast radius (1h TTL,
session-scoped path).

Related business rules: BR-013 (signed-URL TTL = 3600s).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid as _uuid
from datetime import timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from sqlalchemy import text

from app.auth import CurrentUser
from app.config import settings
from app.db import DbSession
from app.middleware.envelope import (
    ConflictError,
    InternalError,
    InvalidInputError,
    NotFoundError,
    ValidationFailedError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/sessions", tags=["add-to-session"])


# ─── MIME constants ────────────────────────────────────────────────────

_PRIMARY_AV_MIMES = {
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "video/mpeg", "video/webm",
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
    "audio/mp4", "audio/x-m4a", "audio/aac",
}
_SLIDE_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
_CHAT_MIMES = {"text/plain", "text/csv", "application/octet-stream"}
_MANIFEST_MIMES = {"text/plain", "application/octet-stream"}
_TYPE_MIME_MAP = {"slides": _SLIDE_MIMES, "chat": _CHAT_MIMES, "manifest": _MANIFEST_MIMES}

_SIGNED_URL_TTL_SECONDS = 3600


# ─── GCS helpers ───────────────────────────────────────────────────────

def _gcs_client():
    from google.cloud import storage as gcs_lib
    return gcs_lib.Client(project=settings.GCP_PROJECT_ID)


def _gcs_bucket():
    return _gcs_client().bucket(settings.GCS_BUCKET)


def _gs_uri(blob_name: str) -> str:
    return f"gs://{settings.GCS_BUCKET}/{blob_name}"


def _blob_name_from_gs_uri(gcs_uri: str) -> Optional[str]:
    prefix = f"gs://{settings.GCS_BUCKET}/"
    return gcs_uri[len(prefix):] if gcs_uri.startswith(prefix) else None


def _staging_blob_name(session_id: str, filename: str) -> str:
    safe = (filename or "upload.bin").replace("/", "_").replace("\\", "_")
    return f"sessions/{session_id}/staging/phase6/{_uuid.uuid4()}/{safe}"


def _is_phase6_staging_uri(session_id: str, gcs_uri: str) -> bool:
    expected = f"gs://{settings.GCS_BUCKET}/sessions/{session_id}/staging/phase6/"
    return bool(gcs_uri) and gcs_uri.startswith(expected)


async def _gcs_upload_bytes(blob_name: str, data: bytes, content_type: str) -> str:
    def _sync():
        blob = _gcs_bucket().blob(blob_name)
        blob.upload_from_string(data, content_type=content_type or "application/octet-stream")
        return _gs_uri(blob_name)
    return await asyncio.to_thread(_sync)


async def _gcs_download_text(gcs_uri: str, encoding: str = "utf-8") -> Optional[str]:
    def _sync():
        bn = _blob_name_from_gs_uri(gcs_uri)
        if bn is None:
            return None
        blob = _gcs_bucket().blob(bn)
        if not blob.exists():
            return None
        return blob.download_as_text(encoding=encoding)
    return await asyncio.to_thread(_sync)


async def _gcs_download_bytes(gcs_uri: str) -> Optional[bytes]:
    def _sync():
        bn = _blob_name_from_gs_uri(gcs_uri)
        if bn is None:
            return None
        blob = _gcs_bucket().blob(bn)
        if not blob.exists():
            return None
        return blob.download_as_bytes()
    return await asyncio.to_thread(_sync)


async def _gcs_delete(gcs_uri: str) -> None:
    def _sync():
        bn = _blob_name_from_gs_uri(gcs_uri)
        if bn is None:
            return
        try:
            _gcs_bucket().blob(bn).delete()
        except Exception:
            pass
    await asyncio.to_thread(_sync)


def _mint_signed_put_url(blob_name: str, mime_type: str) -> str:
    blob = _gcs_bucket().blob(blob_name)
    return blob.generate_signed_url(
        version="v4",
        method="PUT",
        expiration=timedelta(seconds=_SIGNED_URL_TTL_SECONDS),
        content_type=mime_type or "application/octet-stream",
    )


def _mint_signed_get_url(blob_name: str, ttl_seconds: int = 3600) -> str:
    blob = _gcs_bucket().blob(blob_name)
    return blob.generate_signed_url(
        version="v4",
        method="GET",
        expiration=timedelta(seconds=ttl_seconds),
    )


# ─── Validation helpers ────────────────────────────────────────────────

async def _require_session(db, session_id: str) -> Optional[dict]:
    row = (
        await db.execute(
            text("SELECT id, code, title, title_long, title_short, ce_broker_id, class_id, tags, "
                 "publishing_links, polls_raw AS polls FROM sessions "
                 "WHERE id = CAST(:sid AS uuid) AND deleted_at IS NULL"),
            {"sid": session_id},
        )
    ).mappings().first()
    return dict(row) if row else None


def _reject_primary_av(mime_type: Optional[str]) -> Optional[str]:
    if mime_type and mime_type.lower() in _PRIMARY_AV_MIMES:
        return ("Primary audio/video must be uploaded through the main /upload page. "
                "For a bad recording, upload a new session and archive the old one.")
    return None


def _reject_bad_type_mime(file_type: str, mime_type: Optional[str]) -> Optional[str]:
    if file_type == "slides" and mime_type and mime_type.lower() not in _SLIDE_MIMES:
        return f"slides upload requires PDF or PPTX; got {mime_type}"
    return None


# ─── Missing-file detection ────────────────────────────────────────────

async def _compute_missing(db, session_id: str) -> dict:
    """Per-type presence booleans using authoritative tables."""
    slides_cnt = (await db.execute(
        text("SELECT count(*) AS n FROM slides WHERE session_id = CAST(:sid AS uuid)"),
        {"sid": session_id},
    )).mappings().first()["n"]

    chat_cnt = (await db.execute(
        text("SELECT count(*) AS n FROM chat_messages WHERE session_id = CAST(:sid AS uuid)"),
        {"sid": session_id},
    )).mappings().first()["n"]

    title_long = (await db.execute(
        text("SELECT title_long FROM sessions WHERE id = CAST(:sid AS uuid)"),
        {"sid": session_id},
    )).mappings().first()
    has_manifest = bool(title_long and title_long.get("title_long"))

    bios_cnt = (await db.execute(
        text("SELECT count(*) AS n FROM session_speakers "
             "WHERE session_id = CAST(:sid AS uuid) AND bio IS NOT NULL AND bio <> ''"),
        {"sid": session_id},
    )).mappings().first()["n"]

    return {
        "has_slides":   bool(slides_cnt and slides_cnt > 0),
        "has_chat":     bool(chat_cnt and chat_cnt > 0),
        "has_manifest": has_manifest,
        "has_bios":     bool(bios_cnt and bios_cnt > 0),
    }


# ─── GET /missing ──────────────────────────────────────────────────────

@router.get("/{session_id}/missing")
async def get_missing(session_id: str, db: DbSession, _u: CurrentUser) -> dict:
    if await _require_session(db, session_id) is None:
        raise NotFoundError(f"Session {session_id} not found")
    return await _compute_missing(db, session_id)


# ─── POST /add/signed-url ──────────────────────────────────────────────

@router.post("/{session_id}/add/signed-url")
async def add_signed_url(
    session_id: str, request: Request, db: DbSession, _u: CurrentUser,
) -> dict:
    if await _require_session(db, session_id) is None:
        raise NotFoundError(f"Session {session_id} not found")
    try:
        body = await request.json()
    except Exception:
        raise InvalidInputError("body must be JSON")

    filename = (body or {}).get("filename")
    mime_type = (body or {}).get("mime_type") or "application/octet-stream"
    file_type = (body or {}).get("type")

    if not filename:
        raise InvalidInputError("filename required")
    if file_type not in _TYPE_MIME_MAP:
        raise InvalidInputError(f"type must be one of {sorted(_TYPE_MIME_MAP.keys())}")

    rej = _reject_primary_av(mime_type) or _reject_bad_type_mime(file_type, mime_type)
    if rej:
        raise ValidationFailedError(rej)

    blob_name = _staging_blob_name(session_id, filename)
    try:
        signed = await asyncio.to_thread(_mint_signed_put_url, blob_name, mime_type)
    except Exception as e:
        logger.exception("add_signed_url: GCS sign failed for %s", session_id)
        raise InternalError(f"failed to mint signed URL: {e}") from e

    return {
        "signed_url": signed,
        "gcs_uri":    _gs_uri(blob_name),
        "blob_name":  blob_name,
        "mime_type":  mime_type,
        "expires_in": _SIGNED_URL_TTL_SECONDS,
    }


# ─── Common upload intake (multipart OR {gcs_uri}) ─────────────────────

async def _intake_upload(
    session_id: str,
    file_type: str,
    request: Request,
    multipart_file: Optional[UploadFile],
) -> tuple[str, str, str, int]:
    """Returns (gcs_uri, mime_type, filename, size_bytes). Raises on failure."""
    if multipart_file is not None:
        filename = multipart_file.filename or "upload.bin"
        mime_type = multipart_file.content_type or "application/octet-stream"
        rej = _reject_primary_av(mime_type) or _reject_bad_type_mime(file_type, mime_type)
        if rej:
            raise ValidationFailedError(rej)
        data = await multipart_file.read()
        size_bytes = len(data)
        blob_name = _staging_blob_name(session_id, filename)
        try:
            gcs_uri = await _gcs_upload_bytes(blob_name, data, mime_type)
        except Exception as e:
            logger.exception("_intake_upload: GCS upload failed for %s", session_id)
            raise InternalError(f"upload to GCS staging failed: {e}") from e
        return gcs_uri, mime_type, filename, size_bytes

    try:
        body = await request.json()
    except Exception:
        raise InvalidInputError("either multipart file OR JSON {gcs_uri} is required")

    gcs_uri = (body or {}).get("gcs_uri")
    if not gcs_uri:
        raise InvalidInputError("gcs_uri required")
    if not _is_phase6_staging_uri(session_id, gcs_uri):
        raise ValidationFailedError("gcs_uri outside this session's Phase 6 staging scope")

    def _stat():
        bn = _blob_name_from_gs_uri(gcs_uri)
        if bn is None:
            return None, None, None
        blob = _gcs_bucket().blob(bn)
        blob.reload()
        return blob.content_type, blob.size or 0, bn.rsplit("/", 1)[-1]

    try:
        mime_type, size_bytes, filename = await asyncio.to_thread(_stat)
    except Exception as e:
        logger.warning("_intake_upload: stat failed for %s: %s", gcs_uri, e)
        raise NotFoundError("staging blob not found — preview expired or never uploaded")

    if mime_type is None:
        raise NotFoundError("staging blob not found")
    rej = _reject_primary_av(mime_type) or _reject_bad_type_mime(file_type, mime_type)
    if rej:
        raise ValidationFailedError(rej)
    return gcs_uri, mime_type, filename, int(size_bytes or 0)


# ─── Slide thumbnail helpers (for conflict UI) ─────────────────────────

_THUMBNAIL_SCALE = 0.4
_THUMBNAIL_TTL_SECS = 3600


async def _count_pdf_pages(gcs_uri: str, mime_type: Optional[str]) -> Optional[int]:
    if (mime_type or "") != "application/pdf":
        return None
    data = await _gcs_download_bytes(gcs_uri)
    if not data:
        return None
    try:
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        n = len(doc)
        doc.close()
        return int(n)
    except Exception:
        return None


async def _render_deck_thumbnails_from_bytes(
    session_id: str, gcs_uri: str, mime_type: Optional[str],
) -> list[dict]:
    if (mime_type or "") != "application/pdf":
        return []
    data = await _gcs_download_bytes(gcs_uri)
    if not data:
        return []

    def _render():
        import fitz
        fitz.TOOLS.mupdf_display_errors(False)
        out = []
        doc = fitz.open(stream=data, filetype="pdf")
        try:
            matrix = fitz.Matrix(_THUMBNAIL_SCALE, _THUMBNAIL_SCALE)
            for i in range(len(doc)):
                pix = doc[i].get_pixmap(matrix=matrix)
                out.append((i + 1, pix.tobytes("png")))
        finally:
            doc.close()
        return out

    try:
        pages = await asyncio.to_thread(_render)
    except Exception as e:
        logger.warning("thumbnail render failed: %s", e)
        return []

    thumb_prefix = f"sessions/{session_id}/staging/phase6/thumbs/{_uuid.uuid4()}"
    sem = asyncio.Semaphore(10)

    async def _upload_one(page_num: int, png_bytes: bytes):
        blob_name = f"{thumb_prefix}/p{page_num:04d}.png"
        async with sem:
            try:
                await _gcs_upload_bytes(blob_name, png_bytes, "image/png")
                url = await asyncio.to_thread(_mint_signed_get_url, blob_name, _THUMBNAIL_TTL_SECS)
                return {"page_number": page_num, "thumbnail_url": url}
            except Exception as e:
                logger.warning("thumb upload failed page=%d: %s", page_num, e)
                return None

    res = await asyncio.gather(*[_upload_one(pn, pb) for pn, pb in pages])
    return [r for r in res if r is not None]


async def _render_deck_thumbnails_from_current(db, session_id: str) -> list[dict]:
    row = (await db.execute(
        text("""
            SELECT gcs_uri, content_type FROM sources
            WHERE session_id = CAST(:sid AS uuid)
              AND (content_type = ANY(:slide_mimes) OR role = 'slide')
            ORDER BY created_at DESC LIMIT 1
        """),
        {"sid": session_id, "slide_mimes": list(_SLIDE_MIMES)},
    )).mappings().first()
    if not row or not row["gcs_uri"]:
        return []
    return await _render_deck_thumbnails_from_bytes(
        session_id, row["gcs_uri"], row["content_type"],
    )


async def _list_existing_slide_decks(db, session_id: str) -> list[dict]:
    src_rows = (await db.execute(
        text("""
            SELECT id, gcs_uri, created_at FROM sources
            WHERE session_id = CAST(:sid AS uuid)
              AND (content_type = ANY(:slide_mimes) OR role = 'slide')
            ORDER BY created_at
        """),
        {"sid": session_id, "slide_mimes": list(_SLIDE_MIMES)},
    )).mappings().all()
    total = (await db.execute(
        text("SELECT count(*) AS n FROM slides WHERE session_id = CAST(:sid AS uuid)"),
        {"sid": session_id},
    )).mappings().first()["n"]
    decks: list[dict] = []
    for i, row in enumerate(src_rows):
        uri = row.get("gcs_uri") or ""
        fn = uri.rsplit("/", 1)[-1] if uri else f"source-{row['id']}"
        decks.append({
            "source_id":   str(row["id"]),
            "filename":    fn,
            "uploaded_at": row["created_at"].isoformat() if row.get("created_at") else None,
            "slide_count": int(total or 0) if i == 0 else 0,
        })
    return decks


# ─── POST /add/slides ──────────────────────────────────────────────────

@router.post("/{session_id}/add/slides")
async def add_slides(
    session_id: str,
    request: Request,
    db: DbSession,
    _u: CurrentUser,
    slide_file: Annotated[Optional[UploadFile], File()] = None,
    mode: Annotated[Optional[str], Query()] = None,
) -> dict:
    if await _require_session(db, session_id) is None:
        raise NotFoundError(f"Session {session_id} not found")

    gcs_uri, mime_type, filename, size_bytes = await _intake_upload(
        session_id, "slides", request, slide_file,
    )
    existing_decks = await _list_existing_slide_decks(db, session_id)
    new_deck_pages = await _count_pdf_pages(gcs_uri, mime_type)

    if existing_decks and mode not in ("replace", "append", "replace_selected"):
        current_pages = await _render_deck_thumbnails_from_current(db, session_id)
        new_pages     = await _render_deck_thumbnails_from_bytes(session_id, gcs_uri, mime_type)
        total_existing = sum(d["slide_count"] for d in existing_decks)
        raise ConflictError(
            message=(
                f"Session already has {total_existing} slide(s) across "
                f"{len(existing_decks)} deck(s). Pick Replace, Append, or Replace selected."
            ),
            details={
                "existing_decks":   existing_decks,
                "new_deck_pages":   new_deck_pages,
                "new_deck_filename": filename,
                "new_filename":     filename,
                "current_pages":    current_pages,
                "new_pages":        new_pages,
                "gcs_uri":          gcs_uri,
            },
        )

    selected: list[int] = []
    if mode == "replace_selected":
        try:
            body = await request.json()
        except Exception:
            body = {}
        raw = (body or {}).get("slide_numbers") or []
        if not isinstance(raw, list) or not raw:
            raise InvalidInputError(
                "replace_selected requires body {slide_numbers: [int, ...]} with ≥1 entry."
            )
        try:
            selected = sorted({int(n) for n in raw if int(n) >= 1})
        except (TypeError, ValueError):
            raise InvalidInputError("slide_numbers must be a list of positive integers.")
        if not selected:
            raise InvalidInputError("slide_numbers must contain ≥1 positive integer.")
        if new_deck_pages is not None:
            too_big = [n for n in selected if n > new_deck_pages]
            if too_big:
                raise ValidationFailedError(
                    f"slide_numbers exceed new deck page count ({new_deck_pages}): {too_big}"
                )

    if mode == "replace":
        await db.execute(
            text("DELETE FROM slides WHERE session_id = CAST(:sid AS uuid)"),
            {"sid": session_id},
        )
    if mode == "replace_selected":
        await db.execute(
            text("DELETE FROM slides WHERE session_id = CAST(:sid AS uuid) "
                 "AND (slide_index + 1) = ANY(:nums)"),
            {"sid": session_id, "nums": selected},
        )

    inserted = (await db.execute(
        text("""
            INSERT INTO sources (session_id, role, filename, gcs_uri, content_type, size_bytes)
            VALUES (CAST(:sid AS uuid), 'slide', :fn, :uri, :ct, :sz)
            ON CONFLICT (gcs_uri) DO NOTHING
            RETURNING id
        """),
        {"sid": session_id, "fn": filename, "uri": gcs_uri,
         "ct": mime_type or "application/pdf", "sz": size_bytes or None},
    )).first()
    source_id = str(inserted[0]) if inserted else None
    await db.commit()

    dispatched_task = None
    try:
        from app.tasks.slide_extract import slide_extract_task
        slide_extract_task.delay(session_id)
        dispatched_task = "slide_extract_task"
    except Exception as e:
        logger.exception("add_slides: task dispatch failed for %s", session_id)
        raise InternalError(f"source committed but task dispatch failed: {e}")

    return {
        "source_id":             source_id,
        "gcs_uri":               gcs_uri,
        "mode":                  mode or ("append" if existing_decks else "first-add"),
        "dispatched_task":       dispatched_task,
        "new_deck_pages":        new_deck_pages,
        "selected_slide_numbers": selected if mode == "replace_selected" else None,
    }


# ─── POST /add/chat ────────────────────────────────────────────────────

async def _chat_existing_preview(db, session_id: str, limit: int = 10) -> list[dict]:
    rows = (await db.execute(
        text("""
            SELECT sent_at_ms, author, body FROM chat_messages
            WHERE session_id = CAST(:sid AS uuid)
            ORDER BY sent_at_ms LIMIT :n
        """),
        {"sid": session_id, "n": limit},
    )).mappings().all()
    return [
        {
            "timestamp": float((r["sent_at_ms"] or 0)) / 1000.0,
            "speaker":   (r["author"] or "")[:200],
            "message":   (r["body"] or "")[:200],
        }
        for r in rows
    ]


async def _chat_new_preview(gcs_uri: str, limit: int = 10, start_time: Optional[str] = None):
    txt = await _gcs_download_text(gcs_uri, encoding="utf-8")
    if txt is None:
        return [], 0
    from app.engines.chat_parser import parse_chat_file
    try:
        msgs = parse_chat_file(txt, start_time_override=start_time)
    except Exception:
        return [], 0
    preview = [
        {
            "timestamp": float(m.get("timestamp", 0.0) or 0.0),
            "speaker":   (m.get("speaker") or "")[:200],
            "message":   (m.get("message") or "")[:200],
        }
        for m in msgs[:limit]
    ]
    return preview, len(msgs)


@router.post("/{session_id}/add/chat")
async def add_chat(
    session_id: str,
    request: Request,
    db: DbSession,
    _u: CurrentUser,
    chat_file: Annotated[Optional[UploadFile], File()] = None,
    confirm: Annotated[Optional[bool], Query()] = None,
    start_time: Annotated[Optional[str], Query()] = None,
) -> dict:
    if await _require_session(db, session_id) is None:
        raise NotFoundError(f"Session {session_id} not found")

    gcs_uri, mime_type, filename, size_bytes = await _intake_upload(
        session_id, "chat", request, chat_file,
    )

    existing_cnt = (await db.execute(
        text("SELECT count(*) AS n FROM chat_messages WHERE session_id = CAST(:sid AS uuid)"),
        {"sid": session_id},
    )).mappings().first()["n"] or 0

    if existing_cnt > 0 and not confirm:
        current_preview = await _chat_existing_preview(db, session_id, limit=10)
        new_preview, new_count = await _chat_new_preview(gcs_uri, limit=10, start_time=start_time)
        raise ConflictError(
            message=f"Session already has {existing_cnt} chat message(s). Retry with ?confirm=true to replace.",
            details={
                "existing_count":  int(existing_cnt),
                "new_count":       int(new_count),
                "current_preview": current_preview,
                "new_preview":     new_preview,
                "gcs_uri":         gcs_uri,
                "new_filename":    filename,
            },
        )

    body_text = await _gcs_download_text(gcs_uri, encoding="utf-8")
    if body_text is None:
        raise NotFoundError("staging chat file could not be read from GCS")

    from app.engines.chat_parser import parse_chat_file
    try:
        messages = parse_chat_file(body_text, start_time_override=start_time)
    except Exception as e:
        logger.exception("add_chat: parse failed for %s", session_id)
        raise ValidationFailedError(f"chat parse failed: {e}")

    await db.execute(
        text("DELETE FROM chat_messages WHERE session_id = CAST(:sid AS uuid)"),
        {"sid": session_id},
    )
    for m in messages:
        await db.execute(
            text("""
                INSERT INTO chat_messages (session_id, author, body, sent_at_ms, placed)
                VALUES (CAST(:sid AS uuid), :a, :b, :ts, FALSE)
            """),
            {
                "sid": session_id,
                "a":   (m.get("speaker") or "")[:500],
                "b":   (m.get("message") or "")[:5000],
                "ts":  int(round((m.get("timestamp") or 0.0) * 1000)),
            },
        )

    await db.execute(
        text("""
            INSERT INTO sources (session_id, role, filename, gcs_uri, content_type, size_bytes)
            VALUES (CAST(:sid AS uuid), 'chat', :fn, :uri, :ct, :sz)
            ON CONFLICT (gcs_uri) DO NOTHING
        """),
        {"sid": session_id, "fn": filename, "uri": gcs_uri,
         "ct": mime_type or "text/plain", "sz": size_bytes or None},
    )
    await db.commit()

    return {
        "messages_written":  len(messages),
        "replaced_existing": int(existing_cnt),
        "gcs_uri":           gcs_uri,
    }


# ─── POST /add/manifest ────────────────────────────────────────────────

def _manifest_current_summary(sess: dict) -> dict:
    return {
        "code":             sess.get("code"),
        "title_long":       sess.get("title_long"),
        "title_short":      sess.get("title_short"),
        "ce_broker_id":     sess.get("ce_broker_id"),
        "class_id":         sess.get("class_id"),
        "tags":             list(sess.get("tags") or []),
        "publishing_links": dict(sess.get("publishing_links") or {}),
        "polls":            sess.get("polls"),
    }


def _manifest_parsed_summary(parsed) -> dict:
    return {
        "code":             parsed.code,
        "title_long":       parsed.title_long,
        "title_short":      parsed.title_short,
        "ce_broker_id":     parsed.ce_broker_id,
        "class_id":         parsed.class_id,
        "tags":             list(parsed.tags or []),
        "publishing_links": dict(parsed.publishing_links or {}),
        "polls":            parsed.polls,
        "speaker_count":    len(parsed.speakers or []),
        "resource_count":   len(parsed.slide_resources or []),
    }


@router.post("/{session_id}/add/manifest")
async def add_manifest(
    session_id: str,
    request: Request,
    db: DbSession,
    _u: CurrentUser,
    manifest_file: Annotated[Optional[UploadFile], File()] = None,
    mode: Annotated[Optional[str], Query()] = None,
) -> dict:
    sess = await _require_session(db, session_id)
    if sess is None:
        raise NotFoundError(f"Session {session_id} not found")

    gcs_uri, mime_type, filename, size_bytes = await _intake_upload(
        session_id, "manifest", request, manifest_file,
    )
    body_text = await _gcs_download_text(gcs_uri, encoding="utf-8")
    if body_text is None:
        raise NotFoundError("staging manifest file could not be read from GCS")

    from app.services.extras2_parser import parse_extras2
    try:
        parsed = parse_extras2(body_text)
    except Exception as e:
        logger.exception("add_manifest: parse failed for %s", session_id)
        raise ValidationFailedError(f"manifest parse failed: {e}")

    current_has_manifest = bool(sess.get("title_long"))

    if current_has_manifest and mode not in ("use_new", "keep_current"):
        raise ConflictError(
            message="Session already has a manifest. Retry with ?mode=use_new or ?mode=keep_current.",
            details={
                "current_summary": _manifest_current_summary(sess),
                "new_summary":     _manifest_parsed_summary(parsed),
                "gcs_uri":         gcs_uri,
                "new_filename":    filename,
            },
        )

    if mode == "keep_current":
        await _gcs_delete(gcs_uri)
        return {"session_updated": False, "mode": "keep_current"}

    if mode == "use_new":
        await db.execute(
            text("DELETE FROM session_slide_resources WHERE session_id = CAST(:sid AS uuid)"),
            {"sid": session_id},
        )
        await db.execute(
            text("DELETE FROM session_speakers WHERE session_id = CAST(:sid AS uuid)"),
            {"sid": session_id},
        )

    updates: list[str] = []
    params: dict = {"sid": session_id}
    if parsed.code:             updates.append("code = :code");                       params["code"] = parsed.code
    if parsed.title_long:       updates.append("title_long = :tl");                   params["tl"]   = parsed.title_long
    if parsed.title_short:      updates.append("title_short = :ts");                  params["ts"]   = parsed.title_short
    if parsed.ce_broker_id:     updates.append("ce_broker_id = :ce");                 params["ce"]   = parsed.ce_broker_id
    if parsed.class_id:         updates.append("class_id = :cl");                     params["cl"]   = parsed.class_id
    if parsed.tags:             updates.append("tags = CAST(:tg AS jsonb)");          params["tg"]   = json.dumps(parsed.tags)
    if parsed.publishing_links: updates.append("publishing_links = CAST(:pl AS jsonb)"); params["pl"]= json.dumps(parsed.publishing_links)
    if parsed.polls:            updates.append("polls_raw = :pr");                    params["pr"]   = parsed.polls
    if parsed.polls_parsed:     updates.append("polls_parsed = CAST(:pp AS jsonb)");  params["pp"]   = json.dumps(parsed.polls_parsed)

    if updates:
        await db.execute(
            text(f"UPDATE sessions SET {', '.join(updates)}, updated_at = now() WHERE id = CAST(:sid AS uuid)"),
            params,
        )

    speakers_written = 0
    for sp in parsed.speakers:
        await db.execute(
            text("""
                INSERT INTO session_speakers (session_id, role, name, credentials, bio, sort_order)
                VALUES (CAST(:sid AS uuid), :r, :n, :c, :b, :so)
            """),
            {"sid": session_id, "r": sp.role, "n": sp.name,
             "c": sp.credentials, "b": sp.bio, "so": sp.sort_order},
        )
        speakers_written += 1

    resources_written = 0
    for rs in parsed.slide_resources:
        await db.execute(
            text("""
                INSERT INTO session_slide_resources (session_id, slide_number, label, url, sort_order)
                VALUES (CAST(:sid AS uuid), :n, :l, :u, :so)
            """),
            {"sid": session_id, "n": rs.slide_number, "l": rs.label,
             "u": rs.url, "so": rs.sort_order},
        )
        resources_written += 1

    await db.execute(
        text("""
            INSERT INTO sources (session_id, role, filename, gcs_uri, content_type, size_bytes)
            VALUES (CAST(:sid AS uuid), 'manifest', :fn, :uri, :ct, :sz)
            ON CONFLICT (gcs_uri) DO NOTHING
        """),
        {"sid": session_id, "fn": filename, "uri": gcs_uri,
         "ct": mime_type or "text/plain", "sz": size_bytes or None},
    )
    await db.commit()

    return {
        "session_updated":   True,
        "mode":              mode or "first-add",
        "fields_updated":    [u.split(" = ")[0] for u in updates],
        "speakers_written":  speakers_written,
        "resources_written": resources_written,
    }
