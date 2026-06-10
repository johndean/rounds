# Notifications & Email — Product Spec

> Module key: `notifications-email`. This document describes only what exists in the rounds.vin codebase as of the source read. Every claim is tied to a file:line reference. Aspirational or future-state behavior is excluded.

## Overview

The Notifications & Email module covers two distinct, code-verified surfaces:

1. **Email templates** — admin-editable HTML email templates keyed by `(session_type_id, stage_id, locale)`, with a CRUD API and a builder UI. There are two seeded families of templates: stage-transition templates (one per SOP stage) and deadline-overdue templates (one per non-terminal stage). See [email_templates.py](../../app/api/email_templates.py), [048_email_templates.sql](../../migrations/048_email_templates.sql), [051_email_templates_overdue_seeds.sql](../../migrations/051_email_templates_overdue_seeds.sql).
2. **Email diagnostics + send** — admin-only SMTP config check, connectivity probe, test send with raw-wire capture, and a paginated send-attempt ledger. See [email_debug.py](../../app/api/email_debug.py), [EmailDebug.vue](../../frontend/src/components/settings/EmailDebug.vue).

The one production send path that fires automatically today is the **SOP deadline-overdue email**, dispatched by the hourly Celery task `sop_check_deadlines_task` and gated behind a config flag that defaults OFF. See [sop_tasks.py:210](../../app/tasks/sop_tasks.py#L210) and [config.py:110](../../app/config.py#L110).

**PARTIALLY IMPLEMENTED:** Stage-transition emails (the eight templates seeded by migration 048) are NOT wired to any sender. The migration header states the firing trigger is out of scope ([048_email_templates.sql:24-26](../../migrations/048_email_templates.sql#L24)), and code search finds no caller that resolves a non-`_overdue` template and sends it. The only automatic sender resolves `stage_id = '<stage>_overdue'` ([sop_tasks.py:365](../../app/tasks/sop_tasks.py#L365)).

## Purpose

- Give an admin a way to author and preview the HTML email body + subject that gets sent to a stage assignee, with per-Session-Type overrides over a default-for-all-types row ([EmailBuilder.vue:1-16](../../frontend/src/components/settings/EmailBuilder.vue#L1)).
- Notify the assignee of an SOP stage when that stage sits past its SLA window ([sop_tasks.py:210](../../app/tasks/sop_tasks.py#L210), [sop_tasks.py:485-547](../../app/tasks/sop_tasks.py#L485)).
- Let an admin diagnose SMTP problems without sending real assignee mail: config presence check, STARTTLS/LOGIN/NOOP/QUIT probe, controlled test send, and an audit ledger of every attempt ([email_debug.py:10-17](../../app/api/email_debug.py#L10)).

## User Value

- **Operations/admin:** verify SMTP is reachable and correctly configured before turning on automatic sends, and confirm a specific recipient received (or failed to receive) mail via the attempts ledger ([email_debug.py:307](../../app/api/email_debug.py#L307), [EmailDebug.vue:281-305](../../frontend/src/components/settings/EmailDebug.vue#L281)).
- **Admin:** tailor the wording of stage and overdue notifications per Session Type without a code deploy ([EmailBuilder.vue:114-177](../../frontend/src/components/settings/EmailBuilder.vue#L114)).
- **Stage assignee:** receives a deadline-overdue email (when the feature flag is on) telling them which session and stage is past SLA and by how many hours, with a direct link to the editor ([051_email_templates_overdue_seeds.sql:34-36](../../migrations/051_email_templates_overdue_seeds.sql#L34), [sop_tasks.py:340-354](../../app/tasks/sop_tasks.py#L340)).

## Navigation

Both UI surfaces live inside the Settings page ([SettingsView.vue:74-89](../../frontend/src/views/SettingsView.vue#L74)):

- **Settings → Email templates** renders `SectionEmail`, which shows a home view with a header CTA "Open builder" that swaps in `EmailBuilder` ([SectionEmail.vue:10-20](../../frontend/src/components/settings/SectionEmail.vue#L10)).
- **Settings → Diagnostics** renders `SectionDiagnostics`. Its first card has an "Open test email page →" button that swaps the view to `EmailDebug` ([SectionDiagnostics.vue:14](../../frontend/src/components/settings/SectionDiagnostics.vue#L14), [SectionDiagnostics.vue:44](../../frontend/src/components/settings/SectionDiagnostics.vue#L44), [SectionDiagnostics.vue:54](../../frontend/src/components/settings/SectionDiagnostics.vue#L54)).

Note: the email diagnostics page (`EmailDebug`) is reached through the **Diagnostics** section, NOT through the **Email templates** section. The `SectionEmail` "ADMIN · TEST EMAIL" card is descriptive copy only and has no button ([SectionEmail.vue:28-34](../../frontend/src/components/settings/SectionEmail.vue#L28)).

Section visibility is controlled client-side by `SettingsView`'s nav list; **NOT VERIFIED IN CODE** that the Email/Diagnostics nav entries are themselves hidden from non-admins (the section read covered `SettingsView.vue:60-91`; the nav list source was not read). The server enforces admin on every mutating/diagnostic endpoint regardless.

## Screens

### 1. Email templates home (`SectionEmail`)

A `SettingsHeader` titled "Email templates" with an "Open builder" CTA, plus two static info cards ("Stage triggers via Types matrix" and "ADMIN · TEST EMAIL"). The info cards carry no actions ([SectionEmail.vue:13-35](../../frontend/src/components/settings/SectionEmail.vue#L13)).

### 2. Email Template Builder (`EmailBuilder`)

Two-pane editor ([EmailBuilder.vue:328-443](../../frontend/src/components/settings/EmailBuilder.vue#L328)):

- **Type selector** in the subnav: an `<option value="">default (applies to every Type)</option>` plus one option per live Session Type fetched from `/v1/settings/types` ([EmailBuilder.vue:337-345](../../frontend/src/components/settings/EmailBuilder.vue#L337), [EmailBuilder.vue:102-110](../../frontend/src/components/settings/EmailBuilder.vue#L102)).
- **Stage tabs:** 15 tabs — 8 stage-transition (`prep`, `copy_draft`, `medical`, `copy_final`, `cms`, `captions`, `qa`, `complete`) and 7 deadline-overdue (`*_overdue`, no `complete_overdue`) ([EmailBuilder.vue:32-52](../../frontend/src/components/settings/EmailBuilder.vue#L32)).
- **Subject** input and **HTML body** textarea ([EmailBuilder.vue:366-386](../../frontend/src/components/settings/EmailBuilder.vue#L366)).
- **Actions:** "Save default" / "Save for this Type", "Remove override · revert" (enabled only when current row resolved `per_type`), "Send test to my email" ([EmailBuilder.vue:387-410](../../frontend/src/components/settings/EmailBuilder.vue#L387)).
- **Preview pane:** rendered subject + a sandboxed `<iframe srcdoc>` of the HTML body with sample variables substituted, plus a clickable variable-chip palette grouped into SESSION / COUNTS / STAGE / ASSIGNEE / ACTOR / LINKS ([EmailBuilder.vue:412-441](../../frontend/src/components/settings/EmailBuilder.vue#L412), [EmailBuilder.vue:256-263](../../frontend/src/components/settings/EmailBuilder.vue#L256)).
- A "Source: Default | Per-Type override | —" indicator shows where the currently displayed row resolved from ([EmailBuilder.vue:321-325](../../frontend/src/components/settings/EmailBuilder.vue#L321)).

### 3. Test Email · Diagnostics (`EmailDebug`)

Five sections, all wired to `/v1/admin/email-debug/*` ([EmailDebug.vue:3-15](../../frontend/src/components/settings/EmailDebug.vue#L3)):

1. **SMTP Config** — one row per env var (`SMTP_HOST/PORT/FROM/USERNAME/PASSWORD`); username/password show only presence, never values ([EmailDebug.vue:215-230](../../frontend/src/components/settings/EmailDebug.vue#L215), [email_debug.py:64-78](../../app/api/email_debug.py#L64)).
2. **Connectivity Test** — table of connect/starttls/login/noop/quit with ok/latency/error ([EmailDebug.vue:232-260](../../frontend/src/components/settings/EmailDebug.vue#L232)).
3. **Send Test Email** — To / Subject / Body fields and a Send button. The "To" field defaults to `johndean@vin.com` ([EmailDebug.vue:36-38](../../frontend/src/components/settings/EmailDebug.vue#L36), [EmailDebug.vue:262-274](../../frontend/src/components/settings/EmailDebug.vue#L262)).
4. **Recent Attempts** — newest-first table with a per-row "Retest" button ([EmailDebug.vue:281-305](../../frontend/src/components/settings/EmailDebug.vue#L281)).
5. **Event Log** — in-memory client log of every API call this session, plus a "Copy diagnostic bundle" button (config + last connectivity + 5 most-recent attempts; never includes username/password values) ([EmailDebug.vue:161-170](../../frontend/src/components/settings/EmailDebug.vue#L161), [EmailDebug.vue:307-318](../../frontend/src/components/settings/EmailDebug.vue#L307)).
6. A **403 banner** is shown if `/config` returns 403 ([EmailDebug.vue:193-206](../../frontend/src/components/settings/EmailDebug.vue#L193)).

## User Flows

### Edit a template (admin)

1. Open Settings → Email templates → Open builder.
2. Select a Type (or leave default) and a stage tab. The builder calls `POST /v1/email-templates/resolve` and loads the resolved subject/body ([EmailBuilder.vue:74-100](../../frontend/src/components/settings/EmailBuilder.vue#L74)).
3. Edit subject/body, optionally inserting variables via chips ([EmailBuilder.vue:308-315](../../frontend/src/components/settings/EmailBuilder.vue#L308)).
4. Click Save:
   - Default selected + default row resolved → `PUT` the existing row ([EmailBuilder.vue:121-128](../../frontend/src/components/settings/EmailBuilder.vue#L121)).
   - Real Type selected + per-Type row already resolved for this Type → `PUT` that row ([EmailBuilder.vue:144-153](../../frontend/src/components/settings/EmailBuilder.vue#L144)).
   - Real Type selected but currently showing the default → `POST` a new per-Type override ([EmailBuilder.vue:154-167](../../frontend/src/components/settings/EmailBuilder.vue#L154)).
5. "Remove override · revert" deletes the per-Type row (soft-delete) and re-resolves to the default ([EmailBuilder.vue:179-202](../../frontend/src/components/settings/EmailBuilder.vue#L179)).

### Send a template test (admin, from EmailBuilder)

Prompts for a recipient (prefilled with the logged-in user's email), substitutes sample variables client-side, then calls `POST /v1/admin/email-debug/send` with the rendered subject + html_body ([EmailBuilder.vue:204-244](../../frontend/src/components/settings/EmailBuilder.vue#L204)).

### Run SMTP diagnostics (admin)

Open Settings → Diagnostics → Open test email page. `EmailDebug` auto-loads config + attempts on mount; the admin can run a connectivity probe and a test send ([EmailDebug.vue:173-177](../../frontend/src/components/settings/EmailDebug.vue#L173)).

### Automatic deadline-overdue email (system)

1. Celery Beat fires `rounds.tasks.sop.check_deadlines` hourly (also invocable via `/v1/diag/sop-check`) ([celery_app.py:84-88](../../app/tasks/celery_app.py#L84), [diagnostics.py:334-343](../../app/api/diagnostics.py#L334)).
2. The task scans `sop_state` for stages past their SLA (per-stage default hours in `_DEFAULT_SLA_HOURS`, `complete` = 0 = skipped) ([sop_tasks.py:36-45](../../app/tasks/sop_tasks.py#L36), [sop_tasks.py:485-499](../../app/tasks/sop_tasks.py#L485)).
3. For each overdue stage it always emits a WS `sop.deadline_warning` event and an `audit_events` `sop.deadline_warning` row ([sop_tasks.py:500-534](../../app/tasks/sop_tasks.py#L500)).
4. If `SOP_DEADLINE_EMAIL_ENABLED` is True, it calls `_maybe_send_deadline_email`, which resolves the assignee, throttle-checks, resolves the `<stage>_overdue` template (falling back to inline f-strings), and sends via `send_smtp_email` ([sop_tasks.py:536-545](../../app/tasks/sop_tasks.py#L536), [sop_tasks.py:210-404](../../app/tasks/sop_tasks.py#L210)).

## Business Rules

- **One active template per `(session_type_id, stage_id, locale)`.** Enforced by a unique index that collapses NULL `session_type_id` to the literal `'_default_'` so multiple defaults can't coexist ([048_email_templates.sql:51-53](../../migrations/048_email_templates.sql#L51)).
- **Resolution cascade:** per-Type row wins; else the default (`session_type_id IS NULL`) row; else 404 (async) / `None` (sync) ([email_templates.py:316-360](../../app/api/email_templates.py#L316), [email_templates.py:365-429](../../app/api/email_templates.py#L365)).
- **Soft delete:** DELETE sets `is_active = FALSE`; soft-deleted rows still occupy the unique slot (non-partial index), so reuse requires hard-delete handling ([email_templates.py:295-313](../../app/api/email_templates.py#L295), [048_email_templates.sql:46-50](../../migrations/048_email_templates.sql#L46)).
- **Valid stages for the HTTP CRUD surface:** the 8 transition stages + 7 `*_overdue` stages. The sync resolver does NOT validate against this set on purpose, so Celery can query overdue stage IDs ([email_templates.py:118-125](../../app/api/email_templates.py#L118), [email_templates.py:377-385](../../app/api/email_templates.py#L377)).
- **BR-004 — deadline-email throttle:** at most one deadline email per `(session_id, stage)` per 23 hours; the throttle key is an `audit_events` row of kind `sop.deadline_email_sent` or `sop.deadline_email_failed` ([sop_tasks.py:236-238](../../app/tasks/sop_tasks.py#L236), [sop_tasks.py:285-311](../../app/tasks/sop_tasks.py#L285)).
- **BR-005 — zero-hour grace:** there is NO grace period; an email fires the moment `overdue_hours > 0`. BR-004 is the only repeat-send guard ([sop_tasks.py:306-309](../../app/tasks/sop_tasks.py#L306)).
- **Deadline emails skip silently** when: the stage has no assignee entry, the assignee is a group (`group:NAME`), the assignee value isn't an email address, or a send/failure row already exists within 23h ([sop_tasks.py:240-247](../../app/tasks/sop_tasks.py#L240), [sop_tasks.py:271-273](../../app/tasks/sop_tasks.py#L271)).
- **Test send has no rate limit** by design — admins iterate on templates ([email_debug.py:237-238](../../app/api/email_debug.py#L237)).
- **`complete` stage has no overdue variant** (terminal, SLA = 0) ([email_templates.py:121-122](../../app/api/email_templates.py#L121), [051_email_templates_overdue_seeds.sql:5-7](../../migrations/051_email_templates_overdue_seeds.sql#L5)).

## Validation Rules

- `EmailTemplateCreate`: `stage_id` non-empty and must be in `_VALID_STAGES` (else 400 `INVALID_STAGE`); `locale` 2–10 chars (default `en-US`); `subject` 1–300 chars; `body` 1–200,000 chars ([email_templates.py:128-134](../../app/api/email_templates.py#L128), [email_templates.py:224-228](../../app/api/email_templates.py#L224)).
- `EmailTemplatePatch`: all fields optional; empty patch → 400 `NO_CHANGES` ([email_templates.py:137-141](../../app/api/email_templates.py#L137), [email_templates.py:272-276](../../app/api/email_templates.py#L272)).
- Duplicate `(type, stage, locale)` on create → 409 `DUPLICATE_TEMPLATE` ([email_templates.py:244-252](../../app/api/email_templates.py#L244)).
- `SendRequest`: `to` 3–255 chars and must match `^[^@\s]+@[^@\s]+\.[^@\s]+$` (else 400); `subject` ≤200; `text_body` ≤8000; `html_body` ≤32000 ([email_debug.py:56-60](../../app/api/email_debug.py#L56), [email_debug.py:242-244](../../app/api/email_debug.py#L242)).
- `GET /attempts` query params: `limit` 1–500 (default 50), `result` must match `^(sent|failed)$`, `since_hours` 1–720 ([email_debug.py:308-313](../../app/api/email_debug.py#L308)).
- Client-side, EmailBuilder's test-send recipient is re-validated against `/^\S+@\S+\.\S+$/` ([EmailBuilder.vue:220](../../frontend/src/components/settings/EmailBuilder.vue#L220)).

## States

### Template states

- **Active** (`is_active = TRUE`) — resolvable/listable.
- **Soft-deleted** (`is_active = FALSE`) — excluded from list/get/resolve but still occupies the unique slot ([email_templates.py:178](../../app/api/email_templates.py#L178), [email_templates.py:305-307](../../app/api/email_templates.py#L305)).
- **Resolved-from:** `per_type` or `default` discriminator added by the resolve endpoints ([email_templates.py:343](../../app/api/email_templates.py#L343), [email_templates.py:354](../../app/api/email_templates.py#L354)).

### Send-attempt states (email_attempts)

- `result IN ('sent', 'failed')` — CHECK-constrained ([030_email_attempts.sql:31](../../migrations/030_email_attempts.sql#L31)).
- `trigger IN ('stage_notification', 'debug_test', 'template_test')` — CHECK-constrained. In practice only `debug_test` is written by the send endpoint ([030_email_attempts.sql:32](../../migrations/030_email_attempts.sql#L32), [email_debug.py:276](../../app/api/email_debug.py#L276), [email_debug.py:293](../../app/api/email_debug.py#L293)).

### Deadline-email states (audit_events)

- `sop.deadline_warning` — every overdue stage, always ([sop_tasks.py:521](../../app/tasks/sop_tasks.py#L521)).
- `sop.deadline_email_sent` — inserted to claim the throttle slot before the SMTP attempt; left as-is on success ([sop_tasks.py:312-328](../../app/tasks/sop_tasks.py#L312), [sop_tasks.py:412-425](../../app/tasks/sop_tasks.py#L412)).
- `sop.deadline_email_failed` — the same row's kind is UPDATEd on SMTP failure (no second row) ([sop_tasks.py:426-444](../../app/tasks/sop_tasks.py#L426)).

## Dependencies

- **SMTP via env vars** `SMTP_HOST / SMTP_PORT / SMTP_FROM / SMTP_USERNAME / SMTP_PASSWORD`. Same configuration covers diagnostic and operational mail ([email.py:5-8](../../app/services/email.py#L5), [email_debug.py:69-77](../../app/api/email_debug.py#L69)). Per CLAUDE.md, `SMTP_*` is shared with MIC and sends as `mic@design.veterinary.support`.
- **`session_types` table** — per-Type templates FK to it (`ON DELETE CASCADE`) ([048_email_templates.sql:30](../../migrations/048_email_templates.sql#L30)).
- **`sessions` table** — `email_attempts.sop_session_id` FKs it (`ON DELETE SET NULL`); the deadline task reads `sessions.title/code/session_type_id` ([030_email_attempts.sql:23](../../migrations/030_email_attempts.sql#L23), [sop_tasks.py:256-264](../../app/tasks/sop_tasks.py#L256)).
- **`sop_state` table** — source of overdue scan + assignees JSONB ([sop_tasks.py:474-483](../../app/tasks/sop_tasks.py#L474), [sop_tasks.py:256-271](../../app/tasks/sop_tasks.py#L256)).
- **`audit_events` table** — throttle ledger + audit trail for template CRUD and deadline emails ([004_audit.sql:3-11](../../migrations/004_audit.sql#L3)).
- **Celery + Celery Beat** — schedules the hourly deadline scan ([celery_app.py:84-88](../../app/tasks/celery_app.py#L84)).
- **WebSocket bridge** — `publish_ws_event_sync` for the `sop.deadline_warning` event ([sop_tasks.py:501-510](../../app/tasks/sop_tasks.py#L501)).

## Error Handling

- **CRUD errors** surface as structured `{code, message}` detail bodies: `NOT_FOUND` (404), `INVALID_STAGE` (400), `NO_CHANGES` (400), `DUPLICATE_TEMPLATE` (409), `ADMIN_ONLY` (403) ([email_templates.py:213](../../app/api/email_templates.py#L213), [email_templates.py:224](../../app/api/email_templates.py#L224), [email_templates.py:246](../../app/api/email_templates.py#L246), [roles.py:113-117](../../app/security/roles.py#L113)). EmailBuilder extracts the `.message` for its toast ([EmailBuilder.vue:246-252](../../frontend/src/components/settings/EmailBuilder.vue#L246)).
- **SMTP missing config:** `/connectivity` and `/send` return 400 "SMTP_HOST not configured" ([email_debug.py:90-91](../../app/api/email_debug.py#L90), [email_debug.py:253-254](../../app/api/email_debug.py#L253)).
- **Connectivity probe** is fail-fast: each step returns `{ok, latency_ms, error}`; a failed step short-circuits remaining steps to `ok: null` (skipped) ([email_debug.py:96-150](../../app/api/email_debug.py#L96)).
- **Send failure** does NOT raise — it returns `{sent: false, error, smtp_log}` and records a `failed` row in `email_attempts` ([email_debug.py:269-286](../../app/api/email_debug.py#L269)).
- **`_record_attempt` never raises** — an insert failure is logged as a non-fatal warning ([email_debug.py:198-230](../../app/api/email_debug.py#L198)).
- **`send_smtp_email` never raises** — returns `{ok: False, error, latency_ms}` on missing host, malformed `to`, or smtplib errors ([email.py:41-84](../../app/services/email.py#L41)).
- **Deadline path is defensive:** template-resolve errors fall back to inline f-strings; throttle-claim failures log+skip (drop one notification rather than double-send); audit-update failures are logged non-fatally ([sop_tasks.py:359-403](../../app/tasks/sop_tasks.py#L359), [sop_tasks.py:329-336](../../app/tasks/sop_tasks.py#L329), [sop_tasks.py:445-446](../../app/tasks/sop_tasks.py#L445)).

## Permissions

Authorization here is **JWT presence + a hardcoded legacy-admin-email gate**. There is no active role-tier system.

- All `/v1/email-templates` **read** endpoints (`GET ""`, `GET /{id}`, `POST /resolve`) require only a logged-in user (`CurrentUser`), no admin check ([email_templates.py:165-167](../../app/api/email_templates.py#L165), [email_templates.py:205-206](../../app/api/email_templates.py#L205), [email_templates.py:316-319](../../app/api/email_templates.py#L316)).
- All `/v1/email-templates` **mutations** (`POST`, `PUT`, `DELETE`) call `require_admin(user)` ([email_templates.py:223](../../app/api/email_templates.py#L223), [email_templates.py:266](../../app/api/email_templates.py#L266), [email_templates.py:298](../../app/api/email_templates.py#L298)).
- All `/v1/admin/email-debug/*` endpoints call `_require_email_debug_admin`, which delegates to `require_admin` ([email_debug.py:50-53](../../app/api/email_debug.py#L50), invoked at [68](../../app/api/email_debug.py#L68), [87](../../app/api/email_debug.py#L87), [239](../../app/api/email_debug.py#L239), [316](../../app/api/email_debug.py#L316)).
- `require_admin` / `is_admin` resolve admin as **`user.email == LEGACY_ADMIN_EMAIL` (`"johndean@vin.com"`)**, case- and whitespace-sensitive. The `role` parameter exists but is never passed by any of these callers, and `get_current_user` does not load `auth_users.role` ([roles.py:62-92](../../app/security/roles.py#L62), [roles.py:10-19](../../app/security/roles.py#L10)). Role-based auth is scaffold-only.
- Client-side, `EmailDebug` shows a 403 banner if the server rejects `/config` ([EmailDebug.vue:64-66](../../frontend/src/components/settings/EmailDebug.vue#L64), [EmailDebug.vue:193-206](../../frontend/src/components/settings/EmailDebug.vue#L193)). The router-level `adminOnly` guard at [router/index.ts:63](../../frontend/src/router/index.ts#L63) gates other routes (e.g. help articles), not the Settings page itself.

## Reporting Impacts

- **`email_attempts`** is a queryable send ledger: timestamp, from/to, subject, trigger, session, stage, result, error, latency, raw SMTP wire log, operator email. Indexed on `attempted_at DESC`, `to_address`, `sop_session_id`, `result` ([030_email_attempts.sql:16-38](../../migrations/030_email_attempts.sql#L16)). Surfaced in the UI via `GET /attempts` ([EmailDebug.vue:286-301](../../frontend/src/components/settings/EmailDebug.vue#L286)).
- **`audit_events`** records template CRUD (kinds `settings.email_templates.add|update|remove`) and deadline-email outcomes (kinds `sop.deadline_warning|deadline_email_sent|deadline_email_failed`), the latter with `details.overdue_hours`, `details.recipient`, `details.latency_ms` ([email_templates.py:253-256](../../app/api/email_templates.py#L253), [sop_tasks.py:312-328](../../app/tasks/sop_tasks.py#L312), [sop_tasks.py:412-444](../../app/tasks/sop_tasks.py#L412)).
- No aggregate dashboards or scheduled reports for email exist in code — these tables are the raw reporting substrate only. **IMPLEMENTATION NOT FOUND** for any email reporting view beyond the Recent Attempts table.

## Audit Requirements

- Template create/update/delete each write an `audit_events` row with `actor_email = user.email` and a `summary` naming the stage and type ([email_templates.py:253-256](../../app/api/email_templates.py#L253), [email_templates.py:287-290](../../app/api/email_templates.py#L287), [email_templates.py:308-311](../../app/api/email_templates.py#L308)).
- Every test send (success or failure) writes an `email_attempts` row including `operator_email` and the full raw SMTP wire log ([email_debug.py:273-295](../../app/api/email_debug.py#L273)).
- Deadline emails write/update an `audit_events` row. **Recipient masking:** the human-readable `summary` carries a masked address (`jan***@vin.com`); the full address lives only in `details.recipient` for operator forensics ([sop_tasks.py:232-234](../../app/tasks/sop_tasks.py#L232), [sop_tasks.py:144-159](../../app/tasks/sop_tasks.py#L144), [sop_tasks.py:320-326](../../app/tasks/sop_tasks.py#L320)).

## Data Relationships

- `email_templates.session_type_id` → `session_types.id` (`ON DELETE CASCADE`); NULL = default-for-all-types ([048_email_templates.sql:30](../../migrations/048_email_templates.sql#L30)).
- `email_attempts.sop_session_id` → `sessions.id` (`ON DELETE SET NULL`) ([030_email_attempts.sql:23](../../migrations/030_email_attempts.sql#L23)).
- `audit_events.session_id` → `sessions.id` (`ON DELETE SET NULL`) ([004_audit.sql:5](../../migrations/004_audit.sql#L5)).
- Deadline send reads assignee from `sop_state.assignees` JSONB keyed by stage; SLA from `sop_state.sla_target_hours` JSONB ([sop_tasks.py:256-271](../../app/tasks/sop_tasks.py#L256), [sop_tasks.py:489-492](../../app/tasks/sop_tasks.py#L489)).

## Known Constraints

- **Stage-transition emails are not auto-sent.** Migration 048 seeds 8 transition templates but no code path resolves+sends them automatically; only the `*_overdue` variants are wired ([048_email_templates.sql:24-26](../../migrations/048_email_templates.sql#L24), [sop_tasks.py:365](../../app/tasks/sop_tasks.py#L365)). PARTIALLY IMPLEMENTED.
- **Deadline emails are OFF by default.** `SOP_DEADLINE_EMAIL_ENABLED` defaults `False`; with it off, overdue stages still produce WS + `sop.deadline_warning` audit rows but no email ([config.py:110](../../app/config.py#L110), [sop_tasks.py:542](../../app/tasks/sop_tasks.py#L542)).
- **Group assignees are unsupported.** A `group:NAME` assignee is skipped — no per-group roster expansion exists ([sop_tasks.py:271-273](../../app/tasks/sop_tasks.py#L271), [sop_tasks.py:242-243](../../app/tasks/sop_tasks.py#L242)).
- **Locale is effectively `en-US` only.** Every seed row is `en-US`; no other locale is seeded ([048_email_templates.sql:64-90](../../migrations/048_email_templates.sql#L64), [051_email_templates_overdue_seeds.sql:32-55](../../migrations/051_email_templates_overdue_seeds.sql#L32)).
- **Soft-deleted rows occupy the unique slot.** Recreating a deleted `(type, stage, locale)` requires the runtime to compensate (non-partial unique index) ([048_email_templates.sql:46-50](../../migrations/048_email_templates.sql#L46)).
- **EmailBuilder client substitution palette is broader than the deadline sender supports.** The builder offers ~30 variable chips, but the deadline sender supplies only ~8 keys; unmatched `{{ vars }}` render as empty string at send time ([EmailBuilder.vue:256-263](../../frontend/src/components/settings/EmailBuilder.vue#L256), [sop_tasks.py:345-354](../../app/tasks/sop_tasks.py#L345), [email_templates.py:73-79](../../app/api/email_templates.py#L73)).
- **Variable substitution is not Jinja** — a regex over `{{ var }}` with no control flow; missing keys substitute as empty string ([email_templates.py:43-79](../../app/api/email_templates.py#L43)).

## Source Verification
- **Files Used:** app/api/email_templates.py, app/api/email_debug.py, app/services/email.py, app/tasks/sop_tasks.py, app/tasks/celery_app.py, app/config.py, app/security/roles.py, app/main.py, migrations/004_audit.sql, migrations/030_email_attempts.sql, migrations/048_email_templates.sql, migrations/051_email_templates_overdue_seeds.sql, frontend/src/components/settings/SectionEmail.vue, frontend/src/components/settings/EmailBuilder.vue, frontend/src/components/settings/EmailDebug.vue, frontend/src/components/settings/SectionDiagnostics.vue, frontend/src/views/SettingsView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** SectionEmail.vue, EmailBuilder.vue, EmailDebug.vue, SectionDiagnostics.vue, SettingsView.vue
- **APIs Used:** GET/POST/PUT/DELETE /v1/email-templates, POST /v1/email-templates/resolve, GET /v1/admin/email-debug/config, POST /v1/admin/email-debug/connectivity, POST /v1/admin/email-debug/send, GET /v1/admin/email-debug/attempts, POST /v1/diag/sop-check
- **Database Tables Used:** email_templates, email_attempts, audit_events, session_types, sessions, sop_state
- **Permission Logic Used:** JWT (CurrentUser) + LEGACY_ADMIN_EMAIL gate (require_admin / is_admin); reads require JWT only; role-based auth is scaffold-only
- **Confidence Score:** High — all surfaces, routes, columns, and flags read directly from current code; the only unread item is the Settings nav list visibility (flagged NOT VERIFIED IN CODE).
- **Evidence Links:** [email_templates.py:316-360](../../app/api/email_templates.py#L316), [email_debug.py:234-303](../../app/api/email_debug.py#L234), [sop_tasks.py:210-404](../../app/tasks/sop_tasks.py#L210), [config.py:110](../../app/config.py#L110), [roles.py:62-92](../../app/security/roles.py#L62), [048_email_templates.sql:28-90](../../migrations/048_email_templates.sql#L28)
