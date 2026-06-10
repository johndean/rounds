# Notifications & Email — Technical Spec

> Module key: `notifications-email`. Code-verified against the rounds.vin repo. Path references are relative to this file (`docs/technical/`), so repo-root files are reached with `../../`.

## Architecture

Three cooperating layers:

1. **Template store + CRUD** (`app/api/email_templates.py`, mounted at `/v1/email-templates`). Raw-SQL CRUD over the `email_templates` table (migration 048), plus a `POST /resolve` endpoint and a sync helper `resolve_template_sync` for non-HTTP callers ([email_templates.py:35](../../app/api/email_templates.py#L35), [email_templates.py:365](../../app/api/email_templates.py#L365)).
2. **SMTP diagnostics + send** (`app/api/email_debug.py`, mounted at `/v1/admin/email-debug`). Config presence, connectivity probe, test send with raw-wire capture, and an attempts ledger ([email_debug.py:44](../../app/api/email_debug.py#L44)).
3. **Operational send** — `app/services/email.py::send_smtp_email` is the shared sync sender, called by the deadline path in `app/tasks/sop_tasks.py`. SMTP configuration is a single set of env vars used by both diagnostic and operational mail ([email.py:33](../../app/services/email.py#L33), [email.py:5-8](../../app/services/email.py#L5)).

Both API routers are registered in `app/main.py` ([main.py:228-229](../../app/main.py#L228)). The frontend talks to them through typed wrappers in `frontend/src/services/api.ts` (`emailTemplatesApi`, `emailDebug`) ([api.ts:916](../../frontend/src/services/api.ts#L916), [api.ts:1011](../../frontend/src/services/api.ts#L1011)).

Data flow for the live automatic send:

```
Celery Beat (hourly)  ─►  sop_check_deadlines_task
   scan sop_state past SLA  ─►  WS sop.deadline_warning + audit sop.deadline_warning
   if SOP_DEADLINE_EMAIL_ENABLED:
       _maybe_send_deadline_email
          resolve assignee (sop_state.assignees)
          advisory-lock + 23h throttle (audit_events)
          resolve_template_sync(stage_id='<stage>_overdue')  ──►  email_templates
          substitute_variables(_text)  ──►  send_smtp_email  ──►  SMTP
          update audit row -> sent | failed
```
([celery_app.py:84-88](../../app/tasks/celery_app.py#L84), [sop_tasks.py:455-549](../../app/tasks/sop_tasks.py#L455), [sop_tasks.py:210-446](../../app/tasks/sop_tasks.py#L210))

## Frontend Components

- **`SectionEmail.vue`** — home/builder toggle (`view: 'home' | 'builder'`); renders `EmailBuilder` when in builder mode ([SectionEmail.vue:10-14](../../frontend/src/components/settings/SectionEmail.vue#L10)).
- **`EmailBuilder.vue`** — the editor. Local state: `types`, `selectedTypeId` (`''` = default), `stage`, `current` (`EmailTemplate | null`), `resolvedFrom`, `subject`, `body`, plus `loading/saving/sending` flags ([EmailBuilder.vue:54-72](../../frontend/src/components/settings/EmailBuilder.vue#L54)). Key methods: `loadResolved` (calls resolve), `saveForType`, `revertToDefault`, `sendTest`, `substituteVars` (client-side preview substitution) ([EmailBuilder.vue:74-244](../../frontend/src/components/settings/EmailBuilder.vue#L74), [EmailBuilder.vue:298-302](../../frontend/src/components/settings/EmailBuilder.vue#L298)). Watches `[stage, selectedTypeId]` to re-resolve ([EmailBuilder.vue:112](../../frontend/src/components/settings/EmailBuilder.vue#L112)).
- **`EmailDebug.vue`** — five-section diagnostics page. State: `cfg`, `connectivity`, `attempts`, `eventLog`, `forbidden`, and a send-test form (`toAddress/subject/body`) ([EmailDebug.vue:24-38](../../frontend/src/components/settings/EmailDebug.vue#L24)). Methods: `loadConfig`, `testSmtp`, `sendTest`, `loadAttempts`, `retest`, `copyBundle` ([EmailDebug.vue:56-170](../../frontend/src/components/settings/EmailDebug.vue#L56)).
- **`SectionDiagnostics.vue`** — hosts `EmailDebug` behind the "Open test email page →" button (`view: 'home' | 'test' | 'gcs'`) ([SectionDiagnostics.vue:14](../../frontend/src/components/settings/SectionDiagnostics.vue#L14), [SectionDiagnostics.vue:44-54](../../frontend/src/components/settings/SectionDiagnostics.vue#L44)).
- **`SettingsView.vue`** — routes `active === 'email'` → `SectionEmail` and `active === 'diagnostics'` → `SectionDiagnostics` ([SettingsView.vue:84-86](../../frontend/src/views/SettingsView.vue#L84)).

## Backend Services

- **`app/services/email.py::send_smtp_email(to, subject, text_body, html_body=None, *, from_email=None) -> EmailResult`** — sync, never raises. Builds a `multipart/alternative` MIME message, STARTTLS, optional LOGIN, sendmail. Returns `{ok, error, latency_ms}` ([email.py:33-84](../../app/services/email.py#L33)). Reads `SMTP_HOST/PORT/USERNAME/PASSWORD/FROM` from env; `from_email` falls back to `SMTP_FROM` then `rounds-noreply@vin.com` ([email.py:52-62](../../app/services/email.py#L52)).
- **`email_templates.substitute_variables(template_str, variables)`** — regex `{{ var }}` replace with `html.escape(..., quote=True)` on values (XSS-safe, for HTML bodies); missing keys → `""` ([email_templates.py:46-79](../../app/api/email_templates.py#L46)).
- **`email_templates.substitute_variables_text(...)`** — same regex, NO escaping; for plain-text contexts like subjects ([email_templates.py:82-105](../../app/api/email_templates.py#L82)).
- **`email_templates.resolve_template_sync(conn, *, session_type_id=None, stage_id, locale='en-US')`** — sync resolver for Celery; returns the resolved dict (with `resolved_from`) or `None`; does NOT validate `stage_id` against `_VALID_STAGES` ([email_templates.py:365-429](../../app/api/email_templates.py#L365)).
- **`email_debug._send_with_wire_capture(...)`** — sets `smtplib` debuglevel=1 and tees `sys.stderr` to capture the raw wire chatter into a string ([email_debug.py:154-188](../../app/api/email_debug.py#L154)).
- **`email_debug._record_attempt(...)`** — inserts an `email_attempts` row; never raises ([email_debug.py:191-230](../../app/api/email_debug.py#L191)).
- **`sop_tasks._maybe_send_deadline_email(engine, session_id, stage, overdue_hours)`** — assignee lookup, advisory-lock throttle, template resolve + substitute (or inline fallback), send, audit update ([sop_tasks.py:210-446](../../app/tasks/sop_tasks.py#L210)).
- **`sop_tasks._mask_email`, `_deadline_lock_key`, `_html_to_text`** — recipient masking for audit summaries, deterministic MD5-based advisory-lock key, and HTML→text for the plain-text MIME alt part ([sop_tasks.py:144-207](../../app/tasks/sop_tasks.py#L144)).

## APIs

### `/v1/email-templates` ([email_templates.py](../../app/api/email_templates.py))

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `""` | JWT | Filters: `session_type_id`, `stage_id`, `include_defaults` (default true). Orders `session_type_id NULLS FIRST, stage_id, locale` ([email_templates.py:165-202](../../app/api/email_templates.py#L165)). |
| GET | `/{template_id}` | JWT | 404 if not active ([email_templates.py:205-214](../../app/api/email_templates.py#L205)). |
| POST | `""` (201) | admin | `INVALID_STAGE` 400 / `DUPLICATE_TEMPLATE` 409; writes audit row ([email_templates.py:217-258](../../app/api/email_templates.py#L217)). |
| PUT | `/{template_id}` | admin | Partial; `NO_CHANGES` 400; bumps `updated_at`; audit row ([email_templates.py:261-292](../../app/api/email_templates.py#L261)). |
| DELETE | `/{template_id}` (204) | admin | Soft delete `is_active = FALSE`; `response_class=Response`; audit row ([email_templates.py:295-313](../../app/api/email_templates.py#L295)). |
| POST | `/resolve` | JWT | Returns resolved row + `resolved_from`; `INVALID_STAGE` 400; `NOT_FOUND` 404 ([email_templates.py:316-360](../../app/api/email_templates.py#L316)). |

### `/v1/admin/email-debug` ([email_debug.py](../../app/api/email_debug.py)) — all admin-only

| Method | Path | Notes |
|---|---|---|
| GET | `/config` | Presence booleans + non-secret values; username/password value always null ([email_debug.py:64-78](../../app/api/email_debug.py#L64)). |
| POST | `/connectivity` | connect/starttls/login/noop/quit; per-step `{ok, latency_ms, error}`; no mail sent ([email_debug.py:82-150](../../app/api/email_debug.py#L82)). |
| POST | `/send` | Real send + wire capture → `email_attempts` (`trigger='debug_test'`); returns `{sent, to, subject, latency_ms, error, smtp_log}` ([email_debug.py:234-303](../../app/api/email_debug.py#L234)). |
| GET | `/attempts` | `limit` 1–500, `to` substring, `result` sent|failed, `since_hours` 1–720; newest-first ([email_debug.py:307-357](../../app/api/email_debug.py#L307)). |

### Frontend client wrappers ([api.ts](../../frontend/src/services/api.ts))

`emailTemplatesApi.{list,get,add,update,remove,resolve}` and `emailDebug.{config,connectivity,send,attempts}` map 1:1 to the routes above ([api.ts:916-935](../../frontend/src/services/api.ts#L916), [api.ts:1011-1018](../../frontend/src/services/api.ts#L1011)).

## Data Models

### `email_templates` (migration 048) ([048_email_templates.sql:28-39](../../migrations/048_email_templates.sql#L28))

`id UUID PK`, `session_type_id UUID → session_types(id) ON DELETE CASCADE` (NULL = default), `stage_id TEXT`, `locale TEXT DEFAULT 'en-US'`, `subject TEXT`, `body TEXT` (HTML), `is_active BOOLEAN DEFAULT TRUE`, `created_by TEXT`, `created_at/updated_at TIMESTAMPTZ DEFAULT now()`.

Indexes: unique `(COALESCE(session_type_id::text,'_default_'), stage_id, locale)`; partial `(stage_id) WHERE is_active`; partial `(session_type_id) WHERE is_active AND NOT NULL` ([048_email_templates.sql:51-57](../../migrations/048_email_templates.sql#L51)). Migration 048 drops the legacy migration-006 `email_templates` table first ([048_email_templates.sql:21](../../migrations/048_email_templates.sql#L21)).

Seeds: 8 transition rows (`prep`…`complete`) in 048; 7 `*_overdue` rows in 051; all `session_type_id = NULL`, `en-US` ([048_email_templates.sql:64-90](../../migrations/048_email_templates.sql#L64), [051_email_templates_overdue_seeds.sql:32-55](../../migrations/051_email_templates_overdue_seeds.sql#L32)). Overdue templates support vars: `session_code, session_title, assignee_first_name, stage, overdue_hours, editor_url, results_url` ([051_email_templates_overdue_seeds.sql:19-26](../../migrations/051_email_templates_overdue_seeds.sql#L19)).

### `email_attempts` (migration 030) ([030_email_attempts.sql:16-38](../../migrations/030_email_attempts.sql#L16))

`id UUID PK`, `attempted_at TIMESTAMPTZ DEFAULT now()`, `from_address TEXT`, `to_address TEXT`, `subject TEXT`, `trigger TEXT`, `sop_session_id UUID → sessions(id) ON DELETE SET NULL`, `stage TEXT`, `result TEXT`, `error_code TEXT`, `error_message TEXT`, `latency_ms INTEGER`, `smtp_log TEXT`, `operator_email TEXT`. CHECKs: `result IN ('sent','failed')`, `trigger IN ('stage_notification','debug_test','template_test')`. Indexes on `attempted_at DESC`, `to_address`, `sop_session_id`, `result`.

### `audit_events` (migration 004) ([004_audit.sql:3-11](../../migrations/004_audit.sql#L3))

`id, session_id → sessions(id) ON DELETE SET NULL, actor_email, kind, summary, details JSONB DEFAULT '{}', occurred_at`. Used as both the template-CRUD audit and the deadline-email throttle ledger.

### Pydantic / TS models

- Backend: `EmailTemplateCreate`, `EmailTemplatePatch`, `ResolveRequest`, `SendRequest` ([email_templates.py:128-149](../../app/api/email_templates.py#L128), [email_debug.py:56-60](../../app/api/email_debug.py#L56)).
- Frontend: `EmailTemplate`, `EmailTemplateCreate`, `EmailTemplatePatch`, `SmtpConfigCheck`, `SmtpConnectivityResult`, `SmtpSendResult`, `EmailAttemptRow` ([api.ts:891-1009](../../frontend/src/services/api.ts#L891)).

## Events

- **WebSocket:** `sop.deadline_warning` (`{type, stage, overdue_hours}`) emitted per overdue stage via `publish_ws_event_sync` ([sop_tasks.py:503-510](../../app/tasks/sop_tasks.py#L503)).
- **Audit events (kinds):** `settings.email_templates.add|update|remove` (template CRUD); `sop.deadline_warning` (always); `sop.deadline_email_sent` (throttle-claim row, kept on success); `sop.deadline_email_failed` (same row updated on SMTP failure) ([email_templates.py:255](../../app/api/email_templates.py#L255), [email_templates.py:289](../../app/api/email_templates.py#L289), [email_templates.py:310](../../app/api/email_templates.py#L310), [sop_tasks.py:316](../../app/tasks/sop_tasks.py#L316), [sop_tasks.py:430](../../app/tasks/sop_tasks.py#L430)).
- **Client-side event log:** `EmailDebug` keeps an in-memory, last-500 log of every API call this session ([EmailDebug.vue:41-48](../../frontend/src/components/settings/EmailDebug.vue#L41)).

## State Management

- Frontend state is component-local Vue refs (no Pinia store for this module). `EmailBuilder` and `EmailDebug` hold their own state; the only shared store touched is `useAuthStore` indirectly via `auth.me()` ([EmailBuilder.vue:209](../../frontend/src/components/settings/EmailBuilder.vue#L209)).
- Server-side state is the three tables. The deadline throttle is a stateful audit row guarded by a per-`(session, stage)` Postgres advisory lock (`pg_advisory_xact_lock`) so concurrent Beat tick + `/v1/diag/sop-check` can't double-send ([sop_tasks.py:283-328](../../app/tasks/sop_tasks.py#L283), [sop_tasks.py:162-176](../../app/tasks/sop_tasks.py#L162)).

## Validation

- Server-side Pydantic field constraints (lengths, regex) as in the Validation Rules of the product spec; `stage_id` allowlist `_VALID_STAGES` (15 entries) checked on POST/resolve ([email_templates.py:118-125](../../app/api/email_templates.py#L118), [email_templates.py:224](../../app/api/email_templates.py#L224)).
- `to` email regex on `/send`: `^[^@\s]+@[^@\s]+\.[^@\s]+$` ([email_debug.py:47](../../app/api/email_debug.py#L47), [email_debug.py:243](../../app/api/email_debug.py#L243)).
- Client-side `EmailBuilder` recipient regex `/^\S+@\S+\.\S+$/` before the test send ([EmailBuilder.vue:220](../../frontend/src/components/settings/EmailBuilder.vue#L220)).

## Security

- **XSS:** template **body** values are HTML-escaped (`html.escape(quote=True)`) on substitution; **subjects** use the no-escape text variant since RFC 5322 headers are plain text ([email_templates.py:58-79](../../app/api/email_templates.py#L58), [sop_tasks.py:374-380](../../app/tasks/sop_tasks.py#L374)). The inline fallback path in `_maybe_send_deadline_email` independently escapes title/code/stage ([sop_tasks.py:388-402](../../app/tasks/sop_tasks.py#L388)).
- **Preview sandboxing:** the EmailBuilder preview renders into `<iframe srcdoc … sandbox="allow-same-origin">` ([EmailBuilder.vue:420-423](../../frontend/src/components/settings/EmailBuilder.vue#L420)).
- **Secret hygiene:** `/config` and the diagnostic bundle never return `SMTP_USERNAME`/`SMTP_PASSWORD` values, only presence booleans ([email_debug.py:76-77](../../app/api/email_debug.py#L76), [EmailDebug.vue:278](../../frontend/src/components/settings/EmailDebug.vue#L278)).
- **PII minimization:** deadline-email audit `summary` masks the recipient local-part; full address only in `details.recipient` ([sop_tasks.py:144-159](../../app/tasks/sop_tasks.py#L144), [sop_tasks.py:320-326](../../app/tasks/sop_tasks.py#L320)).

## Permissions

JWT presence + hardcoded legacy-admin gate; role-based auth is scaffold-only.

- Reads (`GET ""`, `GET /{id}`, `POST /resolve`) require `CurrentUser` only ([email_templates.py:166-167](../../app/api/email_templates.py#L166), [email_templates.py:318](../../app/api/email_templates.py#L318)).
- Mutations call `require_admin(user)` ([email_templates.py:223](../../app/api/email_templates.py#L223), [email_templates.py:266](../../app/api/email_templates.py#L266), [email_templates.py:298](../../app/api/email_templates.py#L298)).
- All `/v1/admin/email-debug/*` call `require_admin` via `_require_email_debug_admin` ([email_debug.py:50-53](../../app/api/email_debug.py#L50)).
- `require_admin`/`is_admin`: admin == `user.email == "johndean@vin.com"` (exact match). `role` param exists but is never passed; `get_current_user` does not load `auth_users.role` ([roles.py:62-92](../../app/security/roles.py#L62), [roles.py:10-19](../../app/security/roles.py#L10)).

## Integrations

- **SMTP** (stdlib `smtplib`) via `SMTP_HOST/PORT/FROM/USERNAME/PASSWORD`; STARTTLS, optional LOGIN. Per CLAUDE.md, prod shares MIC's SMTP and sends as `mic@design.veterinary.support`. ([email.py:52-77](../../app/services/email.py#L52), [email_debug.py:179-184](../../app/api/email_debug.py#L179)).
- **`session_types`** for per-Type templates; **`sessions`** for title/code/type and the attempts FK; **`sop_state`** for assignees + SLAs.
- **Celery / Celery Beat** for the hourly scan; **WS bridge** for live deadline warnings.

## Background Jobs

- **`rounds.tasks.sop.check_deadlines`** (`sop_check_deadlines_task`) — `max_retries=1`, scheduled every 3600s by Beat; also runnable synchronously via `POST /v1/diag/sop-check` (`apply().get(timeout=60)`) ([sop_tasks.py:449-455](../../app/tasks/sop_tasks.py#L449), [celery_app.py:84-88](../../app/tasks/celery_app.py#L84), [diagnostics.py:334-343](../../app/api/diagnostics.py#L334)).
  - Creates a sync engine from `DATABASE_URL` (strips `+asyncpg`) ([sop_tasks.py:465-470](../../app/tasks/sop_tasks.py#L465)).
  - Scans `sop_state WHERE current_stage NOT IN ('complete')`; per-stage SLA from `sla_target_hours` JSONB, default from `_DEFAULT_SLA_HOURS` (prep 8, copy_draft 24, medical 48, copy_final 24, cms 12, captions 12, qa 8, complete 0) ([sop_tasks.py:36-45](../../app/tasks/sop_tasks.py#L36), [sop_tasks.py:474-499](../../app/tasks/sop_tasks.py#L474)).
  - Email send only when `SOP_DEADLINE_EMAIL_ENABLED` is True (default False) ([sop_tasks.py:540-543](../../app/tasks/sop_tasks.py#L540), [config.py:110](../../app/config.py#L110)).
  - Returns `{warnings, scanned}` ([sop_tasks.py:549](../../app/tasks/sop_tasks.py#L549)).

## Error Handling

- Structured `{code, message}` HTTP error bodies for CRUD; 400/404/409/403 as documented in APIs.
- `/connectivity` short-circuits on first failed step (remaining steps reported `ok: null`); cleans up via `server.quit()` in failure branches ([email_debug.py:104-150](../../app/api/email_debug.py#L104)).
- `/send` catches send exceptions, records a `failed` attempt, and returns `sent: false` (200) rather than raising ([email_debug.py:264-303](../../app/api/email_debug.py#L264)).
- `send_smtp_email` and `_record_attempt` never raise ([email.py:78-84](../../app/services/email.py#L78), [email_debug.py:229-230](../../app/api/email_debug.py#L229)).
- Deadline path: template-resolve error → inline f-string fallback; throttle-claim error → log+skip; audit-update error → log non-fatal; the whole email path is wrapped in a try/except in the task loop so it never fails the scan ([sop_tasks.py:368-371](../../app/tasks/sop_tasks.py#L368), [sop_tasks.py:329-336](../../app/tasks/sop_tasks.py#L329), [sop_tasks.py:540-545](../../app/tasks/sop_tasks.py#L540)).

## Performance Considerations

- **Throttle prevents resend storms:** the hourly Beat tick would otherwise re-email every overdue stage each hour; the 23h `audit_events` throttle (BR-004) caps it to one per `(session, stage)` ([sop_tasks.py:297-311](../../app/tasks/sop_tasks.py#L297)).
- **Advisory lock** serializes concurrent invocations against the same `(session, stage)` so two workers can't both pass the throttle SELECT ([sop_tasks.py:278-284](../../app/tasks/sop_tasks.py#L278)).
- **smtplib timeouts** are 10s on connect/send across all SMTP paths ([email.py:73](../../app/services/email.py#L73), [email_debug.py:107](../../app/api/email_debug.py#L107), [email_debug.py:179](../../app/api/email_debug.py#L179)).
- **`/attempts`** is `LIMIT`-bounded (max 500) and uses the `attempted_at DESC` index ([email_debug.py:310](../../app/api/email_debug.py#L310), [030_email_attempts.sql:35](../../migrations/030_email_attempts.sql#L35)).
- **Test send is intentionally unthrottled** for admin iteration — a known trade-off, admin-gated ([email_debug.py:237-238](../../app/api/email_debug.py#L237)).
- **No batch/bulk email job exists** in this module. IMPLEMENTATION NOT FOUND for any queued bulk-email mechanism beyond the per-overdue-stage send inside the hourly scan.

## Source Verification
- **Files Used:** app/api/email_templates.py, app/api/email_debug.py, app/services/email.py, app/tasks/sop_tasks.py, app/tasks/celery_app.py, app/config.py, app/security/roles.py, app/main.py, app/api/diagnostics.py, migrations/004_audit.sql, migrations/030_email_attempts.sql, migrations/048_email_templates.sql, migrations/051_email_templates_overdue_seeds.sql, frontend/src/components/settings/SectionEmail.vue, frontend/src/components/settings/EmailBuilder.vue, frontend/src/components/settings/EmailDebug.vue, frontend/src/components/settings/SectionDiagnostics.vue, frontend/src/views/SettingsView.vue, frontend/src/services/api.ts
- **Components Used:** SectionEmail.vue, EmailBuilder.vue, EmailDebug.vue, SectionDiagnostics.vue, SettingsView.vue
- **APIs Used:** /v1/email-templates (GET/POST/PUT/DELETE + /resolve), /v1/admin/email-debug/{config,connectivity,send,attempts}, /v1/diag/sop-check
- **Database Tables Used:** email_templates, email_attempts, audit_events, session_types, sessions, sop_state
- **Permission Logic Used:** JWT (CurrentUser) + LEGACY_ADMIN_EMAIL gate via require_admin/is_admin; reads JWT-only; role-based auth scaffold-only
- **Confidence Score:** High — every route, column, index, env var, and the Beat schedule were read from current source.
- **Evidence Links:** [email_templates.py:365-429](../../app/api/email_templates.py#L365), [email_debug.py:154-188](../../app/api/email_debug.py#L154), [sop_tasks.py:210-446](../../app/tasks/sop_tasks.py#L210), [celery_app.py:84-88](../../app/tasks/celery_app.py#L84), [config.py:110](../../app/config.py#L110), [048_email_templates.sql:28-57](../../migrations/048_email_templates.sql#L28)
