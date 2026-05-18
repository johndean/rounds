"""
finalize_task — last link in the chain. aligning → ready.

After 6i, align_task does the heavy lifting and triggers finalize.
finalize's job is simply:
  • verify segments exist (else fail)
  • transition aligning → ready

The "walk every intermediate state" stub logic from 6b is removed because
6g+6h+6i now own their own transitions explicitly.
"""
from __future__ import annotations

import logging

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.finalize",
    max_retries=1,
)
def finalize_task(self, prev_result=None, session_id=None) -> dict:  # noqa: ARG001
    """
    Resolve session_id from kwarg OR previous chain result, verify segments,
    transition aligning → ready. Chain-call safe: when called as the next
    link in a Celery chain, prev_result is the upstream task's return.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.engines.state_machine import ConflictError, transition_session_sync

    if not session_id:
        if isinstance(prev_result, str):
            session_id = prev_result
        elif isinstance(prev_result, dict):
            session_id = prev_result.get("session_id")
    if not session_id:
        raise RuntimeError("finalize_task: no session_id")

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            seg_count = conn.execute(
                text("SELECT COUNT(*) FROM segments WHERE session_id = CAST(:sid AS uuid)"),
                {"sid": session_id},
            ).scalar() or 0
            current = conn.execute(
                text("SELECT status FROM sessions WHERE id = CAST(:sid AS uuid)"),
                {"sid": session_id},
            ).scalar()

        if seg_count == 0:
            try:
                transition_session_sync(session_id, "failed", actor="finalize_task", reason="no_segments")
            except ConflictError as e:
                logger.warning(f"finalize: cannot mark failed: {e}")
            return {"session_id": session_id, "status": "failed", "reason": "no_segments"}

        # If 6g+6h+6i shipped their own transitions, status is already 'aligning'.
        # If running the legacy pre-6g/6h chain via finalize directly, walk
        # through the intermediate states to satisfy ALLOWED_TRANSITIONS.
        try:
            if current == "transcribing":
                transition_session_sync(session_id, "normalizing", actor="finalize_task", reason="stub")
                current = "normalizing"
            if current == "normalizing":
                transition_session_sync(session_id, "fusing", actor="finalize_task", reason="stub")
                current = "fusing"
            if current == "fusing":
                transition_session_sync(session_id, "aligning", actor="finalize_task")
                current = "aligning"
            if current == "aligning":
                transition_session_sync(session_id, "ready", actor="finalize_task")
        except ConflictError as e:
            logger.warning(f"finalize: transition error ({e}) — current={current}")

        # Release rate-limit slot (6o) — session is terminal-success.
        try:
            from app.middleware.rate_limit import release_slot

            release_slot(None, session_id)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"finalize: release_slot failed: {e}")

        # Trigger IIL learning loop (6q) — non-blocking, never marks failed.
        try:
            from app.tasks.kp_task import kp_task

            kp_task.apply_async(args=[session_id], queue="celery")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"finalize: failed to trigger kp_task: {e}")

        logger.info(f"finalize: session {session_id} ready")
        return {"session_id": session_id, "status": "ready"}
    finally:
        engine.dispose()
