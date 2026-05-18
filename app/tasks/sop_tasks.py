"""
SOP control layer — auto-init + stage-deadline notifications.

Ports MIC `app/tasks/sop_tasks.py` (358 LOC) condensed for Rounds' schema.

Two tasks here:
  • sop_auto_init_task — triggered when session.status → ready. Initializes
    sop_state row (if missing) and emits a 'sop.initialized' WS + audit
    event so the editor's right rail shows the active SOP stage.
  • sop_check_deadlines_task — scheduled periodically (every hour). Scans
    sop_state for stages past their SLA window, emits sop.deadline_warning
    WS events + audit log entries. Optionally sends emails via the SMTP
    helper when wired (deferred).

Phase 7g. Closes residual 🟠 (SOP auto-advance + deadline notifications).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


# Default SLA targets per stage (hours). Editable per-session via sop_state.sla_target_hours.
_DEFAULT_SLA_HOURS = {
    "prep":       8,
    "copy_draft": 24,
    "medical":    48,
    "copy_final": 24,
    "cms":        12,
    "captions":   12,
    "qa":         8,
    "complete":   0,  # terminal
}


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.sop.auto_init",
    max_retries=2,
)
def sop_auto_init_task(self, session_id: str) -> dict:
    """
    Initialize sop_state for a session that just landed `ready`.
    Idempotent — if a row already exists, just emit the WS event and return.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT current_stage FROM sop_state WHERE session_id = CAST(:sid AS uuid)"),
                {"sid": session_id},
            ).fetchone()

            if existing:
                logger.info(f"sop_auto_init: row already exists for {session_id} (stage={existing[0]})")
            else:
                # Resolve stage assignees from session_speakers + default templates.
                # For now we leave assignees empty {} — the Settings → Types & Stages
                # matrix is where org-wide defaults live. A future pass can hydrate.
                conn.execute(
                    text(
                        """
                        INSERT INTO sop_state
                            (session_id, current_stage, assignees, sla_target_hours)
                        VALUES
                            (CAST(:sid AS uuid), 'prep', '{}'::jsonb, CAST(:sla AS jsonb))
                        """
                    ),
                    {"sid": session_id, "sla": json.dumps(_DEFAULT_SLA_HOURS)},
                )
                # Append-only transition row
                conn.execute(
                    text(
                        """
                        INSERT INTO sop_transitions
                            (session_id, from_stage, to_stage, actor_email)
                        VALUES
                            (CAST(:sid AS uuid), NULL, 'prep', 'system:sop_auto_init')
                        """
                    ),
                    {"sid": session_id},
                )

        # WS broadcast + audit event
        try:
            from app.engines.ws_bridge import publish_ws_event_sync

            publish_ws_event_sync(
                session_id,
                {"type": "sop.initialized", "stage": existing[0] if existing else "prep"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"sop_auto_init: WS emit failed: {exc}")

        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO audit_events (session_id, actor_email, kind, summary)
                        VALUES (CAST(:sid AS uuid), 'system:sop_auto_init', 'sop.initialized', 'SOP initialized at stage prep')
                        """
                    ),
                    {"sid": session_id},
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"sop_auto_init: audit insert failed: {exc}")

        return {
            "session_id":    session_id,
            "current_stage": existing[0] if existing else "prep",
            "initialized":   not existing,
        }

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        # Non-fatal — SOP init failure should never mark session failed.
        logger.exception(f"sop_auto_init: terminal failure for {session_id}")
        return {"session_id": session_id, "error": str(exc)}
    finally:
        engine.dispose()


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.sop.check_deadlines",
    max_retries=1,
)
def sop_check_deadlines_task(self) -> dict:  # noqa: ARG001
    """
    Periodic scan of sop_state — emit deadline_warning for stages past SLA.

    Scheduled by Celery Beat (configure on the worker side) every hour:
      celery beat tick → rounds.tasks.sop.check_deadlines

    For now this runs only when invoked manually via /v1/diag/sop-check.
    Returns count of warnings emitted.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    warnings_emitted = 0
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT session_id, current_stage, entered_current_at, sla_target_hours
                      FROM sop_state
                     WHERE current_stage NOT IN ('complete')
                    """
                )
            ).fetchall()

        now = datetime.now(timezone.utc)
        for session_id, stage, entered_at, sla_target_hours in rows:
            if not entered_at:
                continue
            sla_map = sla_target_hours if isinstance(sla_target_hours, dict) else (
                json.loads(sla_target_hours) if sla_target_hours else {}
            )
            sla_hours = sla_map.get(stage, _DEFAULT_SLA_HOURS.get(stage, 24))
            if sla_hours <= 0:
                continue
            deadline = entered_at + timedelta(hours=sla_hours)
            if now <= deadline:
                continue

            overdue_hours = round((now - deadline).total_seconds() / 3600.0, 1)
            try:
                from app.engines.ws_bridge import publish_ws_event_sync

                publish_ws_event_sync(
                    str(session_id),
                    {
                        "type":          "sop.deadline_warning",
                        "stage":         stage,
                        "overdue_hours": overdue_hours,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"sop_check_deadlines: WS emit failed for {session_id}: {exc}")

            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            """
                            INSERT INTO audit_events (session_id, actor_email, kind, summary, details)
                            VALUES (CAST(:sid AS uuid), 'system:sop_check_deadlines',
                                    'sop.deadline_warning',
                                    'Stage ' || :stage || ' overdue by ' || :over || ' hours',
                                    CAST(:d AS jsonb))
                            """
                        ),
                        {
                            "sid":   str(session_id),
                            "stage": stage,
                            "over":  str(overdue_hours),
                            "d":     json.dumps({"stage": stage, "overdue_hours": overdue_hours}),
                        },
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"sop_check_deadlines: audit insert failed: {exc}")

            warnings_emitted += 1

        return {"warnings": warnings_emitted, "scanned": len(rows)}
    finally:
        engine.dispose()
