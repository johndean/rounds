"""
Background watchdog for stuck-on-uploading sessions.

Closes the silent-enqueue-failure gap at /v1/gcs/upload-complete:197-200
without touching that handler. Runs every UPLOAD_WATCHDOG_INTERVAL_SEC
via Celery Beat (embedded into the worker via the `-B` flag in
scripts/start.sh). Finds sessions that have been status='uploading'
longer than UPLOAD_STUCK_THRESHOLD_SEC AND have at least one source row
with role in ('audio', 'video') — that combo proves /upload-complete
already ran (sources persisted) but ingest_task never started.

Recovery: calls the existing enqueue_ingest() — identical to what the
/v1/diag/reingest operator endpoint already does. ingest_task itself
has check-before-execute guards (status check, existing-segments check)
that make re-enqueue idempotent.

Feature-flag: UPLOAD_WATCHDOG_ENABLED=False by default. When false the
task returns in ~1ms with {"disabled": True}. Flip the env var in
Railway worker service + restart worker to activate. Same to disable
(no code change required).

Per the 2026-05-25 constraints in lets-start-a-new-streamed-creek.md:
this is a NEW file, does NOT touch any C1-locked file (gcs_upload.py,
ingest.py, ai_process.py, transcribe.py, normalize.py, align.py,
fusion.py, classify_task.py, finalize.py, anchor_task.py, frame_task.py,
slide_extract.py, lcs_discrepancies.py, burn_captions.py, kp_task.py).

Related ADRs: ADR-006 (Celery Beat scheduler).
Related business rules: BR-014 (upload-stuck threshold).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from app.config import settings
from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.upload_watchdog",
    max_retries=0,  # one-shot per beat tick — failures don't requeue, next tick retries
)
def upload_watchdog_task(self) -> dict:  # noqa: ARG001
    """
    Scan for stuck 'uploading' sessions and re-enqueue ingest_task.

    Match criteria (all must hold):
      - sessions.status = 'uploading'
      - sessions.updated_at < now - UPLOAD_STUCK_THRESHOLD_SEC
      - EXISTS a sources row for the session with role in ('audio','video')
        — proves /upload-complete ran and persisted sources (so this is
          not a "user is mid-PUT" false positive)
      - NO recent session_audit entry tagged actor='upload_watchdog'
        within UPLOAD_WATCHDOG_COOLDOWN_SEC — avoids retry storms on
        a session whose broker outage is sustained

    LIMIT 50 per tick keeps any one scan bounded if there's a backlog.
    """
    if not settings.UPLOAD_WATCHDOG_ENABLED:
        return {"disabled": True}

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            stuck = conn.execute(
                text(
                    """
                    SELECT s.id::text
                      FROM sessions s
                     WHERE s.status = 'uploading'
                       AND s.updated_at < (now() - (:thr || ' seconds')::interval)
                       AND EXISTS (
                           SELECT 1 FROM sources src
                            WHERE src.session_id = s.id
                              AND src.role IN ('audio', 'video')
                       )
                       AND NOT EXISTS (
                           SELECT 1 FROM session_audit sa
                            WHERE sa.session_id = s.id
                              AND sa.updated_at > (now() - (:cooldown || ' seconds')::interval)
                              AND sa.processing_log::text LIKE '%upload_watchdog%'
                       )
                     LIMIT 50
                    """
                ),
                {
                    "thr":      str(settings.UPLOAD_STUCK_THRESHOLD_SEC),
                    "cooldown": str(settings.UPLOAD_WATCHDOG_COOLDOWN_SEC),
                },
            ).fetchall()

        recovered = 0
        re_enqueue_failures: list[str] = []

        for (sid,) in stuck:
            try:
                # Same enqueue_ingest the /v1/diag/reingest endpoint uses.
                # Lazy import so the upload_watchdog module can be loaded
                # at startup even if ingest.py has a transient import issue.
                from app.tasks.ingest import enqueue_ingest

                enqueue_ingest(sid)
                _log_audit(engine, sid, "watchdog re-enqueued ingest_task")
                recovered += 1
                logger.info(f"upload_watchdog: re-enqueued ingest for session={sid}")
            except Exception as exc:  # noqa: BLE001
                re_enqueue_failures.append(f"{sid}: {exc.__class__.__name__}")
                logger.warning(
                    f"upload_watchdog: re-enqueue failed for session={sid}: "
                    f"{exc.__class__.__name__}: {exc}"
                )

        result: dict = {
            "scanned":   len(stuck),
            "recovered": recovered,
        }
        if re_enqueue_failures:
            result["failures"] = re_enqueue_failures
        return result

    finally:
        engine.dispose()


def _log_audit(engine, session_id: str, reason: str) -> None:
    """Write a session_audit entry tagged 'upload_watchdog' for traceability.

    Mirrors the JSONB append pattern from app/api/diagnostics.py:133-144
    (reingest's audit write) so the schema is identical and the cooldown
    SELECT in upload_watchdog_task can match on the actor tag.
    """
    entry = {
        "ts":     datetime.now(timezone.utc).isoformat(),
        "actor":  "upload_watchdog",
        "reason": reason,
    }
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO session_audit (session_id, processing_log)
                VALUES (CAST(:sid AS uuid), CAST(:e AS jsonb))
                ON CONFLICT (session_id) DO UPDATE
                  SET processing_log = session_audit.processing_log || EXCLUDED.processing_log,
                      updated_at = now()
                """
            ),
            {"sid": session_id, "e": json.dumps([entry])},
        )
