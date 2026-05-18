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

    Celery ingest enqueue lands in Phase 6 / U37-U45. For now sessions stay
    in `status='ingesting'` and rows accumulate in `sources` for inspection.
    """
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
    return UploadCompleteResponse(session_id=payload.session_id, accepted=accepted)
