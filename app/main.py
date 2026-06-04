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

from app.api import add_to_session as add_to_session_router
from app.api import audit as audit_router
from app.api import auth as auth_router
from app.api import corrections as corrections_router
from app.api import diagnostics as diag_router
from app.api import email_debug as email_debug_router
from app.api import email_templates as email_templates_router
from app.api import discrepancies as disc_router
from app.api import exports as exports_router
from app.api import gcs_upload as gcs_router
from app.api import improvements as improvements_router
from app.api import segments as segments_router
from app.api import session_resources as session_resources_router
from app.api import sessions as sessions_router
from app.api import settings as settings_router
from app.api import sop as sop_router
from app.api import word_alignment as word_alignment_router
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

    # Seed auth_users from the AUTH_USERS env var on first boot. Idempotent:
    # the row-count short-circuit makes every subsequent boot a ~0.3ms no-op.
    # If the seed fails (DB unreachable mid-deploy, schema not migrated yet),
    # we log and continue — login will start working once the table exists.
    try:
        from sqlalchemy import create_engine

        from app.services.auth_users import seed_from_env_if_empty

        _sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        _seed_engine = create_engine(_sync_url)
        try:
            seeded = seed_from_env_if_empty(_seed_engine, settings.AUTH_USERS)
            if seeded > 0:
                print(f"[boot] seeded {seeded} auth_users rows from AUTH_USERS env", flush=True)
        finally:
            _seed_engine.dispose()
    except Exception as exc:  # noqa: BLE001
        print(f"[boot] auth_users seed skipped: {exc}", flush=True)

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

# Response envelope middleware — wraps every JSON response in
# {success, data, error, meta} (MIC §9.1 locked invariant).
# Mounted BELOW request_id so envelope.meta.request_id can read it.
# Phase 7i / parity-3.
#
# The middleware catches MICException directly inside dispatch(), so a
# separate @app.exception_handler(MICException) would be unreachable —
# we don't register one.
from app.middleware.envelope import EnvelopeMiddleware  # noqa: E402

app.add_middleware(EnvelopeMiddleware)


# Request-ID middleware — outermost so x-request-id appears on every response.
# Phase 7h.
from app.middleware.request_id import RequestIdMiddleware  # noqa: E402

app.add_middleware(RequestIdMiddleware)


@app.api_route("/v1/health", methods=["GET", "HEAD"])
async def health() -> JSONResponse:
    """Healthcheck — supports HEAD for load-balancer probes that don't want a body."""
    return JSONResponse({"status": "ok", "version": app.version, "env": settings.ENVIRONMENT})


@app.get("/v1/version")
async def version() -> JSONResponse:
    """
    Build identity. Frontend AppHeader fetches this on mount and compares
    against its baked-in VITE_BUILD_SHA — when they diverge the chip turns
    amber + prompts a refresh. That eliminates the "am I looking at a 14-hour-old
    bundle?" guessing whenever a deploy goes out.

    `commit` is the git SHA baked into the runtime image by the Dockerfile
    ARG RAILWAY_GIT_COMMIT_SHA. Defaults to 'dev' when not built via Railway.
    No auth: monitoring + DevTools probes shouldn't need a JWT to confirm
    which build they're hitting.
    """
    import os
    commit = os.environ.get("ROUNDS_COMMIT_SHA") or "dev"
    return JSONResponse({
        "commit":      commit,
        "commit_short": commit[:7],
        "env":         settings.ENVIRONMENT,
    })


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
app.include_router(add_to_session_router.router)
app.include_router(session_resources_router.router)
app.include_router(corrections_router.router)
app.include_router(segments_router.router)
app.include_router(disc_router.router)
app.include_router(word_alignment_router.router)
app.include_router(sop_router.router)
app.include_router(sop_router.global_router)
app.include_router(audit_router.router)
app.include_router(improvements_router.router)
app.include_router(settings_router.router)
app.include_router(diag_router.router)
app.include_router(email_debug_router.router)
app.include_router(email_templates_router.router)
app.include_router(exports_router.router)


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
    async def spa_fallback(path: str) -> FileResponse:
        # Serve a real file when it exists in dist (e.g. prototype.html,
        # upload-test.html, favicon.svg, fonts/*). Otherwise fall through to
        # index.html so the Vue router can handle the route client-side.
        candidate = (_FRONTEND_DIST / path).resolve()
        try:
            candidate.relative_to(_FRONTEND_DIST.resolve())
        except ValueError:
            # Path-traversal guard — refuse anything outside dist.
            return FileResponse(_FRONTEND_DIST / "index.html")
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
