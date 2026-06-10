# Notifications & Email — Demo Questions

> Module key: `notifications-email`. Every answer below is verified against current code. Path references are relative to this file (`ai-demo-knowledge/demo-questions/`), so repo-root files use `../../`.

---

## User

### Q1. As a stage assignee, will I be emailed when my session task is overdue?
- **Verified Answer:** Only if an admin has turned on the feature flag `SOP_DEADLINE_EMAIL_ENABLED`, which defaults to OFF. When on, the hourly deadline scan emails the stage assignee once their stage passes its SLA window, with a max of one email per session+stage per 23 hours. With the flag off, an overdue stage still produces an in-app WebSocket warning and an audit row, but no email.
- **Supporting Evidence:** `SOP_DEADLINE_EMAIL_ENABLED: bool = False` gates `_maybe_send_deadline_email`; the 23h throttle is BR-004.
- **Source Files:** [app/config.py:110](../../app/config.py#L110), [app/tasks/sop_tasks.py:540-545](../../app/tasks/sop_tasks.py#L540), [app/tasks/sop_tasks.py:297-311](../../app/tasks/sop_tasks.py#L297)
- **API References:** none (background task; manually triggerable via POST /v1/diag/sop-check)
- **Database References:** sop_state, audit_events

### Q2. What does the overdue email tell me?
- **Verified Answer:** The session title and code, which stage is overdue, how many hours past SLA, and a direct "Open session/editor" link to `/#/e/{session_id}/sop`. The greeting uses a first name derived from your email's local part.
- **Supporting Evidence:** Overdue seed templates render `session_title`, `session_code`, `stage`, `overdue_hours`, `editor_url`; the task derives `first_name` from the email local part.
- **Source Files:** [migrations/051_email_templates_overdue_seeds.sql:34-36](../../migrations/051_email_templates_overdue_seeds.sql#L34), [app/tasks/sop_tasks.py:340-354](../../app/tasks/sop_tasks.py#L340)
- **API References:** none
- **Database References:** email_templates

### Q3. Will I get spammed with hourly reminders while a task stays overdue?
- **Verified Answer:** No. The scan runs hourly, but a per-(session, stage) throttle limits deadline emails to one per 23 hours. A broken-recipient failure is also throttled (the failed attempt counts), so a bad address won't trigger hourly resend storms.
- **Supporting Evidence:** Throttle window `timedelta(hours=23)` matches both `sop.deadline_email_sent` and `sop.deadline_email_failed`.
- **Source Files:** [app/tasks/sop_tasks.py:285-311](../../app/tasks/sop_tasks.py#L285)
- **API References:** none
- **Database References:** audit_events

---

## Executive

### Q1. Is automated assignee email notification live in production?
- **Verified Answer:** The capability exists and is wired, but it ships disabled by default — `SOP_DEADLINE_EMAIL_ENABLED` is False, so enabling it is a deliberate production action. Until it's on, overdue stages generate only in-app/audit signals. Stage-transition ("ready for next stage") emails are seeded as templates but are NOT wired to any automatic sender at all.
- **Supporting Evidence:** Config default OFF; migration 048 header states the firing trigger for transition templates is out of scope; only `*_overdue` templates are resolved by the sender.
- **Source Files:** [app/config.py:104-110](../../app/config.py#L104), [migrations/048_email_templates.sql:24-26](../../migrations/048_email_templates.sql#L24), [app/tasks/sop_tasks.py:362-365](../../app/tasks/sop_tasks.py#L362)
- **API References:** none
- **Database References:** email_templates

### Q2. Can email wording be customized without an engineering deploy?
- **Verified Answer:** Yes. An admin edits subject + HTML body per stage in the Email Template Builder, with optional per-Session-Type overrides over a shared default. Changes persist to the `email_templates` table via the CRUD API and take effect for future sends.
- **Supporting Evidence:** EmailBuilder saves via `/v1/email-templates` POST/PUT; resolution cascades per-Type then default.
- **Source Files:** [frontend/src/components/settings/EmailBuilder.vue:114-177](../../frontend/src/components/settings/EmailBuilder.vue#L114), [app/api/email_templates.py:316-360](../../app/api/email_templates.py#L316)
- **API References:** POST/PUT /v1/email-templates, POST /v1/email-templates/resolve
- **Database References:** email_templates

### Q3. Do we have an auditable record of who was emailed and whether it succeeded?
- **Verified Answer:** Yes, two ledgers. Test sends land in `email_attempts` with recipient, result, latency, and full raw SMTP wire log. Automated deadline emails land in `audit_events` as `sop.deadline_email_sent` or `sop.deadline_email_failed`, with overdue hours, latency, and (masked in the summary) recipient.
- **Supporting Evidence:** `_record_attempt` writes email_attempts; the deadline path inserts/updates an audit row.
- **Source Files:** [app/api/email_debug.py:191-230](../../app/api/email_debug.py#L191), [app/tasks/sop_tasks.py:312-444](../../app/tasks/sop_tasks.py#L312)
- **API References:** GET /v1/admin/email-debug/attempts
- **Database References:** email_attempts, audit_events

---

## Operations

### Q1. How do I verify SMTP is configured and reachable before turning on real sends?
- **Verified Answer:** Open Settings → Diagnostics → "Open test email page". Section 1 shows which `SMTP_*` env vars are present (values for HOST/PORT/FROM; presence-only for USERNAME/PASSWORD). Section 2 runs a connect → STARTTLS → LOGIN → NOOP → QUIT probe with per-step latency and errors. No mail is sent by the probe.
- **Supporting Evidence:** `/config` returns presence + non-secret values; `/connectivity` runs the five-step probe.
- **Source Files:** [app/api/email_debug.py:64-150](../../app/api/email_debug.py#L64), [frontend/src/components/settings/EmailDebug.vue:215-260](../../frontend/src/components/settings/EmailDebug.vue#L215)
- **API References:** GET /v1/admin/email-debug/config, POST /v1/admin/email-debug/connectivity
- **Database References:** none

### Q2. Can I send a real test email to confirm end-to-end delivery?
- **Verified Answer:** Yes. The Send Test Email section posts to/subject/body to `/send`, which performs a real SMTP send and captures the full wire protocol. The result (sent/failed, latency, raw SMTP log) is shown and recorded in the attempts ledger with `trigger='debug_test'`. There is intentionally no rate limit on test sends.
- **Supporting Evidence:** `/send` calls `_send_with_wire_capture` and records via `_record_attempt`; no rate limit noted in the route docstring.
- **Source Files:** [app/api/email_debug.py:234-303](../../app/api/email_debug.py#L234), [frontend/src/components/settings/EmailDebug.vue:102-130](../../frontend/src/components/settings/EmailDebug.vue#L102)
- **API References:** POST /v1/admin/email-debug/send
- **Database References:** email_attempts

### Q3. How is the deadline scan scheduled, and can I run it on demand?
- **Verified Answer:** Celery Beat runs `rounds.tasks.sop.check_deadlines` every 3600 seconds (hourly). You can also run it synchronously on demand via `POST /v1/diag/sop-check`, which executes the task and returns its result.
- **Supporting Evidence:** Beat schedule entry `sop-check-deadlines` at 3600s; the diag route calls `sop_check_deadlines_task.apply().get(timeout=60)`.
- **Source Files:** [app/tasks/celery_app.py:84-88](../../app/tasks/celery_app.py#L84), [app/api/diagnostics.py:334-343](../../app/api/diagnostics.py#L334)
- **API References:** POST /v1/diag/sop-check
- **Database References:** sop_state, audit_events

### Q4. A user says they "weren't notified" — how do I investigate?
- **Verified Answer:** For test sends, check the Recent Attempts ledger (filterable by recipient substring, result, and time window). For automated deadline emails, query `audit_events` for `sop.deadline_email_sent`/`sop.deadline_email_failed` on that session; the full recipient is in `details.recipient` and the outcome/error in the row. If nothing is logged, the email path likely never ran (flag off, no assignee, group assignee, or 23h throttle).
- **Supporting Evidence:** `/attempts` filters; audit details carry recipient + outcome; skip conditions are explicit.
- **Source Files:** [app/api/email_debug.py:307-357](../../app/api/email_debug.py#L307), [app/tasks/sop_tasks.py:240-247](../../app/tasks/sop_tasks.py#L240), [app/tasks/sop_tasks.py:412-444](../../app/tasks/sop_tasks.py#L412)
- **API References:** GET /v1/admin/email-debug/attempts, POST /v1/diag/sop-check
- **Database References:** email_attempts, audit_events

### Q5. What SLA hours drive "overdue"?
- **Verified Answer:** Each session's `sop_state.sla_target_hours` JSONB drives it; if a stage isn't present there, the per-stage default applies: prep 8, copy_draft 24, medical 48, copy_final 24, cms 12, captions 12, qa 8, complete 0. A stage with SLA ≤ 0 (e.g. `complete`) is skipped.
- **Supporting Evidence:** `_DEFAULT_SLA_HOURS` map and the `sla_hours <= 0` skip.
- **Source Files:** [app/tasks/sop_tasks.py:36-45](../../app/tasks/sop_tasks.py#L36), [app/tasks/sop_tasks.py:489-499](../../app/tasks/sop_tasks.py#L489)
- **API References:** none
- **Database References:** sop_state

---

## Compliance

### Q1. Are recipient email addresses protected in audit logs?
- **Verified Answer:** Partly. In `audit_events`, the human-readable `summary` masks the local part (e.g. `jan***@vin.com`); the full address is retained only in `details.recipient` for operator forensics. So a casual summary dump is not a recipient-harvest, but the full address is still stored.
- **Supporting Evidence:** `_mask_email` masks the summary; the INSERT puts the raw address in `details.recipient`.
- **Source Files:** [app/tasks/sop_tasks.py:144-159](../../app/tasks/sop_tasks.py#L144), [app/tasks/sop_tasks.py:320-326](../../app/tasks/sop_tasks.py#L320)
- **API References:** none
- **Database References:** audit_events

### Q2. Are SMTP credentials ever exposed through the UI or API?
- **Verified Answer:** No. `/config` returns booleans for SMTP_USERNAME/SMTP_PASSWORD presence and always a null value for them; HOST/PORT/FROM (non-secret) return their literal values. The "Copy diagnostic bundle" feature likewise never includes username/password values.
- **Supporting Evidence:** `/config` sets `"value": None` for username/password; the bundle copy note states it excludes them.
- **Source Files:** [app/api/email_debug.py:72-78](../../app/api/email_debug.py#L72), [frontend/src/components/settings/EmailDebug.vue:276-279](../../frontend/src/components/settings/EmailDebug.vue#L276)
- **API References:** GET /v1/admin/email-debug/config
- **Database References:** none

### Q3. Is operator-authored template content safe from injection into outgoing emails?
- **Verified Answer:** Yes for HTML bodies — substituted values are HTML-escaped with `html.escape(quote=True)`, so a malicious session title can't inject markup. Subjects use a no-escape text variant because RFC 5322 headers are plain text. The inline fallback path also escapes title/code/stage. The builder preview renders in a sandboxed iframe.
- **Supporting Evidence:** `substitute_variables` escapes; `substitute_variables_text` does not; the fallback escapes manually; preview iframe is sandboxed.
- **Source Files:** [app/api/email_templates.py:58-105](../../app/api/email_templates.py#L58), [app/tasks/sop_tasks.py:374-402](../../app/tasks/sop_tasks.py#L374), [frontend/src/components/settings/EmailBuilder.vue:420-423](../../frontend/src/components/settings/EmailBuilder.vue#L420)
- **API References:** none
- **Database References:** email_templates

### Q4. Who is allowed to change email templates or run diagnostics?
- **Verified Answer:** Only the hardcoded legacy admin (`johndean@vin.com`). All template mutations and every email-debug endpoint call `require_admin`, which resolves admin solely by exact email match — there is no role-tier system active (`auth_users.role` exists but is not read by auth). Reading/resolving templates requires only a valid JWT.
- **Supporting Evidence:** `require_admin`/`is_admin` compare `user.email == LEGACY_ADMIN_EMAIL`; reads are CurrentUser-only.
- **Source Files:** [app/security/roles.py:62-92](../../app/security/roles.py#L62), [app/api/email_templates.py:223](../../app/api/email_templates.py#L223), [app/api/email_debug.py:50-53](../../app/api/email_debug.py#L50)
- **API References:** POST/PUT/DELETE /v1/email-templates, /v1/admin/email-debug/*
- **Database References:** none (auth_users.role exists but is unused by these gates)

---

## Administrator

### Q1. How do per-Type overrides work versus the default template?
- **Verified Answer:** There's at most one active template per (Session Type, stage, locale). A row with NULL `session_type_id` is the default for all Types. When you save against a real Type while viewing the default, a per-Type override row is created; that override wins for that Type. "Remove override · revert" soft-deletes the override and falls back to the default.
- **Supporting Evidence:** Resolution cascade (per_type then default); EmailBuilder's save/revert branching; unique index collapses NULL to `_default_`.
- **Source Files:** [app/api/email_templates.py:316-360](../../app/api/email_templates.py#L316), [frontend/src/components/settings/EmailBuilder.vue:114-202](../../frontend/src/components/settings/EmailBuilder.vue#L114), [migrations/048_email_templates.sql:51-53](../../migrations/048_email_templates.sql#L51)
- **API References:** POST/PUT/DELETE /v1/email-templates, POST /v1/email-templates/resolve
- **Database References:** email_templates

### Q2. Which stages have templates, and why is there no `complete_overdue`?
- **Verified Answer:** Eight stage-transition templates (prep, copy_draft, medical, copy_final, cms, captions, qa, complete) and seven deadline-overdue variants (the same minus complete). `complete` is terminal with SLA 0, so the deadline scan never flags it overdue and no `complete_overdue` template is seeded.
- **Supporting Evidence:** `_VALID_STAGES` lists both families; the overdue seed migration documents the terminal-stage exclusion.
- **Source Files:** [app/api/email_templates.py:118-125](../../app/api/email_templates.py#L118), [migrations/051_email_templates_overdue_seeds.sql:5-7](../../migrations/051_email_templates_overdue_seeds.sql#L5)
- **API References:** none
- **Database References:** email_templates

### Q3. How does the overdue template get matched if its stage_id isn't in the validator allowlist?
- **Verified Answer:** The async HTTP `/resolve` validates `stage_id` against `_VALID_STAGES` (which now includes the `*_overdue` IDs). The sync helper `resolve_template_sync` used by Celery deliberately does NOT validate — it trusts its caller and queries by raw `stage_id` like `prep_overdue`, so the deadline task finds the seeded row.
- **Supporting Evidence:** Sync resolver docstring + code skip validation; deadline task passes `f"{stage}_overdue"`.
- **Source Files:** [app/api/email_templates.py:365-385](../../app/api/email_templates.py#L365), [app/tasks/sop_tasks.py:362-365](../../app/tasks/sop_tasks.py#L362)
- **API References:** POST /v1/email-templates/resolve (async, validated)
- **Database References:** email_templates

### Q4. What happens if a template fails to resolve at send time?
- **Verified Answer:** The deadline sender falls back to inline f-string subject/body so a notification still goes out. This covers the case where migration 051 hasn't applied or an operator soft-deleted the overdue variant. A DB error during resolve is caught and also falls through to the fallback.
- **Supporting Evidence:** `if template: … else: inline f-strings`; resolve wrapped in try/except.
- **Source Files:** [app/tasks/sop_tasks.py:359-403](../../app/tasks/sop_tasks.py#L359)
- **API References:** none
- **Database References:** email_templates

### Q5. How do I send myself a test of the exact template I'm editing?
- **Verified Answer:** In the Email Builder, "Send test to my email" prompts for a recipient (prefilled with your address), substitutes sample variables client-side into subject + body, and posts the rendered content to the email-debug send endpoint — exercising the same SMTP path production uses.
- **Supporting Evidence:** `sendTest` substitutes `SAMPLE_VARS` and calls `emailDebug.send`.
- **Source Files:** [frontend/src/components/settings/EmailBuilder.vue:204-244](../../frontend/src/components/settings/EmailBuilder.vue#L204)
- **API References:** POST /v1/admin/email-debug/send
- **Database References:** email_attempts

### Q6. Are template deletes destructive?
- **Verified Answer:** No, they're soft deletes — `is_active = FALSE` — so the row is excluded from lists/resolves but still occupies the unique (type, stage, locale) slot. Each delete also writes an audit row.
- **Supporting Evidence:** DELETE sets `is_active = FALSE`; unique index is non-partial; audit insert on remove.
- **Source Files:** [app/api/email_templates.py:295-313](../../app/api/email_templates.py#L295), [migrations/048_email_templates.sql:46-50](../../migrations/048_email_templates.sql#L46)
- **API References:** DELETE /v1/email-templates/{id}
- **Database References:** email_templates, audit_events

---

## Power User

### Q1. What template variables are actually substituted in a real deadline send?
- **Verified Answer:** The deadline sender supplies: `session_code`, `session_title`, `assignee_first_name`, `stage`, `overdue_hours`, `editor_url`, `results_url` (alias of editor_url), and `session_id`. The builder's variable palette lists ~30 chips, but any variable the sender doesn't supply renders as empty string (missing keys substitute to "").
- **Supporting Evidence:** `template_vars` dict in the deadline task; substitution returns "" for missing keys; palette in EmailBuilder.
- **Source Files:** [app/tasks/sop_tasks.py:345-354](../../app/tasks/sop_tasks.py#L345), [app/api/email_templates.py:73-79](../../app/api/email_templates.py#L73), [frontend/src/components/settings/EmailBuilder.vue:256-263](../../frontend/src/components/settings/EmailBuilder.vue#L256)
- **API References:** none
- **Database References:** email_templates

### Q2. How is double-sending prevented when both Beat and a manual /diag/sop-check run at once?
- **Verified Answer:** A per-(session, stage) Postgres advisory lock (`pg_advisory_xact_lock`, keyed by an MD5 digest of "session::stage") wraps the throttle SELECT and the throttle-row INSERT in a single transaction, so two concurrent workers can't both pass the 23h check and both insert.
- **Supporting Evidence:** `_deadline_lock_key` + `pg_advisory_xact_lock` inside `engine.begin()`.
- **Source Files:** [app/tasks/sop_tasks.py:162-176](../../app/tasks/sop_tasks.py#L162), [app/tasks/sop_tasks.py:282-328](../../app/tasks/sop_tasks.py#L282)
- **API References:** POST /v1/diag/sop-check
- **Database References:** audit_events

### Q3. Why is the throttle window 23 hours, not 24?
- **Verified Answer:** Because the scan fires hourly and the intended cadence is roughly daily. 23h (rather than 24h) avoids an off-by-one where two consecutive daily Beat ticks fall on either side of a 24h boundary and skip a legitimate reminder. This is BR-004.
- **Supporting Evidence:** Inline BR-004 rationale comment.
- **Source Files:** [app/tasks/sop_tasks.py:297-311](../../app/tasks/sop_tasks.py#L297)
- **API References:** none
- **Database References:** audit_events

### Q4. Why don't subjects get HTML-escaped like bodies?
- **Verified Answer:** Subjects are RFC 5322 plain-text headers; mail clients render entity strings like `&#x27;` literally, so escaping a subject visibly corrupts it. The body is HTML and is escaped for XSS safety. Hence two functions: `substitute_variables` (escaping, body) and `substitute_variables_text` (no escaping, subject). The plain-text MIME alt part is generated by `_html_to_text`, which uses `html.unescape` to undo entity encoding.
- **Supporting Evidence:** Docstrings + the deadline task choosing the text variant for subject and HTML variant for body.
- **Source Files:** [app/api/email_templates.py:82-105](../../app/api/email_templates.py#L82), [app/tasks/sop_tasks.py:374-380](../../app/tasks/sop_tasks.py#L374), [app/tasks/sop_tasks.py:179-207](../../app/tasks/sop_tasks.py#L179)
- **API References:** none
- **Database References:** none

### Q5. What does a test send capture for debugging, and can I replay it?
- **Verified Answer:** A test send captures the full raw SMTP wire protocol (smtplib debuglevel=1 teed off stderr) into `email_attempts.smtp_log`, along with from/to/subject/result/latency/operator. In the UI, each attempt row has a "Retest" button that re-sends to the same recipient + subject.
- **Supporting Evidence:** `_send_with_wire_capture` + `_record_attempt`; EmailDebug `retest`.
- **Source Files:** [app/api/email_debug.py:154-188](../../app/api/email_debug.py#L154), [frontend/src/components/settings/EmailDebug.vue:151-156](../../frontend/src/components/settings/EmailDebug.vue#L151)
- **API References:** POST /v1/admin/email-debug/send, GET /v1/admin/email-debug/attempts
- **Database References:** email_attempts

---

## Source Verification
- **Files Used:** app/api/email_templates.py, app/api/email_debug.py, app/services/email.py, app/tasks/sop_tasks.py, app/tasks/celery_app.py, app/config.py, app/security/roles.py, app/api/diagnostics.py, migrations/030_email_attempts.sql, migrations/048_email_templates.sql, migrations/051_email_templates_overdue_seeds.sql, migrations/004_audit.sql, frontend/src/components/settings/EmailBuilder.vue, frontend/src/components/settings/EmailDebug.vue, frontend/src/services/api.ts
- **Components Used:** EmailBuilder.vue, EmailDebug.vue, SectionEmail.vue, SectionDiagnostics.vue
- **APIs Used:** /v1/email-templates (GET/POST/PUT/DELETE + /resolve), /v1/admin/email-debug/{config,connectivity,send,attempts}, /v1/diag/sop-check
- **Database Tables Used:** email_templates, email_attempts, audit_events, sop_state, sessions, session_types
- **Permission Logic Used:** JWT (CurrentUser) + LEGACY_ADMIN_EMAIL gate via require_admin/is_admin; role-based auth scaffold-only
- **Confidence Score:** High — every answer maps to a read line in current source; flags below note the two PARTIALLY IMPLEMENTED behaviors.
- **Evidence Links:** [config.py:110](../../app/config.py#L110), [sop_tasks.py:210-446](../../app/tasks/sop_tasks.py#L210), [email_templates.py:316-429](../../app/api/email_templates.py#L316), [email_debug.py:234-357](../../app/api/email_debug.py#L234), [roles.py:62-92](../../app/security/roles.py#L62)
