# Workflow: SOP Stage Deadline Notifications

Scans the per-session SOP workflow state for stages that have blown past their SLA window and emits warnings. When the `SOP_DEADLINE_EMAIL_ENABLED` feature flag is on, it additionally emails the stage assignee.

**Feature flag:** `SOP_DEADLINE_EMAIL_ENABLED` — **default OFF** ([app/config.py:110](../../app/config.py#L110)). With the flag off, the warning scan still runs (WS event + audit row), but no email is sent ([app/tasks/sop_tasks.py:540-545](../../app/tasks/sop_tasks.py#L540)).

Implemented by `sop_check_deadlines_task` ([app/tasks/sop_tasks.py:455](../../app/tasks/sop_tasks.py#L455)); the email path is `_maybe_send_deadline_email` ([app/tasks/sop_tasks.py:210](../../app/tasks/sop_tasks.py#L210)); SMTP send is `send_smtp_email` ([app/services/email.py:33](../../app/services/email.py#L33)).

## Trigger

Two trigger paths, both run the same `sop_check_deadlines_task`:

1. **Celery Beat schedule** — `sop-check-deadlines` runs every `3600.0` seconds (hourly) from worker start ([app/tasks/celery_app.py:84-88](../../app/tasks/celery_app.py#L84)). Beat is embedded in the worker via the `-B` flag (per the comment at [app/tasks/celery_app.py:66-70](../../app/tasks/celery_app.py#L66)).
2. **Manual operator invocation** — `POST /v1/diag/sop-check` runs the task synchronously (`.apply().get(timeout=60)`) and returns its result ([app/api/diagnostics.py:331-346](../../app/api/diagnostics.py#L331)). Requires a logged-in `CurrentUser`; no admin gate on this route.

## Inputs

The task takes no arguments. It reads, per overdue stage:

- `sop_state` rows where `current_stage NOT IN ('complete')` — columns `session_id`, `current_stage`, `entered_current_at`, `sla_target_hours` ([app/tasks/sop_tasks.py:475-483](../../app/tasks/sop_tasks.py#L475)).
- `sla_target_hours` is per-session JSONB; falls back to the built-in `_DEFAULT_SLA_HOURS` table per stage, then to `24` ([app/tasks/sop_tasks.py:492](../../app/tasks/sop_tasks.py#L492)). Defaults: `prep` 8, `copy_draft` 24, `medical` 48, `copy_final` 24, `cms` 12, `captions` 12, `qa` 8, `complete` 0 (terminal) ([app/tasks/sop_tasks.py:36-45](../../app/tasks/sop_tasks.py#L36)).

When the email path runs, `_maybe_send_deadline_email` additionally reads from `sop_state` joined to `sessions`: `assignees` (JSONB), `title`, `code`, `session_type_id` ([app/tasks/sop_tasks.py:256-264](../../app/tasks/sop_tasks.py#L256)). Email subject/body are resolved from the `email_templates` table by `stage_id='<stage>_overdue'` via `resolve_template_sync`; an inline f-string fallback is used when no template resolves ([app/tasks/sop_tasks.py:359-403](../../app/tasks/sop_tasks.py#L359)).

SMTP transport reads env vars at send time: `SMTP_HOST` (required), `SMTP_PORT` (default `587`), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` (default sentinel `rounds-noreply@vin.com`) ([app/services/email.py:52-62](../../app/services/email.py#L52)).

## Validations

- **Overdue gate:** `deadline = entered_current_at + sla_hours`; a stage is overdue only when `now > deadline` ([app/tasks/sop_tasks.py:495-497](../../app/tasks/sop_tasks.py#L495)). Stages with `entered_current_at` NULL are skipped ([app/tasks/sop_tasks.py:487](../../app/tasks/sop_tasks.py#L487)).
- **Zero-SLA skip:** stages with `sla_hours <= 0` are skipped (covers terminal `complete`) ([app/tasks/sop_tasks.py:493-494](../../app/tasks/sop_tasks.py#L493)). No grace period beyond this — emails fire the moment `overdue_hours > 0` ([app/tasks/sop_tasks.py:306-309](../../app/tasks/sop_tasks.py#L306)).
- **Assignee validation (email path):** the stage's assignee must be a string, must NOT start with `group:` (group expansion is not implemented), and must contain `@`; otherwise the email is silently skipped ([app/tasks/sop_tasks.py:271-273](../../app/tasks/sop_tasks.py#L271)).
- **Throttle (BR-004):** at most one email per `(session_id, stage)` per 23 hours. Enforced inside a Postgres advisory transaction lock keyed on `(session_id, stage)`; the throttle SELECT checks `audit_events` of kind in `('sop.deadline_email_sent', 'sop.deadline_email_failed')` and returns early if the last such event is < 23 h old ([app/tasks/sop_tasks.py:282-311](../../app/tasks/sop_tasks.py#L282)).
- **SMTP recipient validation:** `send_smtp_email` returns `ok=False` (no raise) on missing `SMTP_HOST` or a `to` missing `@` ([app/services/email.py:52-57](../../app/services/email.py#L52)).

## Approvals

None. This is an automated background scan with no human approval step.

## Notifications

- **WebSocket:** one `sop.deadline_warning` event per overdue stage (`type`, `stage`, `overdue_hours`), published via `publish_ws_event_sync` ([app/tasks/sop_tasks.py:501-510](../../app/tasks/sop_tasks.py#L501)). WS emit failure is logged and non-fatal.
- **Email (flag-gated):** when `SOP_DEADLINE_EMAIL_ENABLED` is true, a multipart (text + HTML) email to the stage assignee via SMTP. Subject defaults to `[Rounds] {code} — {stage} stage overdue by {overdue_hours}h` on the inline-fallback path ([app/tasks/sop_tasks.py:391](../../app/tasks/sop_tasks.py#L391)); the body links to `https://rounds.vin/#/e/{session_id}/sop` ([app/tasks/sop_tasks.py:340](../../app/tasks/sop_tasks.py#L340)). HTML values are escaped (`html.escape(..., quote=True)`) for XSS safety ([app/tasks/sop_tasks.py:388-390](../../app/tasks/sop_tasks.py#L388)).

## Outputs

- Return dict: `{"warnings": <count emitted>, "scanned": <rows scanned>}` ([app/tasks/sop_tasks.py:549](../../app/tasks/sop_tasks.py#L549)).
- `/v1/diag/sop-check` wraps this as `{"ok": True, **result}` or `{"ok": False, "error": ...}` ([app/api/diagnostics.py:343-346](../../app/api/diagnostics.py#L343)).
- On email send: an `audit_events` row is written/updated (see Audit Events), and the recipient receives mail.

## Status Changes

**None.** The docstring and Beat comment both state the task is purely additive — it writes to `audit_events` only and never mutates `sop_state` or `sessions` ([app/tasks/celery_app.py:79-83](../../app/tasks/celery_app.py#L79), [app/tasks/sop_tasks.py:457](../../app/tasks/sop_tasks.py#L457)). SOP stage advancement is a separate concern not handled here.

## Audit Events

All to the `audit_events` table:

- **`sop.deadline_warning`** — one per overdue stage, `actor_email='system:sop_check_deadlines'`, summary `Stage <stage> overdue by <hours> hours`, `details` JSONB `{stage, overdue_hours}` ([app/tasks/sop_tasks.py:516-532](../../app/tasks/sop_tasks.py#L516)). Insert failure is logged, non-fatal.
- **`sop.deadline_email_sent`** — inserted *before* the SMTP attempt to claim the 23 h throttle slot; recipient is masked in `summary` but full address kept in `details->>'recipient'` ([app/tasks/sop_tasks.py:312-328](../../app/tasks/sop_tasks.py#L312), masking at [app/tasks/sop_tasks.py:144-159](../../app/tasks/sop_tasks.py#L144)). On success the same row is UPDATEd with `latency_ms` + `outcome: sent` ([app/tasks/sop_tasks.py:412-425](../../app/tasks/sop_tasks.py#L412)).
- **`sop.deadline_email_failed`** — on SMTP failure the claimed row's `kind` is UPDATEd to this value with the error merged into `details` (no second row) ([app/tasks/sop_tasks.py:426-444](../../app/tasks/sop_tasks.py#L426)). The throttle WHERE matches both `sent` and `failed`, so a broken recipient does not trigger hourly resend storms.

## Exception Handling

- `sop_check_deadlines_task` is `max_retries=1` ([app/tasks/sop_tasks.py:454](../../app/tasks/sop_tasks.py#L454)). The scan body wraps WS emit, audit insert, and the entire email path in individual try/except blocks that log a warning and continue — a failure on one stage never aborts the scan ([app/tasks/sop_tasks.py:511-545](../../app/tasks/sop_tasks.py#L511)).
- The email path's throttle-claim block catches all exceptions, logs, and returns (skips the send) rather than risking a double-send ([app/tasks/sop_tasks.py:329-336](../../app/tasks/sop_tasks.py#L329)).
- Template resolution failure falls through to the inline f-string body ([app/tasks/sop_tasks.py:368-371](../../app/tasks/sop_tasks.py#L368)).
- `send_smtp_email` never raises — it returns `{ok, error, latency_ms}` and the caller records the outcome ([app/services/email.py:78-84](../../app/services/email.py#L78)).
- The engine is always disposed in a `finally` block ([app/tasks/sop_tasks.py:550-551](../../app/tasks/sop_tasks.py#L550)).

## Source Verification
- **Files Used:** app/tasks/sop_tasks.py, app/services/email.py, app/config.py, app/tasks/celery_app.py, app/api/diagnostics.py
- **Components Used:** none
- **APIs Used:** POST /v1/diag/sop-check (manual trigger)
- **Database Tables Used:** sop_state, sessions, email_templates, audit_events
- **Permission Logic Used:** /v1/diag/sop-check requires JWT (CurrentUser); no admin gate. The Beat-triggered path has no auth (runs in worker).
- **Confidence Score:** High — every claim traced to the named source lines; flag default OFF confirmed in config.
- **Evidence Links:** [app/config.py:110](../../app/config.py#L110), [app/tasks/sop_tasks.py:455](../../app/tasks/sop_tasks.py#L455), [app/tasks/sop_tasks.py:540](../../app/tasks/sop_tasks.py#L540), [app/tasks/celery_app.py:84](../../app/tasks/celery_app.py#L84), [app/api/diagnostics.py:331](../../app/api/diagnostics.py#L331)
