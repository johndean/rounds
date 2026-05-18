"""
Ingest orchestrator — drives a session from `ingesting` → `ready`.

Flow:
  /v1/gcs/upload-complete  → enqueue ingest_task(session_id)
  ingest_task
    ├─ check-before-execute: skip if status != 'ingesting'
    ├─ enqueue transcribe_task (writes segments)
    ├─ enqueue slide_extract_task (writes slides rows + thumbnails)
    └─ chain finalize_task to run after both prerequisites land

  finalize_task
    ├─ run align_task (assigns slides to segments)
    └─ mark session 'ready'

This is the lean v1 path. Frame sampling (FRAME_SAMPLE_FPS=2 visual
change detection) and AI MODE (Gemini direct-to-LLM transcript
reconciliation) are downstream enhancements that hang off the same
orchestrator without changing the externally observable contract.
"""
from __future__ import annotations

import logging

from celery import chain

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.ingest",
    max_retries=2,
)
def ingest_task(self, session_id: str) -> dict:  # noqa: ARG001
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.tasks.finalize import finalize_task
    from app.tasks.slide_extract import slide_extract_task
    from app.tasks.transcribe import transcribe_task

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    from app.engines.state_machine import ConflictError, transition_session_sync

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT status FROM sessions WHERE id = CAST(:sid AS uuid)"),
                {"sid": session_id},
            ).fetchone()
        if not row:
            logger.warning(f"ingest: session {session_id} not found")
            return {"skipped": True, "reason": "not_found"}
        if row[0] != "uploading":
            logger.info(f"ingest: skip — session {session_id} status={row[0]}")
            return {"skipped": True, "reason": f"status={row[0]}"}

        # uploading → transcribing happens here so the audit log records the
        # entry into the pipeline. Failure to transition (e.g. terminal state)
        # raises and aborts ingest.
        transition_session_sync(session_id, "transcribing", actor="ingest_task")

        with engine.connect() as conn:
            slide_src_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM sources
                     WHERE session_id = CAST(:sid AS uuid)
                       AND role = 'slide'
                    """
                ),
                {"sid": session_id},
            ).scalar() or 0

        # Run transcribe + slide_extract in parallel, then finalize
        # (align + mark ready). Celery `chord` would be ideal but adds a
        # result backend requirement; a serial chain is reliable enough
        # for v1 — transcribe takes the long path so we let it run first
        # then slide_extract (fast) then finalize.
        tasks = [transcribe_task.s(session_id)]
        if slide_src_count > 0:
            tasks.append(slide_extract_task.s(session_id))
        tasks.append(finalize_task.s(session_id))
        chain(*tasks).apply_async()

        logger.info(f"ingest: enqueued pipeline for {session_id} (slides={slide_src_count})")
        return {"session_id": session_id, "enqueued": True, "slide_sources": slide_src_count}

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        raise
    finally:
        engine.dispose()


def enqueue_ingest(session_id: str) -> None:
    """Called from `/v1/gcs/upload-complete` to kick off the pipeline."""
    ingest_task.apply_async(args=[session_id], queue="celery")
