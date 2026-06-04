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


def _maybe_send_deadline_email(engine, session_id: str, stage: str, overdue_hours: float) -> None:
    """
    Look up the stage assignee from sop_state, throttle-check against
    audit_events, and send via app.services.email.send_smtp_email.

    Throttle: a single email per (session_id, stage) per 23 hours. Lookup
    is via audit_events of kind 'sop.deadline_email_sent' (written by this
    function after a successful send). 23h chosen so the next hourly Beat
    tick after a 24h-after-overdue moment will re-send.

    Skips silently when:
      • the assignees JSONB is missing the stage entry
      • the assignee value is a group ("group:NAME") — group expansion is
        deferred (no per-group roster table wired yet)
      • the assignee doesn't look like an email address
      • a previous sop.deadline_email_sent exists for (session_id, stage)
        within the 23h window
    """
    from app.services.email import send_smtp_email

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT s.assignees, sess.title, sess.code "
                "FROM sop_state s "
                "LEFT JOIN sessions sess ON sess.id = s.session_id "
                "WHERE s.session_id = CAST(:sid AS uuid)"
            ),
            {"sid": session_id},
        ).first()
    if not row:
        return
    assignees = row[0] if isinstance(row[0], dict) else (json.loads(row[0]) if row[0] else {})
    title = row[1] or "(untitled)"
    code = row[2] or session_id[:8]
    raw = assignees.get(stage) if isinstance(assignees, dict) else None
    if not isinstance(raw, str) or raw.startswith("group:") or "@" not in raw:
        return

    # Throttle: did we send for this (session, stage) within 23h?
    with engine.connect() as conn:
        last = conn.execute(
            text(
                "SELECT MAX(occurred_at) FROM audit_events "
                "WHERE session_id = CAST(:sid AS uuid) "
                "  AND kind = 'sop.deadline_email_sent' "
                "  AND details->>'stage' = :stage"
            ),
            {"sid": session_id, "stage": stage},
        ).scalar()
    if last is not None:
        # Postgres returns timezone-aware datetimes when the column is
        # TIMESTAMPTZ; coerce defensively in case of TIMESTAMP.
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last < timedelta(hours=23):
            return

    subject = f"[Rounds] {code} — {stage} stage overdue by {overdue_hours}h"
    text_body = (
        f"Session: {title} ({code})\n"
        f"Stage: {stage}\n"
        f"Overdue: {overdue_hours} hours past SLA\n\n"
        f"Open in editor: https://rounds.vin/#/e/{session_id}/sop\n"
    )
    html_body = (
        f"<p>Session: <strong>{title}</strong> ({code})</p>"
        f"<p>Stage: <code>{stage}</code></p>"
        f"<p style='color:#b00'>Overdue: <strong>{overdue_hours}h</strong> past SLA</p>"
        f"<p><a href='https://rounds.vin/#/e/{session_id}/sop'>Open in editor</a></p>"
    )
    result = send_smtp_email(raw, subject, text_body, html_body=html_body)

    # Record outcome regardless of success/failure so retries can be observed.
    kind = "sop.deadline_email_sent" if result["ok"] else "sop.deadline_email_failed"
    summary = (
        f"Notified {raw} for stage {stage}"
        if result["ok"]
        else f"Notify failed for {raw}: {result.get('error', 'unknown')}"
    )
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
                    "VALUES (CAST(:sid AS uuid), 'system:sop_check_deadlines', :k, :s, CAST(:d AS jsonb))"
                ),
                {
                    "sid": session_id,
                    "k":   kind,
                    "s":   summary,
                    "d":   json.dumps({
                        "stage": stage,
                        "overdue_hours": overdue_hours,
                        "recipient": raw,
                        "latency_ms": result["latency_ms"],
                        **({"error": result["error"]} if not result["ok"] and result.get("error") else {}),
                    }),
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"sop_check_deadlines: email audit insert failed: {exc}")


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

            # Optional SMTP notification — feature-flagged off by default
            # (settings.SOP_DEADLINE_EMAIL_ENABLED) so enabling it is an
            # intentional production action. See app/services/email.py for
            # the SMTP env-var pattern.
            try:
                from app.config import settings as _settings
                if _settings.SOP_DEADLINE_EMAIL_ENABLED:
                    _maybe_send_deadline_email(engine, str(session_id), stage, overdue_hours)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"sop_check_deadlines: email path failed: {exc}")

            warnings_emitted += 1

        return {"warnings": warnings_emitted, "scanned": len(rows)}
    finally:
        engine.dispose()
