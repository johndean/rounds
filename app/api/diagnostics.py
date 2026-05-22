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


class RealignResult(BaseModel):
    session_id: str
    enqueued:   bool
    detail:     str | None = None


@router.post("/realign/{session_id}", response_model=RealignResult)
async def realign(session_id: str, _db: DbSession, _u: CurrentUser) -> RealignResult:
    """
    Manually re-trigger lcs_discrepancies_task for an already-ready session
    so it can populate the word_alignment table (migration 036 was added
    after some sessions had finished STT + LCS, so they have discrepancies
    but no alignment rows). lcs_discrepancies_task itself is idempotent:
    if discrepancies already exist it preserves them; it only fills in the
    missing alignment data.
    """
    enqueued = False
    detail: str | None = None
    try:
        from app.tasks.lcs_discrepancies import lcs_discrepancies_task

        lcs_discrepancies_task.apply_async(args=[session_id], queue="celery")
        enqueued = True
    except Exception as exc:  # noqa: BLE001
        detail = f"{exc.__class__.__name__}: {exc}"
    return RealignResult(session_id=session_id, enqueued=enqueued, detail=detail)


class InitStagesResult(BaseModel):
    session_id:  str
    type_id:     str | None
    stages:      int
    detail:      str | None = None


@router.post("/init-session-stages/{session_id}", response_model=InitStagesResult)
async def init_session_stages_diag(
    session_id: str,
    _db:        DbSession,
    _u:         CurrentUser,
    type_id:    str | None = None,
) -> InitStagesResult:
    """
    Manually fire session_stage_assignees init for a session. Useful for
    sessions ingested before the auto-init hook was wired (Unit 6) or
    when an operator changes the session's Type and wants the new
    matrix's defaults populated.

    Pass `?type_id=<uuid>` to force a specific Type; omit to use the
    session's existing session_type_id, falling back to the org default.
    Idempotent — only writes stages that don't already have an assignee.
    """
    from sqlalchemy import create_engine

    from app.config import settings
    from app.services.session_init import init_session_stages

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        stages = init_session_stages(engine, session_id, type_id=type_id, actor="diag/init-session-stages")
        return InitStagesResult(session_id=session_id, type_id=type_id, stages=stages)
    except Exception as exc:  # noqa: BLE001
        return InitStagesResult(
            session_id=session_id, type_id=type_id, stages=0,
            detail=f"{exc.__class__.__name__}: {exc}",
        )
    finally:
        engine.dispose()


class AutoplacePollsResult(BaseModel):
    session_id: str
    placed:     int
    detail:     str | None = None


@router.post("/autoplace-polls/{session_id}", response_model=AutoplacePollsResult)
async def autoplace_polls(session_id: str, _db: DbSession, _u: CurrentUser) -> AutoplacePollsResult:
    """
    Manually fire poll auto-placement for an already-ingested session.

    Useful for backfilling sessions that completed ingest before the
    auto-placement service was wired in, or for re-running after the
    operator has manually cleared anchors and wants the defaults back.

    Idempotent — only places polls with anchor_segment IS NULL.
    """
    from sqlalchemy import create_engine

    from app.config import settings
    from app.services.poll_autoplace import auto_place_polls

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        placed = auto_place_polls(engine, session_id)
        return AutoplacePollsResult(session_id=session_id, placed=placed)
    except Exception as exc:  # noqa: BLE001
        return AutoplacePollsResult(
            session_id=session_id, placed=0,
            detail=f"{exc.__class__.__name__}: {exc}",
        )
    finally:
        engine.dispose()


class ClearSlotsResult(BaseModel):
    email: str
    removed_count: int
    removed_session_ids: list[str]
    cap: int
    remaining: int


