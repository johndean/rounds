# SOP Workflow — Technical Spec

> Module key: `sop-workflow`. Code-verified against the rounds.vin repository on 2026-06-08.
> Backend: FastAPI + SQLAlchemy (async) + Celery. Frontend: Vue 3 SFC. All claims tied to file:line.

## Architecture

The SOP Workflow is a per-session, forward-only state machine. The canonical state lives in `sop_state` (one row per session, PK = `session_id`). Three append-only side tables record history (`sop_transitions`), check resolutions (`sop_checks`), and signoffs (`sop_approvals` — defined but unused by this module). Stage owners exist in two unreconciled stores: a JSONB field on `sop_state` (`assignees`) and a typed `session_stage_assignees` table seeded from a per-Type `stage_assignees` matrix.

Two routers are mounted ([app/main.py:222](../../app/main.py#L222)):
- `router` — prefix `/v1/sessions/{session_id}/sop` (session-scoped) ([app/api/sop.py:20](../../app/api/sop.py#L20)).
- `global_router` — prefix `/v1/sop` (dashboard summary) ([app/api/sop.py:22](../../app/api/sop.py#L22)).

Two Celery tasks complete the architecture: `sop_auto_init_task` (event-triggered on session ready) and `sop_check_deadlines_task` (hourly Beat) ([app/tasks/sop_tasks.py:48](../../app/tasks/sop_tasks.py#L48), [app/tasks/sop_tasks.py:449](../../app/tasks/sop_tasks.py#L449)).

The eight stages are defined identically in three places (single logical source of truth, duplicated for locality):
`prep, copy_draft, medical, copy_final, cms, captions, qa, complete` ([app/api/sop.py:24](../../app/api/sop.py#L24), [app/tasks/sop_tasks.py:36](../../app/tasks/sop_tasks.py#L36), [frontend/src/fixtures/sop_stages.ts:12](../../frontend/src/fixtures/sop_stages.ts#L12)).

## Frontend Components

- **`SopView.vue`** ([frontend/src/views/SopView.vue:1](../../frontend/src/views/SopView.vue#L1)) — route `/e/:id/sop`. On mount it `Promise.all`s `sessions.get(id)` + `sop.state(id)` ([frontend/src/views/SopView.vue:43](../../frontend/src/views/SopView.vue#L43)). Renders header, KPI row, stepper, detail grid, history, and an `SOP Invariants` panel.
  - Local computeds derive `currentStage`, `currentIdx`, `nextStage`, dwell hours, and per-stage overdue from `entered_current_at` + SLA ([frontend/src/views/SopView.vue:59](../../frontend/src/views/SopView.vue#L59), [frontend/src/views/SopView.vue:163](../../frontend/src/views/SopView.vue#L163), [frontend/src/views/SopView.vue:185](../../frontend/src/views/SopView.vue#L185)).
  - `stageMeta` overlays the live `sop_state.assignees` identifier onto a static decorative palette (color/role/avatar initials stay from the palette) ([frontend/src/views/SopView.vue:66](../../frontend/src/views/SopView.vue#L66), [frontend/src/views/SopView.vue:98](../../frontend/src/views/SopView.vue#L98)).
  - Acceptance checks are derived from the fixture's stage labels and rendered `'pending'` for the current stage ([frontend/src/views/SopView.vue:114](../../frontend/src/views/SopView.vue#L114)). `canAdvance` requires all checks `'pass'` ([frontend/src/views/SopView.vue:139](../../frontend/src/views/SopView.vue#L139)).
  - Actions: `advance()` (confirm → `sop.advance`), `resolveCheck()`, `reassign()` (window.prompt → `sop.assign`), `addOverride()`/`addNote()` (`sop.annotate`), `ping()` (warn toast — no integration) ([frontend/src/views/SopView.vue:224](../../frontend/src/views/SopView.vue#L224)).
- **`StageBadge.vue`** ([frontend/src/components/shared/StageBadge.vue:1](../../frontend/src/components/shared/StageBadge.vue#L1)) — renders `.stage-badge.stage-badge--<id>` with `"<order>. <name>"`, looked up from `SOP_STAGE_BY_ID`.
- **`sop_stages.ts`** ([frontend/src/fixtures/sop_stages.ts:12](../../frontend/src/fixtures/sop_stages.ts#L12)) — frozen 8-stage fixture (`id`, `name`, `order`, `checks[]`) and a `SOP_STAGE_BY_ID` map.

## Backend Services

- **`app/api/sop.py`** — session-scoped state machine + dashboard summary. Helpers: `_validate_transition` (forward-only) and the `_DEFAULT_SLA_HOURS` map ([app/api/sop.py:80](../../app/api/sop.py#L80), [app/api/sop.py:29](../../app/api/sop.py#L29)).
- **`app/api/sessions.py`** (stage-assignees routes 345/379/498) — typed per-session assignee CRUD + bulk apply-type-defaults ([app/api/sessions.py:345](../../app/api/sessions.py#L345)).
- **`app/services/session_init.py`** — `init_session_stages(engine_or_conn, session_id, type_id, actor)` copies the resolved Type's `stage_assignees` rows into `session_stage_assignees` with `ON CONFLICT (session_id, stage) DO NOTHING`; also pins `sessions.session_type_id` to the resolved default if unset ([app/services/session_init.py:27](../../app/services/session_init.py#L27)).
- **`app/tasks/sop_tasks.py`** — the two Celery tasks plus the deadline-email helper `_maybe_send_deadline_email`, the email masker `_mask_email`, the advisory-lock key `_deadline_lock_key`, and the HTML→text converter `_html_to_text` ([app/tasks/sop_tasks.py:144](../../app/tasks/sop_tasks.py#L144), [app/tasks/sop_tasks.py:162](../../app/tasks/sop_tasks.py#L162), [app/tasks/sop_tasks.py:179](../../app/tasks/sop_tasks.py#L179), [app/tasks/sop_tasks.py:210](../../app/tasks/sop_tasks.py#L210)).

## APIs

All session-scoped routes are prefixed `/v1/sessions/{session_id}/sop`; the summary route is `/v1/sop/dashboard-summary`. Every route depends on `CurrentUser` (JWT presence).

| Method | Path | Body | Returns | Evidence |
|---|---|---|---|---|
| GET | `/sop` | — | `SopState` (auto-creates row at `prep` if missing) | [app/api/sop.py:93](../../app/api/sop.py#L93) |
| POST | `/sop/advance` | `{to_stage, note?}` | updated `SopState` | [app/api/sop.py:113](../../app/api/sop.py#L113) |
| POST | `/sop/assign` | `{stage?, assignee, note?}` | `{session_id, stage, assignee, prev}` | [app/api/sop.py:145](../../app/api/sop.py#L145) |
| PATCH | `/sop/annotations` | `{stage?, kind?, body}` | `{session_id, stage, kind, annotation, total_count}` | [app/api/sop.py:196](../../app/api/sop.py#L196) |
| POST | `/sop/checks/resolve` | `{check_id, label}` | `{resolved, check_id, stage}` | [app/api/sop.py:250](../../app/api/sop.py#L250) |
| GET | `/v1/sop/dashboard-summary` | — | `[{stage, count, overdue_count}]` | [app/api/sop.py:279](../../app/api/sop.py#L279) |
| GET | `/v1/sessions/{id}/stage-assignees` | — | typed assignee rows (JOIN-resolved labels) | [app/api/sessions.py:345](../../app/api/sessions.py#L345) |
| PUT | `/v1/sessions/{id}/stage-assignees/{stage}` | `StageAssigneePatch` | resolved row | [app/api/sessions.py:379](../../app/api/sessions.py#L379) |
| POST | `/v1/sessions/{id}/stage-assignees/apply-type-defaults?type_id=` | — | `{session_id, stages}` | [app/api/sessions.py:498](../../app/api/sessions.py#L498) |
| POST | `/v1/diag/sop-check` | — | `{ok, warnings, scanned}` | [app/api/diagnostics.py:331](../../app/api/diagnostics.py#L331) |

Frontend client wrappers live in [frontend/src/services/api.ts:628](../../frontend/src/services/api.ts#L628) (`sop.*`) and [frontend/src/services/api.ts:146](../../frontend/src/services/api.ts#L146) (`stageAssignees`).

### `SopState` shape

`{current_stage, is_blocked, blockers[], assignees{}, sla_target_hours{}, entered_current_at}` ([app/api/sop.py:41](../../app/api/sop.py#L41)). On first read with no row, `entered_current_at` is `null` and the JSONB fields are empty ([app/api/sop.py:106](../../app/api/sop.py#L106)).

## Data Models

`migrations/003_sop.sql` defines four tables:

- **`sop_state`** — `session_id UUID PK FK sessions(id) ON DELETE CASCADE`, `current_stage TEXT DEFAULT 'prep'`, `is_blocked BOOLEAN DEFAULT FALSE`, `blockers JSONB DEFAULT '[]'`, `assignees JSONB DEFAULT '{}'`, `entered_current_at TIMESTAMPTZ DEFAULT now()`, `sla_target_hours JSONB DEFAULT '{}'`, `metadata JSONB DEFAULT '{}'`, `updated_at TIMESTAMPTZ`. Index on `current_stage` ([migrations/003_sop.sql:5](../../migrations/003_sop.sql#L5)).
- **`sop_transitions`** — `id UUID PK`, `session_id FK`, `from_stage TEXT NULL`, `to_stage TEXT`, `actor_email TEXT`, `note TEXT`, `occurred_at TIMESTAMPTZ`. Index `(session_id, occurred_at DESC)` ([migrations/003_sop.sql:20](../../migrations/003_sop.sql#L20)).
- **`sop_checks`** — `id`, `session_id`, `stage`, `check_id`, `label`, `is_resolved BOOLEAN`, `resolved_by`, `resolved_at`, `metadata JSONB`, `UNIQUE (session_id, stage, check_id)` ([migrations/003_sop.sql:34](../../migrations/003_sop.sql#L34)).
- **`sop_approvals`** — `id`, `session_id`, `stage`, `actor_email`, `signature TEXT`, `occurred_at`. **Defined but no module code writes/reads it** ([migrations/003_sop.sql:50](../../migrations/003_sop.sql#L50)).

Assignee-matrix tables:

- **`session_stage_assignees`** ([migrations/042_session_stage_assignees.sql:20](../../migrations/042_session_stage_assignees.sql#L20)) — `session_id FK CASCADE`, `stage`, `person_id FK people SET NULL`, `group_id FK groups SET NULL`, `notify_email BOOLEAN DEFAULT TRUE`, `source TEXT DEFAULT 'manual'` (`'default'|'manual'`), `assigned_by`, `assigned_at`, `PRIMARY KEY (session_id, stage)`, `CHECK ((person_id IS NULL) OR (group_id IS NULL))`.
- **`stage_assignees`** — the per-Type matrix; migration 040 adds typed `person_id`/`group_id` FKs alongside the legacy `assignee_email` text and a single-assignee CHECK ([migrations/040_stage_assignees_typed_fk.sql:17](../../migrations/040_stage_assignees_typed_fk.sql#L17)). Seeded by migration 043 from Carla's matrix (17 Types × stages) ([migrations/043_seed_carla_matrix.sql:37](../../migrations/043_seed_carla_matrix.sql#L37)).
- **`session_types`** — 17 conference rounds + `default`, seeded by migration 039 ([migrations/039_seed_session_types.sql:10](../../migrations/039_seed_session_types.sql#L10)).
- Migration 044 backfills `session_stage_assignees` for pre-existing sessions from their Type matrix (or org default), guarded by a NOT EXISTS clause ([migrations/044_backfill_session_stage_assignees.sql:16](../../migrations/044_backfill_session_stage_assignees.sql#L16)).

## Events

WebSocket events emitted via `app.engines.ws_bridge.publish_ws_event_sync`:

- `sop.initialized` `{type, stage}` — on auto-init ([app/tasks/sop_tasks.py:106](../../app/tasks/sop_tasks.py#L106)). The SopView fixture comment references it but the live subscriber only handles deadline warnings.
- `sop.deadline_warning` `{type, stage, overdue_hours}` — per overdue stage in the hourly scan ([app/tasks/sop_tasks.py:503](../../app/tasks/sop_tasks.py#L503)). `SopView.vue` subscribes and updates its `overdueByStage` map ([frontend/src/views/SopView.vue:202](../../frontend/src/views/SopView.vue#L202)).

`audit_events` rows are written for `sop.advance`, `sop.assign`, `sop.annotation`, `sop.check.resolve`, `sop.initialized`, `sop.deadline_warning`, `sop.deadline_email_sent`, `sop.deadline_email_failed` (see the Audit Requirements table in the product spec).

## State Management

- **Backend** — `sop_state.current_stage` is authoritative. `POST /advance` locks the row `FOR UPDATE` before validating + updating, preventing concurrent double-advance ([app/api/sop.py:116](../../app/api/sop.py#L116)). `entered_current_at` is reset to `now()` on every advance ([app/api/sop.py:126](../../app/api/sop.py#L126)).
- **Frontend** — `SopView.vue` holds local refs (`session`, `sopState`, `selectedStage`, `overdueByStage`) and re-`load()`s after each mutation ([frontend/src/views/SopView.vue:39](../../frontend/src/views/SopView.vue#L39)). Stepper status is derived from `currentIdx` ([frontend/src/views/SopView.vue:401](../../frontend/src/views/SopView.vue#L401)). Overdue uses WS value when present, else client-side computation from `entered_current_at` + SLA ([frontend/src/views/SopView.vue:185](../../frontend/src/views/SopView.vue#L185)).
- No Pinia store backs SOP state; it is component-local.

## Validation

- `AdvancePayload.to_stage`: `min_length=1`; `_validate_transition` enforces known + exactly-one-step-forward (400 otherwise) ([app/api/sop.py:50](../../app/api/sop.py#L50), [app/api/sop.py:80](../../app/api/sop.py#L80)).
- `AssignPayload.assignee`: `min_length=1, max_length=128`; `stage` validated against `_STAGE_INDEX` ([app/api/sop.py:60](../../app/api/sop.py#L60), [app/api/sop.py:159](../../app/api/sop.py#L159)).
- `AnnotationPayload`: `kind` 1–32 chars and restricted to `note|override|blocker`; `body` 1–2000 chars; `stage` validated ([app/api/sop.py:71](../../app/api/sop.py#L71), [app/api/sop.py:210](../../app/api/sop.py#L210)).
- `StageAssigneePatch`: optional `assignee_email|person_id|group_id|notify_email`; resolver enforces single-assignee, backed by the DB CHECK constraint ([app/api/sessions.py:118](../../app/api/sessions.py#L118), [app/api/sessions.py:404](../../app/api/sessions.py#L404)).

## Security

- **Authentication:** every endpoint requires a valid JWT via the `CurrentUser` dependency ([app/api/sop.py:94](../../app/api/sop.py#L94), [app/api/sessions.py:347](../../app/api/sessions.py#L347)).
- **SQL:** all queries use SQLAlchemy `text()` with bound parameters and explicit `CAST(... AS uuid)` / `CAST(... AS jsonb)`; no string interpolation of user input into SQL ([app/api/sop.py:95](../../app/api/sop.py#L95), [app/api/sop.py:169](../../app/api/sop.py#L169)).
- **Email XSS:** the deadline-email path HTML-escapes operator-controlled values (`title`, `code`, `stage`) in the inline fallback, and uses the escaping `substitute_variables` for the HTML body vs the non-escaping `substitute_variables_text` for the RFC-5322 subject ([app/tasks/sop_tasks.py:378](../../app/tasks/sop_tasks.py#L378), [app/tasks/sop_tasks.py:388](../../app/tasks/sop_tasks.py#L388)).
- **PII minimization:** recipient local-part masked in `audit_events.summary`; full address only in `details->>'recipient'` ([app/tasks/sop_tasks.py:144](../../app/tasks/sop_tasks.py#L144), [app/tasks/sop_tasks.py:321](../../app/tasks/sop_tasks.py#L321)).
- **Frontend `reassign` uses `window.prompt`** for the assignee string — raw, unsanitized, sent to the server which stores it verbatim in JSONB ([frontend/src/views/SopView.vue:260](../../frontend/src/views/SopView.vue#L260)).

## Permissions

**No role/admin authorization on any SOP endpoint.** All SOP routes ([app/api/sop.py](../../app/api/sop.py)) and stage-assignee routes ([app/api/sessions.py](../../app/api/sessions.py)) authorize on JWT presence only (`CurrentUser`). There is:

- no use of `app/security/roles.py` (`is_admin`/`require_admin`) in SOP code,
- no read of `auth_users.role`,
- no `LEGACY_ADMIN_EMAIL == 'johndean@vin.com'` gate on SOP routes (that gate exists for session delete/trash and some diagnostics, not here) ([app/security/roles.py:54](../../app/security/roles.py#L54), [app/api/sessions.py:27](../../app/api/sessions.py#L27)),
- no `adminOnly` route guard on `/e/:id/sop` (only `/admin/help` carries `adminOnly`) ([frontend/src/router/index.ts:44](../../frontend/src/router/index.ts#L44)).

`/v1/diag/sop-check` also requires only `CurrentUser` (no admin gate) ([app/api/diagnostics.py:332](../../app/api/diagnostics.py#L332)).

## Integrations

- **Celery / Celery Beat** — `RoundsTask` base; beat schedule entry `sop-check-deadlines` runs `rounds.tasks.sop.check_deadlines` every 3600s ([app/tasks/celery_app.py:84](../../app/tasks/celery_app.py#L84)).
- **SMTP** — `app.services.email.send_smtp_email`, only when `SOP_DEADLINE_EMAIL_ENABLED` ([app/tasks/sop_tasks.py:253](../../app/tasks/sop_tasks.py#L253), [app/config.py:110](../../app/config.py#L110)).
- **email_templates** — `resolve_template_sync` with `stage_id='{stage}_overdue'`, locale `en-US`, optional `session_type_id`; inline f-string fallback ([app/tasks/sop_tasks.py:359](../../app/tasks/sop_tasks.py#L359)).
- **WebSocket bridge** — `publish_ws_event_sync` (see Events).
- **Slack** — NOT integrated; the UI "Ping" is a placeholder warn toast ([frontend/src/views/SopView.vue:273](../../frontend/src/views/SopView.vue#L273)).

## Background Jobs

### `sop_auto_init_task` ([app/tasks/sop_tasks.py:48](../../app/tasks/sop_tasks.py#L48))

- Triggered (not scheduled) from `finalize.py` and `ai_process.py` after a session lands `ready` ([app/tasks/finalize.py:103](../../app/tasks/finalize.py#L103), [app/tasks/ai_process.py:561](../../app/tasks/ai_process.py#L561)).
- Idempotent: if a `sop_state` row exists, only emits the WS event. Otherwise inserts `sop_state` at `prep` with `assignees='{}'` and the default SLA map, plus an initial `sop_transitions` row (actor `system:sop_auto_init`) ([app/tasks/sop_tasks.py:78](../../app/tasks/sop_tasks.py#L78)).
- `max_retries=2`, retry-with-backoff; terminal failure returns an error dict — never marks the session failed ([app/tasks/sop_tasks.py:133](../../app/tasks/sop_tasks.py#L133)).

### `sop_check_deadlines_task` ([app/tasks/sop_tasks.py:449](../../app/tasks/sop_tasks.py#L449))

- Scheduled hourly by Beat (3600s) and also runnable on demand via `/v1/diag/sop-check` ([app/tasks/celery_app.py:84](../../app/tasks/celery_app.py#L84), [app/api/diagnostics.py:343](../../app/api/diagnostics.py#L343)).
- Selects all `sop_state` rows where `current_stage NOT IN ('complete')`; for each, computes `deadline = entered_current_at + SLA_hours` (per-session override else default), skips if SLA ≤ 0 or not yet past deadline ([app/tasks/sop_tasks.py:474](../../app/tasks/sop_tasks.py#L474)).
- For each overdue stage: emits `sop.deadline_warning` WS, inserts a `sop.deadline_warning` audit row, and — if `SOP_DEADLINE_EMAIL_ENABLED` — calls `_maybe_send_deadline_email` ([app/tasks/sop_tasks.py:500](../../app/tasks/sop_tasks.py#L500)).
- `max_retries=1`. Returns `{warnings, scanned}` ([app/tasks/sop_tasks.py:549](../../app/tasks/sop_tasks.py#L549)).

### Deadline email (`_maybe_send_deadline_email`) ([app/tasks/sop_tasks.py:210](../../app/tasks/sop_tasks.py#L210))

- Resolves the stage assignee from `sop_state.assignees`; skips groups, non-emails, or missing entries ([app/tasks/sop_tasks.py:271](../../app/tasks/sop_tasks.py#L271)).
- Takes a per-(session,stage) `pg_advisory_xact_lock`, checks for a send/failure audit row within 23h (BR-004), then claims the slot by inserting `sop.deadline_email_sent` BEFORE sending; on SMTP failure it UPDATEs the same row to `sop.deadline_email_failed` ([app/tasks/sop_tasks.py:283](../../app/tasks/sop_tasks.py#L283), [app/tasks/sop_tasks.py:410](../../app/tasks/sop_tasks.py#L410)).
- Editor deep-link: `https://rounds.vin/#/e/{session_id}/sop` ([app/tasks/sop_tasks.py:340](../../app/tasks/sop_tasks.py#L340)).

## Error Handling

- 404 on advance/assign/annotation when `sop_state` is uninitialized ([app/api/sop.py:120](../../app/api/sop.py#L120), [app/api/sop.py:156](../../app/api/sop.py#L156), [app/api/sop.py:207](../../app/api/sop.py#L207)).
- 400 on illegal transition, advance-while-blocked, unknown stage, unknown annotation kind ([app/api/sop.py:83](../../app/api/sop.py#L83), [app/api/sop.py:122](../../app/api/sop.py#L122), [app/api/sop.py:213](../../app/api/sop.py#L213)).
- Background tasks wrap WS/audit/email side-effects in `try/except … logger.warning` so a single failure never aborts the scan or the init ([app/tasks/sop_tasks.py:110](../../app/tasks/sop_tasks.py#L110), [app/tasks/sop_tasks.py:511](../../app/tasks/sop_tasks.py#L511)).
- `dashboard_summary` skips rows whose `current_stage` is not a known stage rather than poisoning the response ([app/api/sop.py:306](../../app/api/sop.py#L306)).
- Frontend actions catch and toast errors; `load()` swallows fetch errors via `.catch(() => null)` ([frontend/src/views/SopView.vue:47](../../frontend/src/views/SopView.vue#L47)).

## Performance Considerations

- `sop_state` has an index on `current_stage`; transitions index `(session_id, occurred_at DESC)`; checks index `(session_id, stage)` ([migrations/003_sop.sql:17](../../migrations/003_sop.sql#L17)).
- `dashboard_summary` does a single full scan of `sop_state` and aggregates in Python, keeping the overdue definition identical to the deadline task and client fallback ([app/api/sop.py:295](../../app/api/sop.py#L295)). This is O(rows in sop_state) — fine at current scale, unindexed for overdue.
- The deadline task opens a fresh sync engine per invocation and disposes it in `finally`; it reads all non-complete rows in one query then loops ([app/tasks/sop_tasks.py:469](../../app/tasks/sop_tasks.py#L469)).
- The advisory lock in the email path serializes only same-(session,stage) sends, not the whole scan ([app/tasks/sop_tasks.py:284](../../app/tasks/sop_tasks.py#L284)).
- Stage-assignee reads JOIN `people`/`groups` so renames/deletes propagate without backfill; both FK columns are indexed ([app/api/sessions.py:360](../../app/api/sessions.py#L360), [migrations/042_session_stage_assignees.sql:34](../../migrations/042_session_stage_assignees.sql#L34)).

## Source Verification
- **Files Used:** app/api/sop.py, app/tasks/sop_tasks.py, app/tasks/celery_app.py, app/tasks/finalize.py, app/tasks/ai_process.py, app/api/diagnostics.py, app/api/sessions.py, app/services/session_init.py, app/config.py, app/main.py, app/security/roles.py, frontend/src/views/SopView.vue, frontend/src/components/shared/StageBadge.vue, frontend/src/fixtures/sop_stages.ts, frontend/src/services/api.ts, frontend/src/router/index.ts, migrations/003_sop.sql, migrations/039_seed_session_types.sql, migrations/040_stage_assignees_typed_fk.sql, migrations/042_session_stage_assignees.sql, migrations/043_seed_carla_matrix.sql, migrations/044_backfill_session_stage_assignees.sql
- **Components Used:** SopView.vue, StageBadge.vue, sop_stages.ts fixture
- **APIs Used:** /v1/sessions/{id}/sop (GET/advance/assign/annotations/checks/resolve), /v1/sop/dashboard-summary, /v1/sessions/{id}/stage-assignees[/{stage}], /stage-assignees/apply-type-defaults, /v1/diag/sop-check
- **Database Tables Used:** sop_state, sop_transitions, sop_checks, sop_approvals (unused), session_stage_assignees, stage_assignees, session_types, people, groups, audit_events, email_templates, sessions
- **Permission Logic Used:** JWT presence (CurrentUser) only — no role/admin/LEGACY_ADMIN_EMAIL gate
- **Confidence Score:** High — every architectural and behavioral claim is line-cited; stale-comment and unused-table caveats flagged.
- **Evidence Links:** [app/api/sop.py:20](../../app/api/sop.py#L20), [app/api/sop.py:113](../../app/api/sop.py#L113), [app/tasks/sop_tasks.py:449](../../app/tasks/sop_tasks.py#L449), [app/tasks/celery_app.py:84](../../app/tasks/celery_app.py#L84), [migrations/003_sop.sql:5](../../migrations/003_sop.sql#L5), [frontend/src/views/SopView.vue:1](../../frontend/src/views/SopView.vue#L1)
