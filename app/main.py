"""
Rounds API entry point.

Phase 1 scaffold — only /v1/health is wired so CI + Railway healthchecks pass.
Domain routers (auth, sessions, gcs_upload, segments, slides, discrepancies,
sop, audit, improvements, settings, exports, diagnostics, ws) land in
Phases 5-7 per docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import audit as audit_router
from app.api import auth as auth_router
from app.api import diagnostics as diag_router
from app.api import discrepancies as disc_router
from app.api import gcs_upload as gcs_router
from app.api import improvements as improvements_router
from app.api import segments as segments_router
from app.api import sessions as sessions_router
from app.api import settings as settings_router
from app.api import sop as sop_router
from app.config import settings

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup-time sanity checks (audit §10 finding #3 — fail fast on missing creds)
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        creds_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS)
        if not creds_path.exists():
            # Warn loudly but don't crash on dev — production deploy will set GCP_KEY_B64
            # which scripts/start.sh decodes before this lifespan runs.
            print(
                f"[warn] GOOGLE_APPLICATION_CREDENTIALS={creds_path} does not exist. "
                "GCS / STT / Vertex AI calls will fail at request time.",
                flush=True,
            )
    yield


app = FastAPI(
    title="Rounds API",
    version="0.0.1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rounds.vin",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/v1/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": app.version, "env": settings.ENVIRONMENT})


# ─── Sub-routers ────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(gcs_router.router)
app.include_router(sessions_router.router)
app.include_router(segments_router.router)
app.include_router(disc_router.router)
app.include_router(sop_router.router)
app.include_router(audit_router.router)
app.include_router(improvements_router.router)
app.include_router(settings_router.router)
app.include_router(diag_router.router)


# ── Static frontend (production) ─────────────────────────────────────────
# Railway: Dockerfile builds frontend/dist and copies it in; mount as SPA fallback.
if _FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(_FRONTEND_DIST / "index.html")

    @app.get("/{path:path}")
    async def spa_fallback(path: str) -> FileResponse:  # noqa: ARG001
        return FileResponse(_FRONTEND_DIST / "index.html")
