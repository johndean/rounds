"""
Finalize task — runs align, then flips session to 'ready'.

When this task runs the session has:
  * segments rows from transcribe_task
  * slides rows (if a PDF source was attached) from slide_extract_task

Finalize runs align_task synchronously (it's fast, all DB), then
transitions session.status to 'ready'. The Processing view auto-redirects
the user to /e/<id> when the session lands ready.
"""
from __future__ import annotations

import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="rounds.tasks.finalize",
    max_retries=1,
    default_retry_delay=15,
)
def finalize_task(self, prev_result: dict | None = None, session_id: str | None = None) -> dict:  # noqa: ARG001
    """
    Last link of the ingest chain.

    Celery passes the previous task's return value as the first positional
    argument when tasks are chained. We accept it but ignore — `session_id`
    is also bound via `.s(session_id)` so it's available either way.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.tasks.align import align_task

    if not session_id:
        # Chained-call path: session_id was the .s() arg; the previous
        # return is in prev_result instead. Celery's chain semantics put
        # the previous result first when bound, so accept either order.
        if isinstance(prev_result, str):
            session_id = prev_result
        elif isinstance(prev_result, dict):
            session_id = prev_result.get("session_id")

    if not session_id:
        raise RuntimeError("finalize_task: no session_id resolved")

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        # align runs in-process so we can flip status atomically with the
        # alignment results visible.
        align_result = align_task.run(session_id=session_id)  # type: ignore[misc]
        logger.info(f"finalize: align={align_result}")

        with engine.begin() as conn:
            seg_count = conn.execute(
                text("SELECT COUNT(*) FROM segments WHERE session_id = CAST(:sid AS uuid)"),
                {"sid": session_id},
            ).scalar() or 0
            if seg_count == 0:
                conn.execute(
                    text(
                        """
                        UPDATE sessions
                           SET status = 'failed', updated_at = now()
                         WHERE id = CAST(:sid AS uuid)
                        """
                    ),
                    {"sid": session_id},
                )
                logger.error(f"finalize: session {session_id} has 0 segments — marked failed")
                return {"session_id": session_id, "status": "failed", "reason": "no_segments"}

            conn.execute(
                text(
                    """
                    UPDATE sessions
                       SET status = 'ready', updated_at = now()
                     WHERE id = CAST(:sid AS uuid)
                    """
                ),
                {"sid": session_id},
            )
        logger.info(f"finalize: session {session_id} marked ready")
        return {"session_id": session_id, "status": "ready"}
    except Exception as exc:
        logger.exception(f"finalize failed for {session_id}: {exc}")
        raise
    finally:
        engine.dispose()
