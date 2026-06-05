"""
/v1/sessions/{id}/exports/{format} — produces docx / srt / vtt / txt / zip.
/v1/sessions/{id}/captions.vtt    — cache-friendly WebVTT for HTML5 <track>.

Streams the artifact bytes back; writes a row in the artifacts table when
generated successfully (idempotent via UNIQUE (session_id, kind)).

Phase 6p / U142. Phase C1 (2026-06-05) adds the captions.vtt route with
ETag + Cache-Control so the editor's <track> tag doesn't re-fetch every
mount; the ETag fingerprints (session_id, max corrections.sequence_number)
so the cache invalidates the moment any correction lands.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/sessions/{session_id}/exports", tags=["exports"])
captions_router = APIRouter(prefix="/v1/sessions/{session_id}", tags=["exports"])


_KIND_TO_MIME = {
    "txt":  "text/plain; charset=utf-8",
    "srt":  "application/x-subrip; charset=utf-8",
    "vtt":  "text/vtt; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "html": "text/html; charset=utf-8",
    "zip":  "application/zip",
}


@router.get("/{format}")
async def export_session(
    session_id: UUID,
    format: str,
    db: DbSession,
    user: CurrentUser,
) -> Response:
    fmt = format.lower()
    if fmt not in _KIND_TO_MIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FORMAT", "supported": list(_KIND_TO_MIME.keys())},
        )

    from app.engines.artifact_transformer import (
        load_session_for_export,
        to_cms_html,
        to_docx,
        to_srt,
        to_txt,
        to_vtt,
        to_zip,
    )

    try:
        sess = load_session_for_export(str(session_id))
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if fmt == "txt":
        body = to_txt(sess)
    elif fmt == "srt":
        body = to_srt(sess)
    elif fmt == "vtt":
        body = to_vtt(sess)
    elif fmt == "docx":
        body = to_docx(sess)
    elif fmt == "html":
        body = to_cms_html(sess)
    else:
        body = to_zip(sess)

    # Record artifact metadata (best-effort).
    try:
        await db.execute(
            text(
                """
                INSERT INTO artifacts (session_id, kind, bytes, generated_by)
                VALUES (CAST(:sid AS uuid), :k, :b, :u)
                ON CONFLICT (session_id, kind) DO UPDATE
                  SET bytes = EXCLUDED.bytes,
                      generated_by = EXCLUDED.generated_by,
                      generated_at = now()
                """
            ),
            {"sid": str(session_id), "k": fmt, "b": len(body), "u": user.email},
        )
        await db.commit()
    except Exception:  # noqa: BLE001
        # Schema not migrated yet, or transient DB error — non-fatal.
        await db.rollback()

    filename = f"{sess.code}.{fmt}"
    return Response(
        content=body,
        media_type=_KIND_TO_MIME[fmt],
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


# ─── /captions.vtt — Phase C1 ─────────────────────────────────────────
# Dedicated route for the HTML5 <track> element. The editor fetches this
# via authenticated fetch() and wraps the body in a Blob URL, which
# sidesteps <track>'s inability to send Authorization headers. The ETag
# is the load-bearing perf bit: it fingerprints (session_id, latest
# correction sequence_number), so the browser sends If-None-Match on
# every reload and the server returns 304 (zero body bytes) until a new
# correction lands. Cache-Control: private, max-age=60 also lets the
# browser skip the network entirely for the first minute.
@captions_router.get("/captions.vtt")
async def get_captions_vtt(
    session_id: UUID,
    request: Request,
    db: DbSession,
    _user: CurrentUser,
) -> Response:
    """WebVTT captions for the video <track>. ETag-cached on the
    (session_id, max_correction_seq) pair."""
    # Compute the ETag fingerprint from the corrections ledger BEFORE
    # materializing the body. If the client's If-None-Match matches,
    # return 304 with no body — the entire VTT generation is skipped.
    row = (
        await db.execute(
            text(
                "SELECT COALESCE(MAX(sequence_number), -1) AS max_seq "
                "FROM corrections WHERE session_id = CAST(:sid AS uuid)"
            ),
            {"sid": str(session_id)},
        )
    ).mappings().first()
    max_seq = int(row["max_seq"]) if row else -1
    etag = f'W/"{session_id}-{max_seq}"'

    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=304,
            headers={
                "ETag": etag,
                "Cache-Control": "private, max-age=60",
            },
        )

    from app.engines.artifact_transformer import load_session_for_export, to_vtt
    try:
        sess = load_session_for_export(str(session_id))
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))

    body = to_vtt(sess)
    return Response(
        content=body,
        media_type="text/vtt; charset=utf-8",
        headers={
            "ETag": etag,
            "Cache-Control": "private, max-age=60",
            # Inline disposition so the browser plays this in <track>
            # rather than offering it as a download.
            "Content-Disposition": "inline",
        },
    )
