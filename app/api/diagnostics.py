"""
/v1/diag — diagnostic endpoints (GCS QA, classify-route, SMTP test).
Settings → Diagnostics drill-in (IMPLEMENTATION.md §10).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import CurrentUser
from app.config import settings
from app.db import DbSession

router = APIRouter(prefix="/v1/diag", tags=["diagnostics"])


class GcsCheckResult(BaseModel):
    project_id: str
    bucket: str
    credentials_loaded: bool
    bucket_reachable: bool
    detail: str | None = None


@router.get("/gcs", response_model=GcsCheckResult)
async def gcs_check(_u: CurrentUser) -> GcsCheckResult:
    """Lightweight GCS QA — verifies project / bucket / credentials line up."""
    creds_loaded = False
    reachable = False
    detail: str | None = None
    try:
        from google.cloud import storage as gcs_lib  # type: ignore
        client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
        creds_loaded = True
        bucket = client.bucket(settings.GCS_BUCKET)
        bucket.reload()  # raises if bucket doesn't exist / no access
        reachable = True
    except Exception as exc:
        detail = f"{exc.__class__.__name__}: {exc}"
    return GcsCheckResult(
        project_id=settings.GCP_PROJECT_ID,
        bucket=settings.GCS_BUCKET,
        credentials_loaded=creds_loaded,
        bucket_reachable=reachable,
        detail=detail,
    )


class ClassifyRouteResult(BaseModel):
    backend: str
    model_id: str
    healthy: bool
    detail: str | None = None


@router.get("/classify-route", response_model=ClassifyRouteResult)
async def classify_route(_u: CurrentUser) -> ClassifyRouteResult:
    """Reports which classification backend is enabled + which model."""
    backend = "vertex_ai" if settings.VERTEX_AI_CLASSIFY_ENABLED else "gemini_dev"
    detail = None
    healthy = False
    if backend == "gemini_dev":
        if not settings.GEMINI_API_KEY:
            detail = "GEMINI_API_KEY not set"
        else:
            healthy = True
    else:
        if not settings.GOOGLE_APPLICATION_CREDENTIALS:
            detail = "GOOGLE_APPLICATION_CREDENTIALS not set for Vertex AI"
        else:
            healthy = True
    return ClassifyRouteResult(
        backend=backend, model_id=settings.GEMINI_CLASSIFY_MODEL, healthy=healthy, detail=detail,
    )


class ReingestResult(BaseModel):
    session_id: str
    status_before: str
    enqueued: bool
    detail: str | None = None


@router.post("/reingest/{session_id}", response_model=ReingestResult)
async def reingest(session_id: str, db: DbSession, _u: CurrentUser) -> ReingestResult:
    """
    Re-trigger the ingest pipeline for a session. Resets status to
    'ingesting' (a no-op if it's already there) and enqueues ingest_task.

    Useful when a session was uploaded before the worker was up, or when
    transcribe failed transiently and the operator wants to retry without
    re-uploading the source.
    """
    row = (
        await db.execute(
            text("SELECT status FROM sessions WHERE id = CAST(:sid AS uuid)"),
            {"sid": session_id},
        )
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    status_before = row[0]

    # Reingest is the one explicit operator escape — bypass the state
    # machine since `failed`/`ready` are terminal but reingest is exactly
    # the operation that should be able to push them back to `uploading`.
    await db.execute(
        text(
            """
            UPDATE sessions SET status = 'uploading', updated_at = now()
             WHERE id = CAST(:sid AS uuid)
            """
        ),
        {"sid": session_id},
    )
    # Wipe prior segments so transcribe doesn't no-op via its
    # check-before-execute guard.
    await db.execute(
        text("DELETE FROM segments WHERE session_id = CAST(:sid AS uuid)"),
        {"sid": session_id},
    )
    # Append an audit log entry documenting the reingest reset.
    import json as _json
    from datetime import datetime, timezone
    entry = {
        "ts":     datetime.now(timezone.utc).isoformat(),
        "prev":   status_before,
        "next":   "uploading",
        "actor":  "diag/reingest",
        "reason": "operator reset",
    }
    await db.execute(
        text(
            """
            INSERT INTO session_audit (session_id, processing_log)
            VALUES (CAST(:sid AS uuid), CAST(:e AS jsonb))
            ON CONFLICT (session_id) DO UPDATE
              SET processing_log = session_audit.processing_log || EXCLUDED.processing_log,
                  updated_at = now()
            """
        ),
        {"sid": session_id, "e": _json.dumps([entry])},
    )
    await db.commit()

    enqueued = False
    detail: str | None = None
    try:
        from app.tasks.ingest import enqueue_ingest

        enqueue_ingest(session_id)
        enqueued = True
    except Exception as exc:  # noqa: BLE001
        detail = f"{exc.__class__.__name__}: {exc}"

    return ReingestResult(
        session_id=session_id,
        status_before=status_before,
        enqueued=enqueued,
        detail=detail,
    )
