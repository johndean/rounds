"""
Rounds API entry point.

Phase 1 scaffold — only /v1/health is wired so CI + Railway healthchecks pass.
Domain routers (auth, sessions, gcs_upload, segments, slides, discrepancies,
sop, audit, improvements, settings, exports, diagnostics, ws) land in
Phases 5-7 per docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
from app.api import session_resources as session_resources_router
from app.api import sessions as sessions_router
from app.api import settings as settings_router
from app.api import sop as sop_router
from app.config import settings

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


_ws_manager = None
_ws_bridge_task = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _ws_manager, _ws_bridge_task

    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        creds_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS)
        if not creds_path.exists():
            print(
                f"[warn] GOOGLE_APPLICATION_CREDENTIALS={creds_path} does not exist. "
                "GCS / STT / Vertex AI calls will fail at request time.",
                flush=True,
            )

    # Start the WS bridge — subscribes to Redis pub/sub + fans out to clients.
    from app.engines.ws_bridge import WSManager, start_ws_bridge

    _ws_manager = WSManager()
    _ws_bridge_task = asyncio.create_task(start_ws_bridge(_ws_manager))
    try:
        yield
    finally:
        if _ws_bridge_task and not _ws_bridge_task.done():
            _ws_bridge_task.cancel()
            try:
                await _ws_bridge_task
            except asyncio.CancelledError:
                pass


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

# Idempotency middleware — replay-cached responses on Idempotency-Key header.
# Phase 6o / U139-U140.
from app.middleware.idempotency import IdempotencyMiddleware  # noqa: E402

app.add_middleware(IdempotencyMiddleware)


@app.get("/v1/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": app.version, "env": settings.ENVIRONMENT})


@app.websocket("/v1/ws/sessions/{session_id}")
async def session_ws(websocket: WebSocket, session_id: str):
    """Live session updates: processing_update, metrics_update, session_failed, etc."""
    if _ws_manager is None:
        await websocket.close(code=1011)
        return
    await _ws_manager.connect(session_id, websocket)
    try:
        while True:
            # Keep-alive — client may send pings; we ignore content.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await _ws_manager.disconnect(session_id, websocket)


# ─── Sub-routers ────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(gcs_router.router)
app.include_router(sessions_router.router)
app.include_router(session_resources_router.router)
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
