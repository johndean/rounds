# Sessions — Product Spec

> Module key: `sessions`. Code-verified against `HEAD` on 2026-06-08.
> Every claim below is traced to a source file with a `file:line` link.
> Paths are relative to this file (`docs/product/`).

## Overview

The Sessions module is the operator's catalog of continuing-education
recordings moving through the rounds.vin transcription pipeline. It provides a
filterable list of every non-deleted session, a per-session detail page, inline
metadata editing, soft-delete / restore / permanent-purge lifecycle, per-stage
assignee management, a status state machine, a concurrent-edit lock for the
editor, and per-user upload concurrency limiting.

The list and create/read/update/delete surface live in
[app/api/sessions.py](../../app/api/sessions.py). Status changes are funnelled
through the state machine in
[app/engines/state_machine.py](../../app/engines/state_machine.py). The editor
lock surface lives in [app/api/locks.py](../../app/api/locks.py). The two
operator-facing screens are
[frontend/src/views/SessionsView.vue](../../frontend/src/views/SessionsView.vue)
(list) and
[frontend/src/views/SessionDetailView.vue](../../frontend/src/views/SessionDetailView.vue)
(detail).

## Purpose

- Give operators a single place to see which recordings exist and where each one
  is in processing ([SessionsView.vue:144](../../frontend/src/views/SessionsView.vue#L144)).
- Persist the pipeline routing chosen at upload alongside the session row so the
  ingest worker always finds a config ([sessions.py:178](../../app/api/sessions.py#L178)).
- Enforce that the `sessions.status` field can only move along legal transitions
  ([state_machine.py:40](../../app/engines/state_machine.py#L40)).
- Let operators rename / re-code a session and reassign per-stage owners after
  upload ([sessions.py:569](../../app/api/sessions.py#L569),
  [sessions.py:379](../../app/api/sessions.py#L379)).
- Protect against two operators silently overwriting each other's editor changes
  ([locks.py:99](../../app/api/locks.py#L99)).

## User Value

- **A filterable session list** with KPI tiles (In Workflow, Processing,
  Published, Total) and filter chips (All / In Workflow / Processing / Published)
  ([SessionsView.vue:163](../../frontend/src/views/SessionsView.vue#L163),
  [SessionsView.vue:84](../../frontend/src/views/SessionsView.vue#L84)).
- **Search** by title or presenter, plus deep-link filters via `?stage=`, `?ai=`,
  and `?f=` query params ([SessionsView.vue:33](../../frontend/src/views/SessionsView.vue#L33),
  [sessions.py:138](../../app/api/sessions.py#L138)).
- **A failure-detail modal**: clicking the "Failed · why?" pill on a failed row
  surfaces the last failed transition, its reason/category, and the recent
  transition tail ([SessionsView.vue:129](../../frontend/src/views/SessionsView.vue#L129),
  [sessions.py:753](../../app/api/sessions.py#L753)).
- **Inline title / code editing** click-to-edit on the detail page, committing via
  PATCH ([SessionTextEdit.vue:67](../../frontend/src/components/session/SessionTextEdit.vue#L67),
  [sessions.py:569](../../app/api/sessions.py#L569)).
- **Per-stage assignment** with Type-matrix defaults and manual overrides
  ([SessionDetailView.vue:531](../../frontend/src/views/SessionDetailView.vue#L531),
  [sessions.py:345](../../app/api/sessions.py#L345)).

## Navigation

- The list is the route the catch-all and primary nav target. The list view is
  labelled `data-screen-label="Sessions List"`
  ([SessionsView.vue:144](../../frontend/src/views/SessionsView.vue#L144)).
- Clicking a row routes to `/p/{id}` when the session is still `ingesting`
  (processing view) or `/s/{id}` otherwise (detail view)
  ([SessionsView.vue:98](../../frontend/src/views/SessionsView.vue#L98)).
- The detail page links to `/e/{id}` (Editor), `/e/{id}/sop` (Workflow), and
  `/e/{id}/audit` (Audit) ([SessionDetailView.vue:387](../../frontend/src/views/SessionDetailView.vue#L387)).
- "New upload" routes to `/upload`; "Export CSV" raises a success toast only — no
  backend export call is made ([SessionsView.vue:102](../../frontend/src/views/SessionsView.vue#L102),
  [SessionsView.vue:157](../../frontend/src/views/SessionsView.vue#L157)).

## Screens

### Sessions list (`SessionsView.vue`)

- Page eyebrow (`Workspace / Sessions`), title, and description
  ([SessionsView.vue:145](../../frontend/src/views/SessionsView.vue#L145)).
- KPI row computed client-side from the loaded rows
  ([SessionsView.vue:163](../../frontend/src/views/SessionsView.vue#L163)).
- Toolbar: search input, filter-chip row, and a client-side sort selector
  (Last updated / Code / Title). **The sort selector is bound to `sortBy` but
  the `filtered` computed does not apply it** — sorting is display-only state
  with no effect ([SessionsView.vue:182](../../frontend/src/views/SessionsView.vue#L182),
  [SessionsView.vue:61](../../frontend/src/views/SessionsView.vue#L61)).
- Sessions table with columns: Code, Session (title + presenter), AI Status, SOP,
  Segs, Words, and a delete action ([SessionsView.vue:220](../../frontend/src/views/SessionsView.vue#L220)).
- The "SOP" column renders a hardcoded `StageBadge id="prep"` for every row — it
  does not reflect the row's real SOP stage
  ([SessionsView.vue:258](../../frontend/src/views/SessionsView.vue#L258)).
- Failure-detail modal ([SessionsView.vue:284](../../frontend/src/views/SessionsView.vue#L284)).

### Session detail (`SessionDetailView.vue`)

- Header strip: status chip, inline-editable code chip, inline-editable title,
  presenter, and review/aligned chips, with Workflow / Audit / Open Editor links
  ([SessionDetailView.vue:353](../../frontend/src/views/SessionDetailView.vue#L353)).
- Three-column grid: left meta + downloads, center KPIs + AI-mode + session-files,
  right stage-assignments + publishing-links
  ([SessionDetailView.vue:393](../../frontend/src/views/SessionDetailView.vue#L393)).
- Timeline bar, segment-confidence, slide-assignment, and review-queue widgets
  ([SessionDetailView.vue:668](../../frontend/src/views/SessionDetailView.vue#L668)).
- Downloads buttons (`.docx`, `.srt`, `.txt`, `.zip`) and publishing-link chips
  are **not wired** — they raise honest "not yet wired / not persisted" warn
  toasts ([SessionDetailView.vue:299](../../frontend/src/views/SessionDetailView.vue#L299),
  [SessionDetailView.vue:329](../../frontend/src/views/SessionDetailView.vue#L329)).

> NOTE: The detail page also fetches `/sources`, `/slides`, `/segments`,
> `/stage-assignees`, `/chat-participants`, and Settings types/people/groups
> ([SessionDetailView.vue:97](../../frontend/src/views/SessionDetailView.vue#L97)).
> Of these, only the `stage-assignees` endpoint lives in the Sessions module
> ([sessions.py:345](../../app/api/sessions.py#L345)); `/sources` and `/slides`
> are served by `app/api/session_resources.py` and `/segments` by
> `app/api/segments.py` (other modules — referenced here only because this screen
> consumes them).

## User Flows

### Create a session (upload path)

`POST /v1/sessions` inserts a `sessions` row with status `'uploading'` and a
matching `session_templates` row carrying pipeline routing, in one transaction
([sessions.py:178](../../app/api/sessions.py#L178)). Code collisions on the
`sessions_code_key` unique constraint return a `409 CONFLICT` envelope rather
than a 500 ([sessions.py:219](../../app/api/sessions.py#L219)).

### Rename / re-code

Inline click-to-edit swaps the display span for an `<input>`; blur or Enter
commits via `PATCH /v1/sessions/{id}`; Escape cancels
([SessionTextEdit.vue:54](../../frontend/src/components/session/SessionTextEdit.vue#L54)).
A duplicate code returns `409` and the input stays open for retry
([SessionTextEdit.vue:82](../../frontend/src/components/session/SessionTextEdit.vue#L82),
[sessions.py:605](../../app/api/sessions.py#L605)).

### Reassign a stage owner

The detail page's Stage Assignments card lets an operator pick a person or group
per stage, which calls `PUT /v1/sessions/{id}/stage-assignees/{stage}` and marks
`source='manual'` ([SessionDetailView.vue:178](../../frontend/src/views/SessionDetailView.vue#L178),
[sessions.py:379](../../app/api/sessions.py#L379)). An empty body resets the stage
to its Type-matrix default and flips `source` back to `'default'`
([sessions.py:424](../../app/api/sessions.py#L424)).

### Change session Type / apply defaults

Choosing a new Type immediately PATCHes `session_type_id` and shows a "Type
changed — apply defaults?" banner ([SessionDetailView.vue:131](../../frontend/src/views/SessionDetailView.vue#L131)).
Confirming calls `POST /v1/sessions/{id}/stage-assignees/apply-type-defaults`,
which **wipes all existing per-session stage rows** then re-seeds them from the
Type matrix via `init_session_stages`
([sessions.py:498](../../app/api/sessions.py#L498),
[session_init.py:27](../../app/services/session_init.py#L27)).

### Soft-delete / restore / purge

- Soft-delete sets `deleted_at` and releases the rate-limit slot
  ([sessions.py:621](../../app/api/sessions.py#L621)). The list page confirms with
  a danger dialog before calling `DELETE`
  ([SessionsView.vue:106](../../frontend/src/views/SessionsView.vue#L106)).
- Restore clears `deleted_at` ([sessions.py:668](../../app/api/sessions.py#L668)).
- Permanent delete hard-deletes the row (and cascading children) — only allowed
  after a soft-delete ([sessions.py:697](../../app/api/sessions.py#L697)).

### Concurrent editing

When the Editor opens, `useSessionLock` acquires the lock and heartbeats every
interval; a non-holder drops to read-only and sees the holder banner
([useSessionLock.ts:88](../../frontend/src/composables/useSessionLock.ts#L88)).
If the lock service is unreachable the frontend fails closed
([useSessionLock.ts:55](../../frontend/src/composables/useSessionLock.ts#L55)).

## Business Rules

- **One state-machine path (BR-007).** `sessions.status` may only move along
  `ALLOWED_TRANSITIONS`. `failed` and `complete` are terminal
  ([state_machine.py:40](../../app/engines/state_machine.py#L40),
  [state_machine.py:49](../../app/engines/state_machine.py#L49)). See **States**
  for the actual map.
- **Soft-delete carve-out (BR-002).** Only emails in `SESSION_TRASH_ALLOWED`
  (`johndean@vin.com` plus `carlab@vin.com`) may soft-delete
  ([sessions.py:52](../../app/api/sessions.py#L52),
  [sessions.py:630](../../app/api/sessions.py#L630)).
- **Restore and permanent-purge are admin-only.** Both call `require_admin`,
  which (today) resolves admin solely via the `LEGACY_ADMIN_EMAIL` email gate
  ([sessions.py:674](../../app/api/sessions.py#L674),
  [sessions.py:707](../../app/api/sessions.py#L707), see **Permissions**).
- **Permanent delete requires a prior soft-delete** ([sessions.py:718](../../app/api/sessions.py#L718)).
- **30-day recovery window.** The deleted-sessions listing only shows rows
  soft-deleted within the last 30 days; older rows are hidden but not yet purged
  ([sessions.py:266](../../app/api/sessions.py#L266)).
- **Title precedence cascade (BR-019).** Display title prefers `title_long`, then
  `title_short`, then `title` ([SessionDetailView.vue:53](../../frontend/src/views/SessionDetailView.vue#L53),
  [SessionsView.vue:239](../../frontend/src/views/SessionsView.vue#L239)).
- **Per-user concurrency cap.** `MAX_CONCURRENT_SESSIONS = 3` and
  `MAX_QUEUE_LENGTH = 10` enforced at upload time (not at `POST /v1/sessions`)
  ([config.py:46](../../app/config.py#L46),
  [rate_limit.py:33](../../app/middleware/rate_limit.py#L33)).

## Validation Rules

- `code`: required, 1–64 chars; `title`: required, 1–512 chars
  ([sessions.py:71](../../app/api/sessions.py#L71)).
- `code` is `UNIQUE` at the DB level (`sessions_code_key`); duplicates surface as
  `409` on create and PATCH ([001_init.sql:15](../../migrations/001_init.sql#L15),
  [sessions.py:223](../../app/api/sessions.py#L223),
  [sessions.py:605](../../app/api/sessions.py#L605)).
- PATCH is a whitelist of `code`, `title`, `title_long`, `title_short`,
  `presenter`, `session_type_id`; `model_dump(exclude_unset=True)` means `null`
  leaves a field unchanged while `""` clears it; an empty patch returns `400`
  ([sessions.py:106](../../app/api/sessions.py#L106),
  [sessions.py:587](../../app/api/sessions.py#L587)).
- Stage-assignee resolution: typed `person_id`/`group_id` win, else
  `assignee_email` is parsed (`Group: …` → group, `(unassigned)` → reset, else
  person lookup) ([sessions.py:404](../../app/api/sessions.py#L404)). The DB
  CHECK `chk_session_stage_assignees_single_assignee` guarantees at most one of
  person/group is set ([sessions.py:399](../../app/api/sessions.py#L399)).
- SessionTextEdit no-ops when the trimmed draft equals the current value
  ([SessionTextEdit.vue:71](../../frontend/src/components/session/SessionTextEdit.vue#L71)).

## States

`sessions.status` is constrained by a DB CHECK to exactly these eight values
([010_state_machine.sql:23](../../migrations/010_state_machine.sql#L23)):

`uploading`, `transcribing`, `normalizing`, `fusing`, `aligning`, `ready`,
`complete`, `failed`.

Legal transitions ([state_machine.py:40](../../app/engines/state_machine.py#L40)):

| From | Allowed next |
|---|---|
| `uploading` | `transcribing`, `ready`, `failed` |
| `transcribing` | `normalizing`, `failed` |
| `normalizing` | `fusing`, `failed` |
| `fusing` | `aligning`, `failed` |
| `aligning` | `ready`, `failed` |
| `ready` | `complete`, `failed` |
| `complete` | (terminal) |
| `failed` | (terminal) |

- `uploading → ready` is the AI-direct path that skips intermediate stages
  ([state_machine.py:38](../../app/engines/state_machine.py#L38)).
- `failed` and `complete` are terminal — any transition out raises `ConflictError`
  → `409` ([state_machine.py:140](../../app/engines/state_machine.py#L140)).
- New rows are inserted as `'uploading'` ([sessions.py:205](../../app/api/sessions.py#L205)).
  Migration 001's `DEFAULT 'ingesting'` is superseded: migration 010 normalizes
  legacy `ingesting → uploading` and the CHECK rejects `ingesting`
  ([001_init.sql:24](../../migrations/001_init.sql#L24),
  [010_state_machine.sql:19](../../migrations/010_state_machine.sql#L19)).

> FLAG: the frontend uses status strings the backend CHECK does NOT permit —
> `SessionsView.vue` filters on `'ingesting'` and `'archived'`
> ([SessionsView.vue:63](../../frontend/src/views/SessionsView.vue#L63)). Those
> values can never appear in a current `sessions.status`, so the "In Workflow",
> "Processing", and "Published"/"complete + archived" client filters do not match
> live data the way the labels imply. **PARTIALLY IMPLEMENTED.**

Editor lock states (`session_locks` row): held-by-self, held-by-other (fresh),
or stale (expired past `expires_at`), with TTL = 90 seconds = 3 missed
30-second heartbeats ([locks.py:42](../../app/api/locks.py#L42),
[057_session_locks.sql:19](../../migrations/057_session_locks.sql#L19)).

## Dependencies

- **State machine** — every status mutation must route through it
  ([state_machine.py](../../app/engines/state_machine.py)).
- **`session_templates`** — pipeline config row written at create
  ([sessions.py:232](../../app/api/sessions.py#L232)).
- **`session_types` / `stage_assignees` matrix** — source of per-session stage
  defaults ([session_init.py:69](../../app/services/session_init.py#L69)).
- **`people` / `groups`** — joined to resolve stage assignee display labels
  ([sessions.py:360](../../app/api/sessions.py#L360)).
- **Redis rate-limit slots** — concurrency cap and slot release
  ([rate_limit.py:33](../../app/middleware/rate_limit.py#L33)).
- **WebSocket bridge** — each transition emits a `processing_update` event
  ([state_machine.py:98](../../app/engines/state_machine.py#L98)).
- **Auth** — every endpoint requires a valid JWT (`CurrentUser`)
  ([auth.py:172](../../app/auth.py#L172)).

## Error Handling

- **404** when a session is missing or soft-deleted on get / patch
  ([sessions.py:564](../../app/api/sessions.py#L564),
  [sessions.py:615](../../app/api/sessions.py#L615)).
- **409 CONFLICT** on duplicate code (create/patch), already-deleted soft-delete,
  not-deleted restore, and not-soft-deleted purge
  ([sessions.py:224](../../app/api/sessions.py#L224),
  [sessions.py:643](../../app/api/sessions.py#L643),
  [sessions.py:685](../../app/api/sessions.py#L685),
  [sessions.py:718](../../app/api/sessions.py#L718)).
- **409** on illegal state transition, raised as `ConflictError` by the FSM
  ([state_machine.py:146](../../app/engines/state_machine.py#L146)).
- **403** on delete by a non-allowlisted user, and on admin-only routes
  ([sessions.py:630](../../app/api/sessions.py#L630),
  [sessions.py:674](../../app/api/sessions.py#L674)).
- **400** on empty PATCH body ([sessions.py:589](../../app/api/sessions.py#L589)).
- **500** on a cascade-delete failure; the row is rolled back and the error class
  is surfaced ([sessions.py:734](../../app/api/sessions.py#L734)).
- The failure-reason endpoint reads the last failed audit entry to explain a
  `failed` session ([sessions.py:753](../../app/api/sessions.py#L753)).
- Frontend list/detail show inline error strings on load failure
  ([SessionsView.vue:42](../../frontend/src/views/SessionsView.vue#L42),
  [SessionDetailView.vue:117](../../frontend/src/views/SessionDetailView.vue#L117)).

## Permissions

> PERMISSION REALITY (verified): role-based authorization is **not active**. The
> `User` object carries only `email` — `get_current_user` never reads
> `auth_users.role` ([auth.py:37](../../app/auth.py#L37),
> [auth.py:172](../../app/auth.py#L172)).

- Every Sessions and lock endpoint requires a valid JWT (`CurrentUser` dependency)
  ([sessions.py:25](../../app/api/sessions.py#L25),
  [locks.py:36](../../app/api/locks.py#L36)).
- **Soft-delete** is gated to `SESSION_TRASH_ALLOWED` =
  `{johndean@vin.com, carlab@vin.com}` ([sessions.py:52](../../app/api/sessions.py#L52),
  [sessions.py:630](../../app/api/sessions.py#L630)).
- **List-deleted, restore, permanent-delete** call `require_admin`, and
  **lock force-take** calls `is_admin` ([sessions.py:276](../../app/api/sessions.py#L276),
  [sessions.py:674](../../app/api/sessions.py#L674),
  [sessions.py:707](../../app/api/sessions.py#L707),
  [locks.py:225](../../app/api/locks.py#L225)). These helpers are wired into the
  endpoints, but because no caller passes a `role=` and no role is loaded onto the
  user, they resolve admin **only** by comparing `user.email == 'johndean@vin.com'`
  (`LEGACY_ADMIN_EMAIL`) ([roles.py:62](../../app/security/roles.py#L62),
  [roles.py:88](../../app/security/roles.py#L88)).
- `app/security/roles.py` ships a role-aware code path (`is_admin(user, role=...)`)
  but it is **scaffold only** until `get_current_user` loads `auth_users.role`
  ([roles.py:10](../../app/security/roles.py#L10)). **PARTIALLY IMPLEMENTED** —
  role tiers exist in code but are inert.
- There is one client-side route guard: `/admin/help` (`meta.adminOnly`) redirects
  non-`johndean@vin.com` users to the dashboard. No Sessions route uses
  `adminOnly` ([router/index.ts:63](../../frontend/src/router/index.ts#L63)).
- The list page renders the delete button for every row regardless of viewer; the
  `403` is enforced server-side on the DELETE call
  ([SessionsView.vue:262](../../frontend/src/views/SessionsView.vue#L262)).

## Reporting Impacts

- The "Export CSV" button raises a toast only — **no report is generated or
  downloaded** ([SessionsView.vue:102](../../frontend/src/views/SessionsView.vue#L102)).
  IMPLEMENTATION NOT FOUND for a sessions CSV export endpoint.
- KPI tiles (In Workflow / Processing / Published / Total) are computed entirely
  client-side from the loaded page of rows, not from a reporting endpoint
  ([SessionsView.vue:163](../../frontend/src/views/SessionsView.vue#L163)).
  Because they key off `status === 'ingesting'` / `'ready'` / `'complete'`, the
  "Processing" tile (which counts `ingesting`) will read 0 against current data
  (see **States** flag).
- Word/segment counts shown in the table come straight from
  `sessions.word_count` / `segment_count` columns
  ([SessionsView.vue:259](../../frontend/src/views/SessionsView.vue#L259),
  [001_init.sql:20](../../migrations/001_init.sql#L20)).
- No revenue/finance figures exist anywhere in this module. NOT VERIFIED IN CODE.

## Audit Requirements

- Every state transition appends one entry to `session_audit.processing_log`
  (a JSONB array) with `{stage, status, started_at, completed_at, actor, reason,
  metadata}` ([state_machine.py:52](../../app/engines/state_machine.py#L52),
  [010_state_machine.sql:31](../../migrations/010_state_machine.sql#L31)).
- `GET /v1/sessions/{id}/audit-log` returns that processing log
  ([sessions.py:306](../../app/api/sessions.py#L306)).
- `GET /v1/sessions/{id}/failure-reason` derives the failure explanation from the
  same log ([sessions.py:753](../../app/api/sessions.py#L753)).
- Lock **force-take** writes an `audit_events` row
  (`kind = 'session.lock_force_take'`) capturing the prior holder
  ([locks.py:246](../../app/api/locks.py#L246)).
- There is **no per-field metadata audit** — PATCH on title/code/presenter is not
  recorded in any audit table; only status transitions and force-takes are
  logged. **PARTIALLY IMPLEMENTED** (matches the seed doc's "Known gaps").

## Data Relationships

- `sessions` (PK `id`) is the parent. Children with `ON DELETE CASCADE`:
  `sources`, `slides`, `speakers`, `segments`, and `session_audit`
  ([001_init.sql:36](../../migrations/001_init.sql#L36),
  [010_state_machine.sql:32](../../migrations/010_state_machine.sql#L32)).
- `segments.slide_id` → `slides` and `segments.speaker_id` → `speakers` are
  `ON DELETE SET NULL` ([001_init.sql:85](../../migrations/001_init.sql#L85)).
- `sessions.session_type_id` → `session_types`; the chosen Type drives stage
  defaults ([sessions.py:103](../../app/api/sessions.py#L103),
  [session_init.py:69](../../app/services/session_init.py#L69)).
- `session_templates` holds one pipeline-config row per session
  ([sessions.py:232](../../app/api/sessions.py#L232)).
- `session_stage_assignees` holds one row per (session, stage), each pointing at a
  `person` or `group` ([sessions.py:455](../../app/api/sessions.py#L455)).
- `session_locks` holds one row per session being edited (PK = `session_id`)
  ([057_session_locks.sql:14](../../migrations/057_session_locks.sql#L14)).
- Permanent delete relies on the parent CASCADE; `audit_events.session_id` is
  intentionally `ON DELETE SET NULL` so forensic events survive
  ([sessions.py:722](../../app/api/sessions.py#L722)).

## Known Constraints

- The list endpoint defaults to `limit=50, offset=0` and orders by
  `created_at DESC, code DESC`; there is no UI pagination — the page renders one
  server page ([sessions.py:146](../../app/api/sessions.py#L146)).
- The list `?ai=` filter matches `sessions.status` exactly; combined with the
  non-existent `ingesting`/`archived` statuses, several documented filters cannot
  match live rows (see **States**) ([sessions.py:155](../../app/api/sessions.py#L155)).
- The list sort selector is non-functional ([SessionsView.vue:212](../../frontend/src/views/SessionsView.vue#L212)).
- SOP stage in the list is hardcoded to `prep`
  ([SessionsView.vue:258](../../frontend/src/views/SessionsView.vue#L258)).
- No bulk session actions (delete/restore/reassign are one-at-a-time) — confirmed,
  matches the seed doc.
- Downloads and publishing-link buttons on the detail page are not wired
  ([SessionDetailView.vue:299](../../frontend/src/views/SessionDetailView.vue#L299)).
- The editor lock TTL is 90s; a crashed tab blocks others for up to that long
  unless an admin force-takes ([locks.py:42](../../app/api/locks.py#L42)).
- The advisory-lock service (`db_locks.py`) is a **separate** mechanism from the
  editor lock — it serializes ingest/correction work via Postgres advisory locks
  and is not exposed as a Sessions route
  ([db_locks.py:70](../../app/services/db_locks.py#L70)).

## Source Verification
- **Files Used:** app/api/sessions.py, app/engines/state_machine.py, app/services/session_init.py, app/services/db_locks.py, app/api/locks.py, app/middleware/rate_limit.py, app/security/roles.py, app/auth.py, app/config.py, app/main.py, migrations/001_init.sql, migrations/010_state_machine.sql, migrations/057_session_locks.sql, frontend/src/views/SessionsView.vue, frontend/src/views/SessionDetailView.vue, frontend/src/components/session/SessionTextEdit.vue, frontend/src/composables/useSessionLock.ts, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** SessionsView.vue, SessionDetailView.vue, SessionTextEdit.vue, useSessionLock.ts (composable)
- **APIs Used:** GET/POST /v1/sessions, GET /v1/sessions/{id}, PATCH /v1/sessions/{id}, DELETE /v1/sessions/{id}, POST /v1/sessions/{id}/restore, DELETE /v1/sessions/{id}/permanent, GET /v1/sessions/deleted, GET /v1/sessions/{id}/audit-log, GET /v1/sessions/{id}/failure-reason, GET /v1/sessions/{id}/pipeline-config, GET/PUT /v1/sessions/{id}/stage-assignees[/{stage}], POST /v1/sessions/{id}/stage-assignees/apply-type-defaults, POST /v1/sessions/{id}/lock/{acquire,heartbeat,release,force-take}, GET /v1/sessions/{id}/lock/holder
- **Database Tables Used:** sessions, session_templates, session_audit, session_stage_assignees, stage_assignees, session_types, people, groups, sources, slides, speakers, segments, session_locks, audit_events
- **Permission Logic Used:** JWT (CurrentUser) on all routes; SESSION_TRASH_ALLOWED email allowlist for soft-delete; require_admin/is_admin resolving solely via LEGACY_ADMIN_EMAIL email gate for restore/purge/force-take; client-side adminOnly guard on /admin/help only (not Sessions)
- **Confidence Score:** High — all claims traced to read source lines; uncertainties tagged inline.
- **Evidence Links:** [sessions.py:178](../../app/api/sessions.py#L178), [state_machine.py:40](../../app/engines/state_machine.py#L40), [010_state_machine.sql:23](../../migrations/010_state_machine.sql#L23), [locks.py:99](../../app/api/locks.py#L99), [roles.py:88](../../app/security/roles.py#L88), [auth.py:37](../../app/auth.py#L37)