@router.post("/clear-rate-limit-slots", response_model=ClearSlotsResult)
async def clear_rate_limit_slots(db: DbSession, _u: CurrentUser) -> ClearSlotsResult:
    """
    Sweep the Redis active-sessions set for the calling user and remove any
    slot whose session_id is soft-deleted (or no longer exists) in the DB.
    Unblocks operators who hit 429 RATE_LIMIT_USER after a create+delete
    cycle that didn't release slots (regression from older DELETE handler
    that didn't call release_slot — now fixed, this endpoint cleans up
    pre-fix leakage).

    Idempotent. Slots for live sessions (deleted_at IS NULL) are preserved.
    """
    import redis as _redis
    r = _redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        key = f"sessions:active:{_u.email}"
        ids = list(r.smembers(key))
        removed: list[str] = []
        for sid in ids:
            row = (
                await db.execute(
                    text("SELECT deleted_at FROM sessions WHERE id = CAST(:sid AS uuid)"),
                    {"sid": sid},
                )
            ).fetchone()
            should_release = (row is None) or (row[0] is not None)
            if should_release:
                r.srem(key, sid)
                r.lrem("sessions:queue", 0, sid)
                removed.append(sid)
        remaining = r.scard(key)
        return ClearSlotsResult(
            email=_u.email,
            removed_count=len(removed),
            removed_session_ids=removed,
            cap=settings.MAX_CONCURRENT_SESSIONS,
            remaining=int(remaining or 0),
        )
    finally:
        r.close()


@router.post("/sop-check")
async def sop_deadline_check(_u: CurrentUser) -> dict:
    """
    Run sop_check_deadlines_task synchronously and return the result.
    Useful for operator/admin to spot-check overdue stages without waiting
    for the next Celery Beat tick.
    """
    try:
        from app.tasks.sop_tasks import sop_check_deadlines_task

        # .run() executes inline rather than enqueueing. RoundsTask base
        # is fine — no self.request access on the inline call path.
        result = sop_check_deadlines_task.apply().get(timeout=60)
        return {"ok": True, **(result or {})}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}


class FlushQueueResult(BaseModel):
    purged:     int
    per_worker: dict | None = None
    detail:     str | None = None


@router.post("/flush-celery-queue", response_model=FlushQueueResult)
async def flush_celery_queue(_u: CurrentUser) -> FlushQueueResult:
    """
    Drain ALL pending messages from the Celery broker queue. Use this
    after an operator mistake stacks redundant tasks that need to be
    discarded en masse (e.g. a reingest stampede).

    Mechanics: calls celery_app.control.purge(), which removes queued-but-
    not-yet-started messages from the broker. Currently-running tasks
    finish (Celery has no way to revoke a task mid-execution from the
    broker side — only the worker can cancel its own current task).

    Scope: this purges the entire Rounds Celery queue. There is no
    per-session filter because Celery doesn't index queue messages by
    args. Pair with /v1/diag/abort-session/{id} to also break the
    target session out of 'uploading' so the user can retry cleanly.
    """
    try:
        from app.tasks.celery_app import celery_app

        # control.purge() returns a dict[worker_hostname, count] under
        # normal operation, an int in some configurations, or None if
        # no workers respond. Normalize.
        raw = celery_app.control.purge()
        if isinstance(raw, dict):
            total = sum(int(v or 0) for v in raw.values())
            return FlushQueueResult(purged=total, per_worker=raw)
        if isinstance(raw, int):
            return FlushQueueResult(purged=raw)
        if raw is None:
            return FlushQueueResult(purged=0, detail="no workers responded — queue may still hold messages")
        return FlushQueueResult(purged=0, detail=f"unexpected purge() result type: {type(raw).__name__}")
    except Exception as exc:  # noqa: BLE001
        return FlushQueueResult(purged=0, detail=f"{exc.__class__.__name__}: {exc}")


class AbortSessionResult(BaseModel):
    session_id:    str
    status_before: str
    status_after:  str
    detail:        str | None = None


