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
    from app.tasks.frame_task import frame_task
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

        # Read pipeline config — routes 'direct' to AI MODE multimodal,
        # 'enhanced' to the STT-based standard chain.
        with engine.connect() as conn:
            cfg = conn.execute(
                text(
                    """
                    SELECT ai_pipeline FROM session_templates
                     WHERE session_id = CAST(:sid AS uuid)
                    """
                ),
                {"sid": session_id},
            ).fetchone()
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

        ai_pipeline = (cfg[0] if cfg else "enhanced") or "enhanced"

        # template_autodetect runs in parallel for either pipeline.
        try:
            from app.tasks.ai_process import template_autodetect_task

            template_autodetect_task.apply_async(args=[session_id], queue="celery")
        except ImportError:
            pass

        if ai_pipeline == "direct":
            # AI MODE direct — single task does everything, marks ready itself.
            # Run slide_extract in parallel for thumbnails + bullets.
            from app.tasks.ai_process import ai_process_task

            if slide_src_count > 0:
                slide_extract_task.apply_async(args=[session_id], queue="celery")
            ai_process_task.apply_async(args=[session_id], queue="celery")
            logger.info(
                f"ingest[direct]: enqueued ai_process_task for {session_id} "
                f"(slides={slide_src_count})"
            )
            return {
                "session_id":    session_id,
                "enqueued":      True,
                "ai_pipeline":   "direct",
                "slide_sources": slide_src_count,
            }

        # Standard STT-enhanced chain.
        # frame_task runs IN PARALLEL with the main chain — anchor_task
        # (triggered by transcribe on completion) reads frame's output
        # from Redis at its moment of execution. Graceful degradation
        # if frame hasn't finished yet (empty visual signals).
        # slide_extract similarly runs in parallel — alignment reads its
        # rows from DB whenever it runs.
        transition_session_sync(session_id, "transcribing", actor="ingest_task")

        frame_task.apply_async(args=[session_id], queue="celery")
        if slide_src_count > 0:
            slide_extract_task.apply_async(args=[session_id], queue="celery")

        # Main chain: transcribe → anchor (triggered inside transcribe) →
        # normalize (when 6g lands) → fusion (when 6h) → align (when 6i) →
        # finalize. Today transcribe triggers anchor which would trigger
        # normalize — until 6g normalize doesn't import so anchor logs a
        # skip. We still need finalize to run after the chain. Pattern:
        # transcribe and anchor are linked via internal triggers;
        # finalize chains explicitly after transcribe so it always runs
        # regardless of normalize/fusion/align presence.
        tasks = [transcribe_task.s(session_id), finalize_task.s(session_id)]
        chain(*tasks).apply_async()

        logger.info(
            f"ingest[enhanced]: enqueued chain (+ frame fanout) for {session_id} "
            f"(slides={slide_src_count})"
        )
        return {
            "session_id":    session_id,
            "enqueued":      True,
            "ai_pipeline":   "enhanced",
            "slide_sources": slide_src_count,
        }

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
