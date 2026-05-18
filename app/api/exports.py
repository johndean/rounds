"""
/v1/sessions/{id}/exports/{format} — produces docx / srt / vtt / txt / zip.

Streams the artifact bytes back; writes a row in the artifacts table when
generated successfully (idempotent via UNIQUE (session_id, kind)).

Phase 6p / U142.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/sessions/{session_id}/exports", tags=["exports"])


_KIND_TO_MIME = {
    "txt":  "text/plain; charset=utf-8",
    "srt":  "application/x-subrip; charset=utf-8",
    "vtt":  "text/vtt; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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