@router.post("/abort-session/{session_id}", response_model=AbortSessionResult)
async def abort_session(
    session_id: str, db: DbSession, _u: CurrentUser,
) -> AbortSessionResult:
    """
    Force a session into 'failed' status, bypassing the state machine.

    Companion to /flush-celery-queue: after draining the broker, this
    breaks the target session out of 'uploading' so the operator can
    retry cleanly without the UI looping on "Preparing files".

    Bypasses ALLOWED_TRANSITIONS (same escape-hatch pattern reingest
    uses). Appends an audit log entry so the post-mortem is traceable.
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

    if status_before == "failed":
        return AbortSessionResult(
            session_id=session_id, status_before=status_before,
            status_after=status_before, detail="already failed — no-op",
        )

    await db.execute(
        text(
            """
            UPDATE sessions SET status = 'failed', updated_at = now()
             WHERE id = CAST(:sid AS uuid)
            """
        ),
        {"sid": session_id},
    )

    import json as _json
    from datetime import datetime, timezone
    entry = {
        "ts":     datetime.now(timezone.utc).isoformat(),
        "prev":   status_before,
        "next":   "failed",
        "actor":  "diag/abort-session",
        "reason": "operator abort (queue flush companion)",
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

    # Also publish a session_failed WS event so any open SessionDetail /
    # ProcessingView tabs flip out of the "Preparing files" loop without
    # a manual refresh.
    try:
        from app.engines.ws_bridge import publish_ws_event_sync
        publish_ws_event_sync(session_id, {
            "type":         "session_failed",
            "category":     "operator_abort",
            "user_message": "Session aborted by operator. Reingest or delete to retry.",
            "reason":       "diag/abort-session",
        })
    except Exception:  # noqa: BLE001
        pass

    return AbortSessionResult(
        session_id=session_id, status_before=status_before, status_after="failed",
    )


class ReseedAuthUsersResult(BaseModel):
    seeded:        int    # rows inserted by THIS call (0 if table already had rows)
    total:         int    # row count in auth_users AFTER the call
    skipped_count: int    # AUTH_USERS env entries that didn't make it (bcrypt errors, etc.)


@router.post("/reseed-auth-users", response_model=ReseedAuthUsersResult)
async def reseed_auth_users(db: DbSession, user: CurrentUser) -> ReseedAuthUsersResult:
    """
    Admin-only escape hatch — re-run the boot-time AUTH_USERS env seed
    against the live DB. Idempotent via the existing count-short-circuit
    inside seed_from_env_if_empty: if auth_users already has rows, the
    call returns 0 seeded with no writes.

    Use after a seed failure left the table empty (e.g. a long password
    tripped bcrypt 4.x's hard 72-byte limit before the per-row try/except
    was in place). Calling this avoids needing a redeploy to trigger the
    lifespan hook again.
    """
    if not hasattr(user, "email") or user.email != "johndean@vin.com":
        raise HTTPException(
            status_code=403,
            detail={"code": "ADMIN_ONLY", "message": "admin only"},
        )

    from sqlalchemy import create_engine

    from app.auth import _parse_auth_users
    from app.config import settings as _s
    from app.services.auth_users import seed_from_env_if_empty

    sync_url = _s.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        before_row = await db.execute(text("SELECT count(*) FROM auth_users"))
        before = int(before_row.scalar() or 0)

        seeded = seed_from_env_if_empty(engine, _s.AUTH_USERS)

        after_row = await db.execute(text("SELECT count(*) FROM auth_users"))
        after = int(after_row.scalar() or 0)

        # Audit so the ledger has a record of every manual reseed.
        await db.execute(
            text(
                "INSERT INTO audit_events (actor_email, kind, summary) "
                "VALUES (:a, 'diag.reseed_auth_users', :s)"
            ),
            {"a": user.email, "s": f"before={before} seeded={seeded} after={after}"},
        )
        await db.commit()

        env_entries = len(_parse_auth_users(_s.AUTH_USERS or ""))
        # If env had N parseable rows and we only end up with M total, the
        # delta is what bcrypt or constraints rejected. Non-negative clamp
        # covers the case where the table had pre-existing rows.
        skipped = max(0, env_entries - after)
        return ReseedAuthUsersResult(seeded=seeded, total=after, skipped_count=skipped)
    finally:
        engine.dispose()
