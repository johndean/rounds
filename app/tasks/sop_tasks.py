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

Related ADRs: ADR-006 (Celery queue + Beat scheduler).
Related business rules: BR-003 (SLA hours table), BR-004 (23h throttle), BR-005 (0h grace period).
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

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


def _mask_email(email: str) -> str:
    """
    Mask the local-part of an email address for audit-log summaries.

    ``jane.doe@vin.com`` -> ``jan***@vin.com``. The full email stays in
    ``audit_events.details->>'recipient'`` for operators who need it; the
    user-readable ``summary`` field gets the masked form so an audit-log
    dump isn't a recipient-address harvest. Returns ``***`` for
    addresses without an ``@`` (defensive — caller already validates).
    """
    if not email or "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 3:
        return f"***@{domain}"
    return f"{local[:3]}***@{domain}"


def _deadline_lock_key(session_id: str, stage: str) -> int:
    """
    Stable per-(session_id, stage) Postgres advisory-lock key.

    Used by ``_maybe_send_deadline_email`` to serialize concurrent
    invocations against the same overdue (session, stage) pair so the
    23h throttle SELECT and the throttle-row INSERT happen atomically.
    Python's built-in ``hash()`` is randomized per process and would
    produce different lock keys across worker restarts; an MD5 digest
    of the canonical string gives a deterministic value. Trimmed to
    8 bytes and masked into the signed-positive bigint range Postgres
    requires.
    """
    h = hashlib.md5(f"{session_id}::{stage}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFFFFFFFFFFFFFF


def _html_to_text(html_str: str) -> str:
    """HTML → plain-text for the email plain-text alternative part.

    Strips tags, collapses whitespace, decodes HTML entities via
    ``html.unescape`` (stdlib — handles 200+ named + numeric entities).
    Fits the flat ProximaNova-style mailer markup seeded in migration
    048 / 051 which has minimal nesting and no script/style blocks.

    Phase 7.4 (2026-06-05) replaced the previous 6-entity decode chain
    with ``html.unescape``. Reason: ``html.escape(s, quote=True)``
    (which ``substitute_variables`` now applies for XSS protection)
    emits ``&#x27;`` for apostrophes — NOT ``&#39;`` — and session
    titles like ``ACVIM's Forum`` were corrupting the text/plain
    alternative body. The stdlib decoder covers both forms plus
    every other entity an operator might write into a template.

    Returns "" on empty/None input.
    """
    if not html_str:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html_str, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</tr\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</td\s*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
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

    Phase 7.3 hardening (2026-06-05) closes three race / contract gaps
    surfaced by the verification workflow:
      • Throttle SELECT + audit INSERT run inside a single transaction
        guarded by a per-(session, stage) advisory lock — no double-send
        between Beat tick and /v1/diag/sop-check.
      • Audit row is inserted BEFORE the SMTP attempt (claims the
        throttle slot); on SMTP failure the same row is UPDATEd to
        kind='sop.deadline_email_failed' instead of inserting a second
        row. Throttle WHERE matches both 'sent' and 'failed' so a
        broken recipient doesn't trigger hourly resend storms.
      • Recipient email is masked in audit_events.summary; full
        address stays in audit_events.details->>'recipient' for
        operator forensics (policy-bound retention).

    Throttle: a single email per (session_id, stage) per 23 hours.
    Lookup via audit_events of kind IN ('sop.deadline_email_sent',
    'sop.deadline_email_failed').

    Skips silently when:
      • the assignees JSONB is missing the stage entry
      • the assignee value is a group ("group:NAME") — group expansion
        is deferred (no per-group roster table wired yet)
      • the assignee doesn't look like an email address
      • a previous send-or-failure audit row exists within the 23h
        window
    """
    from app.api.email_templates import (
        resolve_template_sync,
        substitute_variables,
        substitute_variables_text,
    )
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

    masked_recipient = _mask_email(raw)
    lock_key = _deadline_lock_key(session_id, stage)

    # Atomic throttle-check + slot-claim. The advisory lock serializes
    # concurrent invocations against the same (session, stage), so two
    # workers can't both pass the throttle SELECT and both INSERT.
    audit_id: Optional[str] = None
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})
            last = conn.execute(
                text(
                    "SELECT MAX(occurred_at) FROM audit_events "
                    "WHERE session_id = CAST(:sid AS uuid) "
                    "  AND kind IN ('sop.deadline_email_sent', 'sop.deadline_email_failed') "
                    "  AND details->>'stage' = :stage"
                ),
                {"sid": session_id, "stage": stage},
            ).scalar()
            if last is not None:
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                # BR-004 — 23-hour deadline-email throttle window.
                # See docs/BUSINESS_RULES.md#br-004.
                # Why: sop_check_deadlines_task fires hourly. Without
                # the throttle, every Beat tick would re-email an
                # overdue stage. 23h (not 24h) avoids "off-by-one"
                # drift where two consecutive daily Beat ticks fall
                # on either side of the boundary. The throttle row is
                # the (session_id, stage) audit_events entry above.
                #
                # BR-005 — Zero-hour deadline-email grace period.
                # See docs/BUSINESS_RULES.md#br-005. No grace check
                # here (or anywhere): emails fire the moment overdue_hours
                # > 0. BR-004 is the only thing that prevents repeat sends.
                if datetime.now(timezone.utc) - last < timedelta(hours=23):
                    return
            audit_id = conn.execute(
                text(
                    "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
                    "VALUES (CAST(:sid AS uuid), 'system:sop_check_deadlines', "
                    "        'sop.deadline_email_sent', :s, CAST(:d AS jsonb)) "
                    "RETURNING id"
                ),
                {
                    "sid": session_id,
                    "s":   f"Notify attempt for {masked_recipient} for stage {stage}",
                    "d":   json.dumps({
                        "stage":         stage,
                        "overdue_hours": overdue_hours,
                        "recipient":     raw,
                    }),
                },
            ).scalar()
    except Exception as exc:  # noqa: BLE001
        # Failed to claim the throttle slot — log and skip. Next Beat
        # tick will retry. Better to drop one notification than to
        # double-send.
        logger.warning(
            f"sop_check_deadlines: throttle/claim failed for {session_id}/{stage}: {exc}"
        )
        return
    if audit_id is None:
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
        # Subject is a plain-text RFC 5322 header; use the no-escape
        # variant so {{ session_title }} containing an apostrophe
        # doesn't deliver `&#x27;` literally to recipients. Body IS
        # HTML, so the escaping variant is required there for XSS safety.
        subject   = substitute_variables_text(template["subject"], template_vars)
        html_body = substitute_variables(template["body"],         template_vars)
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

    # Update the throttle row to record the outcome. The row already
    # claimed the slot (kind='sop.deadline_email_sent'); on success we
    # only enrich details with latency. On failure we update the kind
    # and merge in the error so audit consumers see the actual outcome.
    try:
        with engine.begin() as conn:
            if result["ok"]:
                conn.execute(
                    text(
                        "UPDATE audit_events SET "
                        "  summary = :s, "
                        "  details = details || CAST(:d AS jsonb) "
                        "WHERE id = CAST(:id AS uuid)"
                    ),
                    {
                        "id": str(audit_id),
                        "s":  f"Notified {masked_recipient} for stage {stage}",
                        "d":  json.dumps({"latency_ms": result["latency_ms"], "outcome": "sent"}),
                    },
                )
            else:
                conn.execute(
                    text(
                        "UPDATE audit_events SET "
                        "  kind = 'sop.deadline_email_failed', "
                        "  summary = :s, "
                        "  details = details || CAST(:d AS jsonb) "
                        "WHERE id = CAST(:id AS uuid)"
                    ),
                    {
                        "id": str(audit_id),
                        "s":  f"Notify failed for {masked_recipient} for stage {stage}: {result.get('error', 'unknown')}",
                        "d":  json.dumps({
                            "latency_ms": result["latency_ms"],
                            "outcome":    "failed",
                            "error":      result.get("error"),
                        }),
                    },
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"sop_check_deadlines: email audit update failed: {exc}")


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
