# Sessions — Technical Spec

> Module key: `sessions`. Code-verified against `HEAD` on 2026-06-08.
> Paths are relative to this file (`docs/technical/`). Route line numbers track
> the `@router` decorator.

## Architecture

The Sessions module spans three backend concerns and two frontend screens:

1. **CRUD + lifecycle** — `app/api/sessions.py` (list, get, create, patch, soft
   delete, restore, permanent delete, deleted-list, audit-log, failure-reason,
   pipeline-config, stage-assignees) ([sessions.py:30](../../app/api/sessions.py#L30)).
2. **State machine** — `app/engines/state_machine.py` is the single sanctioned
   path for mutating `sessions.status`; there is **no DB-level transition CHECK**,
   only a value-set CHECK ([state_machine.py:1](../../app/engines/state_machine.py#L1)).
3. **Editor lock** — `app/api/locks.py` backed by the `session_locks` table; the
   advisory-lock helper `app/services/db_locks.py` serializes ingest/correction
   work via Postgres advisory locks ([locks.py:1](../../app/api/locks.py#L1),
   [db_locks.py:1](../../app/services/db_locks.py#L1)).

Both `sessions_router` and `locks_router` mount on prefix `/v1/sessions` and are
registered in `app/main.py` ([sessions.py:30](../../app/api/sessions.py#L30),
[locks.py:40](../../app/api/locks.py#L40),
[main.py:214](../../app/main.py#L214)).

The frontend is a Vue 3 `<script setup>` port. `SessionsView.vue` (list) and
`SessionDetailView.vue` (detail) call the typed `sessions` client in
`frontend/src/services/api.ts`; `useSessionLock.ts` drives the editor lock.

## Frontend Components

| Component | Role | Source |
|---|---|---|
| `SessionsView.vue` | List, KPIs, filter chips, search, failure modal, delete | [SessionsView.vue](../../frontend/src/views/SessionsView.vue) |
| `SessionDetailView.vue` | Detail grid: meta, KPIs, stage assignments, timeline, widgets | [SessionDetailView.vue](../../frontend/src/views/SessionDetailView.vue) |
| `SessionTextEdit.vue` | Click-to-edit inline field for `code`/`title`/`title_long`/`title_short` | [SessionTextEdit.vue](../../frontend/src/components/session/SessionTextEdit.vue) |
| `useSessionLock.ts` | Acquire/heartbeat/release/force-take + fail-closed handling | [useSessionLock.ts](../../frontend/src/composables/useSessionLock.ts) |

- `SessionsView.vue` loads via `sessionsApi.list({ stage, ai, f })` and watches
  `route.query` to re-fetch on deep-link change
  ([SessionsView.vue:33](../../frontend/src/views/SessionsView.vue#L33),
  [SessionsView.vue:51](../../frontend/src/views/SessionsView.vue#L51)).
- `SessionDetailView.vue` fans out a `Promise.all` of nine fetches (session,
  sources, slides, segments, stage-assignees, Types, people, groups, chat
  participants), each `.catch`-defaulted so a partial failure still renders
  ([SessionDetailView.vue:97](../../frontend/src/views/SessionDetailView.vue#L97)).
- `SessionTextEdit.vue` is uncontrolled: it tracks a local `draft`, commits on
  blur/Enter via `sessionsApi.update`, and keeps the input open on error
  ([SessionTextEdit.vue:67](../../frontend/src/components/session/SessionTextEdit.vue#L67)).

## Backend Services

| Service | Responsibility | Source |
|---|---|---|
| State machine | `ALLOWED_TRANSITIONS`, `transition_session` (async), `transition_session_sync` (Celery), audit append, WS emit | [state_machine.py](../../app/engines/state_machine.py) |
| Session init | Copy a Type's `stage_assignees` matrix into `session_stage_assignees`; resolve Type by code | [session_init.py](../../app/services/session_init.py) |
| Advisory locks | `try_advisory_lock` (sync, session-scoped) + `try_advisory_lock_async` (xact-scoped) | [db_locks.py](../../app/services/db_locks.py) |
| Rate limit | `check_user_quota`, `reserve_slot`, `release_slot`, `validate_files` (Redis) | [rate_limit.py](../../app/middleware/rate_limit.py) |
| Role gate | `is_admin`, `require_admin`, `LEGACY_ADMIN_EMAIL` | [roles.py](../../app/security/roles.py) |

- `init_session_stages` is idempotent (`ON CONFLICT (session_id, stage) DO
  NOTHING`); if `type_id` is null it falls back to the org-default Type
  (`session_types.is_default = TRUE`) and pins it onto `sessions.session_type_id`
  ([session_init.py:69](../../app/services/session_init.py#L69),
  [session_init.py:53](../../app/services/session_init.py#L53)).
- `apply_type_defaults` opens a **sync** engine (`DATABASE_URL` minus `+asyncpg`)
  to call `init_session_stages` after wiping existing rows
  ([sessions.py:534](../../app/api/sessions.py#L534)).

## APIs

All routes require a valid JWT (`CurrentUser`). Sessions CRUD/lifecycle
([sessions.py](../../app/api/sessions.py)):

| Method | Path | Line |
|---|---|---|
| GET | `/v1/sessions` (filters `stage`,`ai`,`f`,`limit`,`offset`) | [138](../../app/api/sessions.py#L138) |
| POST | `/v1/sessions` (201) | [178](../../app/api/sessions.py#L178) |
| GET | `/v1/sessions/deleted` (admin) | [266](../../app/api/sessions.py#L266) |
| GET | `/v1/sessions/{id}/audit-log` | [306](../../app/api/sessions.py#L306) |
| GET | `/v1/sessions/{id}/pipeline-config` | [323](../../app/api/sessions.py#L323) |
| GET | `/v1/sessions/{id}/stage-assignees` | [345](../../app/api/sessions.py#L345) |
| PUT | `/v1/sessions/{id}/stage-assignees/{stage}` | [379](../../app/api/sessions.py#L379) |
| POST | `/v1/sessions/{id}/stage-assignees/apply-type-defaults` | [498](../../app/api/sessions.py#L498) |
| GET | `/v1/sessions/{id}` | [547](../../app/api/sessions.py#L547) |
| PATCH | `/v1/sessions/{id}` | [569](../../app/api/sessions.py#L569) |
| DELETE | `/v1/sessions/{id}` (soft) | [621](../../app/api/sessions.py#L621) |
| POST | `/v1/sessions/{id}/restore` (admin) | [668](../../app/api/sessions.py#L668) |
| DELETE | `/v1/sessions/{id}/permanent` (admin) | [697](../../app/api/sessions.py#L697) |
| GET | `/v1/sessions/{id}/failure-reason` | [753](../../app/api/sessions.py#L753) |

Editor lock ([locks.py](../../app/api/locks.py)) — note the path segment is
`lock` (singular):

| Method | Path | Line |
|---|---|---|
| POST | `/v1/sessions/{id}/lock/acquire` | [99](../../app/api/locks.py#L99) |
| POST | `/v1/sessions/{id}/lock/heartbeat` | [142](../../app/api/locks.py#L142) |
| POST | `/v1/sessions/{id}/lock/release` (204) | [188](../../app/api/locks.py#L188) |
| GET | `/v1/sessions/{id}/lock/holder` | [204](../../app/api/locks.py#L204) |
| POST | `/v1/sessions/{id}/lock/force-take` (admin) | [218](../../app/api/locks.py#L218) |

> DISCREPANCY: the seed spec `docs/specs/session-management.spec.md` lists these
> as `/v1/sessions/{id}/locks/…` (plural). The code registers **singular**
> `lock` — confirmed by both the router and the frontend composable
> ([locks.py:99](../../app/api/locks.py#L99),
> [useSessionLock.ts:89](../../frontend/src/composables/useSessionLock.ts#L89)).

Important response shapes:

- `SessionOut` ([sessions.py:81](../../app/api/sessions.py#L81)): `id, code, title,
  title_long, title_short, presenter, status, duration_sec, word_count,
  segment_count, attendee_count, taxonomy, session_type_id`.
- `LockState` ([locks.py:57](../../app/api/locks.py#L57)): `{acquired, is_self,
  holder?}` where `holder` is `{user_email, acquired_at, heartbeat_at,
  expires_at}`.

## Data Models

`sessions` ([001_init.sql:13](../../migrations/001_init.sql#L13)): `id` (uuid PK,
`gen_random_uuid()`), `code` (text, UNIQUE), `title`, `presenter`, `recorded_at`,
`duration_sec`, `attendee_count`, `word_count`, `segment_count`, `taxonomy`
(jsonb, default `[]`), `status` (text, default `'ingesting'` — superseded), plus
`deleted_at`, `created_at`, `updated_at`. Indexes: partial on `status`
(`deleted_at IS NULL`), partial on `recorded_at`, and `lower(code)`
([001_init.sql:30](../../migrations/001_init.sql#L30)).

> NOTE: `title_long`, `title_short`, and `session_type_id` are read/written by the
> module but are NOT defined in `001_init.sql`; they are added by later migrations
> (referenced in code at [sessions.py:91](../../app/api/sessions.py#L91) and
> [sessions.py:103](../../app/api/sessions.py#L103)). Exact migration files NOT
> VERIFIED IN CODE for this assignment (outside the listed source set).

`sessions.status` CHECK ([010_state_machine.sql:21](../../migrations/010_state_machine.sql#L21)):
`uploading, transcribing, normalizing, fusing, aligning, ready, complete,
failed`. Migration 010 first drops any prior CHECK, normalizes legacy
`ingesting → uploading`, then adds the constraint
([010_state_machine.sql:15](../../migrations/010_state_machine.sql#L15)).

`session_audit` ([010_state_machine.sql:31](../../migrations/010_state_machine.sql#L31)):
`session_id` (uuid PK, FK → sessions ON DELETE CASCADE), `processing_log` (jsonb,
default `[]`), `updated_at`. One row per session; the log is an append-only JSONB
array. (Code also references a `finalized_at` column set on `ready`
([state_machine.py:91](../../app/engines/state_machine.py#L91)) — that column is
NOT in 010; added by a later migration — NOT VERIFIED IN CODE here.)

`session_locks` ([057_session_locks.sql:14](../../migrations/057_session_locks.sql#L14)):
`session_id` (uuid PK), `user_email` (text), `acquired_at`, `heartbeat_at`,
`expires_at` (default `now() + 90s`), with an `expires_at` lookup index. This is
a Postgres table — **not Redis** (the seed spec's "distributed edit locks
(Redis)" is incorrect; Redis backs rate-limit slots, not the editor lock).

`session_stage_assignees` (referenced, schema in a later migration): columns
`session_id, stage, person_id, group_id, notify_email, source, assigned_by,
assigned_at`, unique on `(session_id, stage)`, with a single-assignee CHECK
`chk_session_stage_assignees_single_assignee`
([sessions.py:455](../../app/api/sessions.py#L455),
[sessions.py:399](../../app/api/sessions.py#L399)).

`session_templates` (pipeline config; later migration): `session_id, ai_pipeline,
ai_mode, ai_model, prompt_mode, custom_prompt, stt_backend, template_id,
iil_config, auto_detected_template_id, auto_detected_confidence`
([sessions.py:235](../../app/api/sessions.py#L235),
[sessions.py:331](../../app/api/sessions.py#L331)).

## Events

- Every status transition emits a WebSocket `processing_update`
  (`{type, stage, progress: 0}`) via `publish_ws_event_sync`, swallowing
  `ImportError` defensively ([state_machine.py:98](../../app/engines/state_machine.py#L98)).
- The WS endpoint is `/v1/ws/sessions/{session_id}`
  ([main.py:192](../../app/main.py#L192)).
- Each transition also appends an audit entry (see **Data Models**)
  ([state_machine.py:52](../../app/engines/state_machine.py#L52)).
- Lock force-take inserts an `audit_events` row
  ([locks.py:246](../../app/api/locks.py#L246)).
- No domain event bus / message queue beyond Celery + the WS bridge is used by
  this module. NOT VERIFIED IN CODE for any other event system.

## State Management

Backend FSM ([state_machine.py:40](../../app/engines/state_machine.py#L40)):

- `ALLOWED_TRANSITIONS` maps each status to its legal successors;
  `TERMINAL_STATES = {failed, complete}` ([state_machine.py:49](../../app/engines/state_machine.py#L49)).
- `transition_session_sync` (Celery) opens its own sync engine, takes
  `SELECT … FOR UPDATE` on the session row inside `engine.begin()`, validates the
  move, updates status, appends the audit entry, commits, then emits WS
  ([state_machine.py:114](../../app/engines/state_machine.py#L114)).
- `transition_session` (async) does the same but does **not** commit — the caller's
  request handler owns the transaction boundary
  ([state_machine.py:173](../../app/engines/state_machine.py#L173)).
- Both raise `ConflictError` (→ 409) for unknown/terminal/illegal moves.

Frontend state:

- List: `sessions`, `loading`, `error`, `query`, `sortBy`, `activeFilter`,
  `stageFilter`, `aiFilter` refs; `filtered` and `filters` computeds
  ([SessionsView.vue:23](../../frontend/src/views/SessionsView.vue#L23)).
- Lock composable: `isHolder` (tri-state `null|true|false`), `holder`,
  `lockError`; heartbeats on an interval, pauses when the tab is hidden, releases
  on `beforeunload` ([useSessionLock.ts:52](../../frontend/src/composables/useSessionLock.ts#L52),
  [useSessionLock.ts:131](../../frontend/src/composables/useSessionLock.ts#L131)).

## Validation

- Pydantic `SessionIn`: `code` 1–64, `title` 1–512; optional `presenter`,
  `duration_sec`, `attendee_count`, `taxonomy` (default `[]`), `pipeline_config`
  ([sessions.py:71](../../app/api/sessions.py#L71)).
- `PipelineConfig` defaults: `ai_pipeline='direct'` (flipped 2026-05-20),
  `ai_mode='transcript'`, `ai_model='gemini-2.5-pro'`,
  `stt_backend='google_latest_long'`, `template_id='lecture_v1'`, `iil_config`
  all-tiers-enabled ([sessions.py:56](../../app/api/sessions.py#L56)).
- `SessionPatch` whitelist + `exclude_unset` semantics
  ([sessions.py:106](../../app/api/sessions.py#L106),
  [sessions.py:587](../../app/api/sessions.py#L587)).
- Stage-assignee resolver and DB single-assignee CHECK
  ([sessions.py:404](../../app/api/sessions.py#L404)).
- Upload-time file validation (`audio_enhance` min 100 KB, media duration ≤
  `MAX_VIDEO_DURATION_MINUTES`) lives in `validate_files`
  ([rate_limit.py:98](../../app/middleware/rate_limit.py#L98)).

## Security

- `get_current_user` decodes the JWT, checks `user_is_active` against the DB, and
  falls back to the env `AUTH_USERS` CSV; returns `User(email=...)` — **no role is
  ever loaded** ([auth.py:172](../../app/auth.py#L172),
  [auth.py:37](../../app/auth.py#L37)).
- SQL is parameterized via SQLAlchemy `text()` binds throughout; the dynamic
  `list_sessions` query assembles a fixed clause set with bound params (no string
  interpolation of user values) ([sessions.py:152](../../app/api/sessions.py#L152)).
- Create catches the `sessions_code_key` `IntegrityError` and rolls back, avoiding
  a leaked 500 ([sessions.py:219](../../app/api/sessions.py#L219)).
- `AUTH_USERS` is plaintext in env (known debt, per repo CLAUDE.md). NOT changed
  by this module.

## Permissions

> PERMISSION REALITY (verified): JWT presence + a hardcoded
> `LEGACY_ADMIN_EMAIL = 'johndean@vin.com'` gate. Role tiers are scaffold-only.

- `CurrentUser` JWT dependency on every route
  ([sessions.py:25](../../app/api/sessions.py#L25),
  [locks.py:36](../../app/api/locks.py#L36)).
- Soft-delete: `_user.email in SESSION_TRASH_ALLOWED`
  (`{johndean@vin.com, carlab@vin.com}`), else `403`
  ([sessions.py:630](../../app/api/sessions.py#L630)).
- `require_admin` on list-deleted / restore / permanent-delete; `is_admin` on lock
  force-take ([sessions.py:276](../../app/api/sessions.py#L276),
  [sessions.py:674](../../app/api/sessions.py#L674),
  [sessions.py:707](../../app/api/sessions.py#L707),
  [locks.py:225](../../app/api/locks.py#L225)).
- `is_admin(user, role=None)` short-circuits to `user.email == LEGACY_ADMIN_EMAIL`
  (case- and whitespace-sensitive) because no caller passes `role=` and no role is
  loaded; the `role == "admin"` branch is dead until `get_current_user` is
  extended ([roles.py:62](../../app/security/roles.py#L62),
  [roles.py:10](../../app/security/roles.py#L10)).
- Client-side: only `/admin/help` carries `meta.adminOnly`, redirecting non-admins
  to `/dashboard`; no Sessions route is guarded
  ([router/index.ts:44](../../frontend/src/router/index.ts#L44),
  [router/index.ts:63](../../frontend/src/router/index.ts#L63)).

## Integrations

- **Redis** — concurrency slots (`sessions:active:{user}` set + `sessions:queue`
  list); soft-delete and permanent-delete call `release_slot` best-effort
  ([rate_limit.py:69](../../app/middleware/rate_limit.py#L69),
  [sessions.py:657](../../app/api/sessions.py#L657)).
- **WebSocket bridge** — `app/engines/ws_bridge.publish_ws_event_sync`
  ([state_machine.py:101](../../app/engines/state_machine.py#L101)).
- **Postgres** — primary store; both async (`DbSession`) and sync engines
  (`create_engine(DATABASE_URL.replace('+asyncpg',''))`) are used
  ([sessions.py:534](../../app/api/sessions.py#L534),
  [state_machine.py:129](../../app/engines/state_machine.py#L129)).
- **Celery** — `transition_session_sync` is the FSM entry point for worker tasks
  ([state_machine.py:114](../../app/engines/state_machine.py#L114)).
- No external billing / CMS / GCS calls originate inside this module's source
  files. NOT VERIFIED IN CODE for export/CMS integration here (the detail page's
  download buttons are stubbed — [SessionDetailView.vue:299](../../frontend/src/views/SessionDetailView.vue#L299)).

## Background Jobs

- The module itself defines no Celery task; it exposes the **sync** FSM entry
  (`transition_session_sync`) that ingest tasks call as they advance a session
  through `transcribing → … → ready`
  ([state_machine.py:114](../../app/engines/state_machine.py#L114)).
- The advisory-lock helpers in `db_locks.py` are designed for those long-running
  ingest tasks (session-scoped sync lock) and the correction handlers
  (xact-scoped async lock) ([db_locks.py:21](../../app/services/db_locks.py#L21)).
- Stale `session_locks` rows are swept by "future cron sweeper" — the index
  exists; no scheduled job is wired in this module's source
  ([057_session_locks.sql:22](../../migrations/057_session_locks.sql#L22)). The
  90s TTL plus force-take are the live recovery mechanisms.

## Error Handling

- 404 / 409 / 403 / 400 / 500 as enumerated in the product spec **Error Handling**
  section, all traced to `sessions.py`.
- `ConflictError` from the FSM (and the envelope `ConflictError`) map to `409`
  ([state_machine.py:29](../../app/engines/state_machine.py#L29),
  [sessions.py:644](../../app/api/sessions.py#L644)).
- Permanent-delete cascade failure: rollback + `logging.error(exc_info=True)` +
  `500` with the exception class name
  ([sessions.py:734](../../app/api/sessions.py#L734)).
- Rate-limit Redis errors are swallowed (warn-only) so uploads aren't blocked by a
  Redis outage ([rate_limit.py:64](../../app/middleware/rate_limit.py#L64)).
- WS emit failures are caught and logged, never propagated
  ([state_machine.py:110](../../app/engines/state_machine.py#L110)).
- Frontend: list and detail render inline error strings; SessionTextEdit surfaces
  a warn toast and keeps the input open on `409`; the lock composable sets
  `lockError` and fails closed (read-only) on any unreachable lock call
  ([SessionTextEdit.vue:82](../../frontend/src/components/session/SessionTextEdit.vue#L82),
  [useSessionLock.ts:61](../../frontend/src/composables/useSessionLock.ts#L61)).

## Performance Considerations

- List defaults to `LIMIT 50 OFFSET 0`, ordered `created_at DESC NULLS LAST,
  code DESC`; the partial index on `status WHERE deleted_at IS NULL` supports the
  default scan ([sessions.py:169](../../app/api/sessions.py#L169),
  [001_init.sql:30](../../migrations/001_init.sql#L30)).
- FSM transitions take a row-level `SELECT … FOR UPDATE` to serialize concurrent
  status changes on one session ([state_machine.py:133](../../app/engines/state_machine.py#L133)).
- Advisory locks are RAM-cheap (`pg_try_advisory_lock`, ~50µs) and avoid table
  locks; sync helper is session-scoped (held across many statements), async helper
  is xact-scoped (auto-released at COMMIT to keep the pooled connection clean)
  ([db_locks.py:8](../../app/services/db_locks.py#L8),
  [db_locks.py:94](../../app/services/db_locks.py#L94)).
- Editor heartbeat pauses while the tab is hidden, reducing idle load and letting
  abandoned locks expire ([useSessionLock.ts:93](../../frontend/src/composables/useSessionLock.ts#L93)).
- `apply_type_defaults` and the FSM open short-lived sync engines and `dispose()`
  them in `finally` ([sessions.py:535](../../app/api/sessions.py#L535),
  [state_machine.py:166](../../app/engines/state_machine.py#L166)).
- Stage-assignee reads do JOINs against `people`/`groups` so renames propagate
  without denormalized copies ([sessions.py:360](../../app/api/sessions.py#L360)).

## Source Verification
- **Files Used:** app/api/sessions.py, app/engines/state_machine.py, app/services/session_init.py, app/services/db_locks.py, app/api/locks.py, app/middleware/rate_limit.py, app/security/roles.py, app/auth.py, app/config.py, app/main.py, migrations/001_init.sql, migrations/010_state_machine.sql, migrations/057_session_locks.sql, frontend/src/views/SessionsView.vue, frontend/src/views/SessionDetailView.vue, frontend/src/components/session/SessionTextEdit.vue, frontend/src/composables/useSessionLock.ts, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** SessionsView.vue, SessionDetailView.vue, SessionTextEdit.vue, useSessionLock.ts
- **APIs Used:** Sessions CRUD/lifecycle (sessions.py) + lock surface (locks.py) as tabulated above; WS /v1/ws/sessions/{id}
- **Database Tables Used:** sessions, session_audit, session_locks, session_templates, session_stage_assignees, stage_assignees, session_types, people, groups, sources, slides, speakers, segments, audit_events
- **Permission Logic Used:** JWT (CurrentUser) on all routes; SESSION_TRASH_ALLOWED email allowlist; require_admin/is_admin resolving via LEGACY_ADMIN_EMAIL email gate only; client-side adminOnly guard on /admin/help only
- **Confidence Score:** High — routes, FSM, schema, and frontend wiring read directly; later-migration column origins (title_long/short, session_type_id, finalized_at, session_stage_assignees, session_templates) tagged NOT VERIFIED IN CODE because their migration files are outside the listed source set.
- **Evidence Links:** [sessions.py:138](../../app/api/sessions.py#L138), [state_machine.py:40](../../app/engines/state_machine.py#L40), [locks.py:99](../../app/api/locks.py#L99), [057_session_locks.sql:14](../../migrations/057_session_locks.sql#L14), [auth.py:172](../../app/auth.py#L172), [roles.py:62](../../app/security/roles.py#L62)
