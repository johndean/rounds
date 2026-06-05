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

import html
import json
import logging
import re
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


def _html_to_text(html: str) -> str:
    """Crude HTML → plain-text for the email plain-text alternative part.

    Strips tags, collapses whitespace, decodes the few HTML entities our
    templates use. Not a full HTML parser — fits the flat ProximaNova-
    style mailer markup seeded in migration 048 / 051 which has minimal
    nesting and no script/style blocks. Returns "" on empty/None input.
    """
    if not html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</tr\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</td\s*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    text = re.sub(r"\n[ \t]*\n[ \t\n]*", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _maybe_send_deadline_email(engine, session_id: str, stage: str, overdue_hours: float) -> None:
    """
    Look up the stage assignee from sop_state, throttle-check against
    audit_events, and send via app.services.email.send_smtp_email.

    Phase 7.2 (2026-06-04): resolves subject/body from the
    email_templates table by querying stage_id='<stage>_overdue'.
    Migration 051 seeds these variants. Falls back to the F1.E inline
    f-strings when no template resolves — keeps the path running even
    if migration 051 hasn't applied yet or an operator soft-deleted
    the overdue variants.

    Throttle: a single email per (session_id, stage) per 23 hours.
    Lookup via audit_events of kind 'sop.deadline_email_sent' (written
    by this function after a successful send). 23h chosen so the next
    hourly Beat tick after a 24h-after-overdue moment will re-send.

    Skips silently when:
      • the assignees JSONB is missing the stage entry
      • the assignee value is a group ("group:NAME") — group expansion
        is deferred (no per-group roster table wired yet)
      • the assignee doesn't look like an email address
      • a previous sop.deadline_email_sent exists for (session_id, stage)
        within the 23h window
    """
    from app.api.email_templates import resolve_template_sync, substitute_variables
    from app.services.email import send_smtp_email

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT s.assignees, sess.title, sess.code, sess.session_type_id "
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
    session_type_id = row[3]
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

    editor_url = f"https://rounds.vin/#/e/{session_id}/sop"
    # Derive a reasonable first-name from the assignee email's local part
    # (e.g. "jane.doe@vin.com" → "Jane"). Templates show this as a
    # greeting prefix; fall back to "team" if local-part is empty.
    first_name = (raw.split("@", 1)[0] or "").split(".")[0].title() or "team"
    template_vars = {
        "session_code":        code,
        "session_title":       title,
        "assignee_first_name": first_name,
        "stage":               stage,
        "overdue_hours":       overdue_hours,
        "editor_url":          editor_url,
        "results_url":         editor_url,
        "session_id":          session_id,
    }

    # Try the deadline-specific template first (migration 051 seeds it).
    # Catch any DB error and fall through to the inline f-string path so
    # a SQL hiccup never blocks a deadline notification.
    template = None
    try:
        with engine.connect() as conn:
            template = resolve_template_sync(
                conn,
                session_type_id=(str(session_type_id) if session_type_id else None),
                stage_id=f"{stage}_overdue",
                locale="en-US",
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"sop_check_deadlines: template resolve failed for {stage}_overdue: {exc}"
        )

    if template:
        subject   = substitute_variables(template["subject"], template_vars)
        html_body = substitute_variables(template["body"],    template_vars)
        text_body = _html_to_text(html_body)
    else:
        # Inline fallback — used before migration 051 lands, or when
        # an operator soft-deletes the overdue template variants.
        # HTML-escape all operator-controlled values (title, code, stage)
        # before they land in the HTML body — substitute_variables does
        # this for the template path; matching here so both paths share
        # XSS-safety guarantees.
        e_title = html.escape(title, quote=True)
        e_code  = html.escape(code,  quote=True)
        e_stage = html.escape(stage, quote=True)
        subject = f"[Rounds] {code} — {stage} stage overdue by {overdue_hours}h"
        text_body = (
            f"Session: {title} ({code})\n"
            f"Stage: {stage}\n"
            f"Overdue: {overdue_hours} hours past SLA\n\n"
            f"Open in editor: {editor_url}\n"
        )
        html_body = (
            f"<p>Session: <strong>{e_title}</strong> ({e_code})</p>"
            f"<p>Stage: <code>{e_stage}</code></p>"
            f"<p style='color:#b00'>Overdue: <strong>{overdue_hours}h</strong> past SLA</p>"
            f"<p><a href='{editor_url}'>Open in editor</a></p>"
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
