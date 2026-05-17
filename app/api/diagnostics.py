"""
/v1/diag — diagnostic endpoints (GCS QA, classify-route, SMTP test).
Settings → Diagnostics drill-in (IMPLEMENTATION.md §10).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth import CurrentUser
from app.config import settings

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
