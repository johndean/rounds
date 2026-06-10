# Dashboard — Technical Spec

> Module key: `dashboard`. Surfaces: `/dashboard` ([frontend/src/views/DashboardView.vue](../../frontend/src/views/DashboardView.vue)) and the per-user work queue `/queue` ([frontend/src/views/QueueView.vue](../../frontend/src/views/QueueView.vue)). Paths in links are relative to this file (`docs/technical/`). Every claim is verified against the cited source line.

## Architecture

The Dashboard is a client-rendered Vue 3 SFC (`<script setup lang="ts">`) served by the hash-mode router ([frontend/src/router/index.ts:22](../../frontend/src/router/index.ts#L22), [:30](../../frontend/src/router/index.ts#L30)). It has **no dedicated backend route**; it composes its data from two existing read endpoints:

- `GET /v1/sessions` — the session list ([app/api/sessions.py:138](../../app/api/sessions.py#L138)), mounted via `sessions_router` ([app/main.py:214](../../app/main.py#L214)).
- `GET /v1/sop/dashboard-summary` — per-stage SOP counts + overdue counts ([app/api/sop.py:279](../../app/api/sop.py#L279)), mounted via `sop_router.global_router` ([app/main.py:223](../../app/main.py#L223)).

The `/queue` view depends on a third endpoint, `GET /v1/queue/mine` ([app/api/queue.py:45](../../app/api/queue.py#L45)), mounted via `queue_router` ([app/main.py:232](../../app/main.py#L232)). All three are FastAPI routes over SQLAlchemy `text()` SQL against Postgres.

Control flow on the Dashboard: `onMounted` fires a `Promise.all` of two service calls; each is `.catch`'d to `[]`; results land in two refs; a tree of `computed` props derives every displayed value ([frontend/src/views/DashboardView.vue:27-97](../../frontend/src/views/DashboardView.vue#L27)). There is no store, no websocket, and no polling on the Dashboard. `/queue` adds a 30s `setInterval` poll plus a `visibilitychange` refresh ([frontend/src/views/QueueView.vue:62-71](../../frontend/src/views/QueueView.vue#L62)).

## Frontend Components

- **DashboardView.vue** ([frontend/src/views/DashboardView.vue](../../frontend/src/views/DashboardView.vue)) — the page. Local reactive state: `allSessions`, `sopSummary`, `loading`, `pipelineFilter`, `timeRange` ([:23-25](../../frontend/src/views/DashboardView.vue#L23), [:40-41](../../frontend/src/views/DashboardView.vue#L40)). Imports `Icon`, `StageBadge`, `Sparkline`, the `SOP_STAGES` fixture, the `sessions`/`sop` API services, and `useAuthStore` ([:11-18](../../frontend/src/views/DashboardView.vue#L11)).
- **QueueView.vue** ([frontend/src/views/QueueView.vue](../../frontend/src/views/QueueView.vue)) — the per-user queue list. Local state: `items`, `loading`, `error`; module-scoped `inFlight` guard and `pollHandle` ([:21-23](../../frontend/src/views/QueueView.vue#L21), [:32-33](../../frontend/src/views/QueueView.vue#L32)). Scoped styles are self-contained (`.route`, `.queue-row`, etc.) ([:152-202](../../frontend/src/views/QueueView.vue#L152)).
- **Sparkline.vue** ([frontend/src/components/dashboard/Sparkline.vue](../../frontend/src/components/dashboard/Sparkline.vue)) — pure presentational. Props: `data: readonly number[]`. Computes `isEmpty` (`< 2` points) and a normalized `points` string for a `100×18` viewBox polyline (`stroke="currentColor"`). Renders an empty `.dash-spark--empty` div when empty ([:9-32](../../frontend/src/components/dashboard/Sparkline.vue#L9)). On the Dashboard, every `spark` array is `[]`, so this component always renders the empty branch ([frontend/src/views/DashboardView.vue:51-67](../../frontend/src/views/DashboardView.vue#L51)).
- **StageBadge.vue** ([frontend/src/components/shared/StageBadge.vue](../../frontend/src/components/shared/StageBadge.vue)) — resolves a stage `id` to `<order>. <name>` from `SOP_STAGE_BY_ID`. Used in the Dashboard's queue cards with a hardcoded `id="prep"` ([frontend/src/views/DashboardView.vue:161](../../frontend/src/views/DashboardView.vue#L161)). Note: the queue card badge is always "1. Prep" regardless of the session's real stage. PARTIALLY IMPLEMENTED.

### Key computed properties (DashboardView)

| Computed | Source | Live? |
|---|---|---|
| `aiCount` | `allSessions.length` ([:43](../../frontend/src/views/DashboardView.vue#L43)) | live (bounded by 50, see Performance) |
| `readyCount` | sessions with status `ready`/`complete` ([:44](../../frontend/src/views/DashboardView.vue#L44)) | live |
| `processingCount` | sessions with status `ingesting` ([:45](../../frontend/src/views/DashboardView.vue#L45)) | live |
| `segmentTotal` | sum of `segment_count` ([:46](../../frontend/src/views/DashboardView.vue#L46)) | live |
| `wordTotal` | sum of `word_count` ([:47](../../frontend/src/views/DashboardView.vue#L47)) | live |
| `topKpis` | 6-card array; "SOP Sessions" = `aiCount`, "Improvement RQs" = 0 ([:50-57](../../frontend/src/views/DashboardView.vue#L50)) | mixed |
| `queue` | `allSessions.slice(0, 3)` ([:59](../../frontend/src/views/DashboardView.vue#L59)) | live (most-recent-3, not assignee) |
| `opsKpis` | static array of zeros/dashes ([:61-68](../../frontend/src/views/DashboardView.vue#L61)) | placeholder |
| `sla` | `SOP_STAGES.map(...)` all `state:'empty'`, `dAvg:null` ([:71-73](../../frontend/src/views/DashboardView.vue#L71)) | placeholder |
| `aiPipeline` | 7 fixed steps; only transcribe/ready/failed derive counts ([:75-83](../../frontend/src/views/DashboardView.vue#L75)) | mixed |
| `sopPipeline` | joins `sopSummary` to `SOP_STAGES`, sets `count` + `attn` ([:90-97](../../frontend/src/views/DashboardView.vue#L90)) | live |

## Backend Services

There is no dashboard-specific service layer. The endpoints inline their SQL:

- **`list_sessions`** ([app/api/sessions.py:138-175](../../app/api/sessions.py#L138)) — builds a parameterized `WHERE deleted_at IS NULL` query, optionally appending `status = :ai`, a `LOWER(code/title) LIKE :f` free-text clause, and a conditional `JOIN sop_state ON ... AND current_stage = :stage`. Orders `created_at DESC NULLS LAST, code DESC`, `LIMIT :limit OFFSET :offset` (default limit 50).
- **`dashboard_summary`** ([app/api/sop.py:279-325](../../app/api/sop.py#L279)) — selects `current_stage, entered_current_at, sla_target_hours` for all `sop_state` rows, then computes counts and overdue counts in Python so the overdue rule stays in lock with `sop_check_deadlines_task` and the SopView client fallback. Returns one row per stage in canonical order.
- **`list_my_queue`** ([app/api/queue.py:45-143](../../app/api/queue.py#L45)) — selects sessions joined to `sop_state` where the COALESCE of the nested-object and flat-string assignee paths equals `:email`, excluding soft-deleted and `complete`-stage rows, ordered `entered_current_at ASC NULLS LAST`, `LIMIT 200`. Computes `overdue_hours` in Python.

## APIs

### GET /v1/sessions
Query params: `stage`, `ai`, `f`, `limit` (default 50), `offset` (default 0) ([app/api/sessions.py:142-147](../../app/api/sessions.py#L142)). Returns `list[SessionOut]` with `id, code, title, title_long, title_short, presenter, status, duration_sec, word_count, segment_count, attendee_count, taxonomy, session_type_id` ([app/api/sessions.py:162-165](../../app/api/sessions.py#L162); response model fields [:94-97](../../app/api/sessions.py#L94)). The Dashboard calls it with no params (`sessions.list({})`) ([frontend/src/views/DashboardView.vue:30](../../frontend/src/views/DashboardView.vue#L30); service [frontend/src/services/api.ts:137-138](../../frontend/src/services/api.ts#L137)).

### GET /v1/sop/dashboard-summary
No params. Returns `list[StageSummaryRow]` = `{ stage: str, count: int, overdue_count: int }`, one per stage, canonical order ([app/api/sop.py:273-276](../../app/api/sop.py#L273), [:322-325](../../app/api/sop.py#L322)). Service: `sop.dashboardSummary` ([frontend/src/services/api.ts:634-637](../../frontend/src/services/api.ts#L634)).

### GET /v1/queue/mine
No params (user comes from the JWT). Returns `list[QueueItemOut]` = `{ session_id, code, title, title_short, title_long, status, current_stage, entered_current_at, overdue_hours }` ([app/api/queue.py:32-43](../../app/api/queue.py#L32)). Service: `queue.mine` ([frontend/src/services/api.ts:366](../../frontend/src/services/api.ts#L366)); TS type `QueueItem` mirrors the model ([frontend/src/services/api.ts:350-360](../../frontend/src/services/api.ts#L350)).

## Data Models

- **`SessionOut` / `SessionSummary`** — backend Pydantic ([app/api/sessions.py:94-97](../../app/api/sessions.py#L94)) and TS interface ([frontend/src/services/api.ts:37-57](../../frontend/src/services/api.ts#L37)). Dashboard consumes `length`, `status`, `segment_count`, `word_count`, `code`, `title`, `presenter`, `id` ([frontend/src/views/DashboardView.vue:43-69](../../frontend/src/views/DashboardView.vue#L43)).
- **`StageSummaryRow`** — `{ stage, count, overdue_count }` ([app/api/sop.py:273-276](../../app/api/sop.py#L273)); typed inline on the service as `Array<{ stage; count; overdue_count }>` ([frontend/src/services/api.ts:635](../../frontend/src/services/api.ts#L635)).
- **`QueueItemOut` / `QueueItem`** — ([app/api/queue.py:32-43](../../app/api/queue.py#L32); [frontend/src/services/api.ts:350-360](../../frontend/src/services/api.ts#L350)).
- **`SopStage` fixture** — `{ id, name, order, checks[] }`, 8 frozen entries, mirrors `data.jsx::SOP_STAGES` ([frontend/src/fixtures/sop_stages.ts:5-29](../../frontend/src/fixtures/sop_stages.ts#L5)). Backend canonical stage list is `STAGES` ([app/api/sop.py:24](../../app/api/sop.py#L24)).
- **DB tables:** `sessions` (`id, code, title[_long/_short], presenter, status, duration_sec, word_count, segment_count, attendee_count, taxonomy, session_type_id, deleted_at, created_at`) and `sop_state` (`session_id, current_stage, entered_current_at, sla_target_hours` JSONB, `assignees` JSONB) ([app/api/sessions.py:162-165](../../app/api/sessions.py#L162); [app/api/queue.py:91-107](../../app/api/queue.py#L91)).

## Events

- **No domain events emitted.** All three endpoints are read-only; `dashboard_summary` is documented "Reads only; no `audit_events` row" ([app/api/sop.py:293](../../app/api/sop.py#L293)) and `list_my_queue` "Read-only. No mutations." ([app/api/queue.py:63](../../app/api/queue.py#L63)).
- **No websocket subscription** on either view. QueueView's comment notes the WS bus is session-scoped and a user-scoped channel is out of scope for v1, which is why it polls instead ([frontend/src/views/QueueView.vue:26-30](../../frontend/src/views/QueueView.vue#L26)).
- **DOM events:** Dashboard click handlers call `router.push` for pipeline drilldowns, queue cards, and the upload button ([frontend/src/views/DashboardView.vue:129](../../frontend/src/views/DashboardView.vue#L129), [:157](../../frontend/src/views/DashboardView.vue#L157), [:205](../../frontend/src/views/DashboardView.vue#L205), [:226](../../frontend/src/views/DashboardView.vue#L226)). QueueView listens for `visibilitychange` and registers/clears a `setInterval` ([frontend/src/views/QueueView.vue:62-71](../../frontend/src/views/QueueView.vue#L62)).

## State Management

- **Dashboard:** purely local `ref`/`computed`; no Pinia store except `useAuthStore` (read-only, for the greeting email) ([frontend/src/views/DashboardView.vue:21](../../frontend/src/views/DashboardView.vue#L21), [:110-113](../../frontend/src/views/DashboardView.vue#L110)). `pipelineFilter` and `timeRange` are local refs that are toggled in the template but never read by any data-deriving computed — they are inert visual toggles ([:40-41](../../frontend/src/views/DashboardView.vue#L40), [:184-192](../../frontend/src/views/DashboardView.vue#L184), [:245-252](../../frontend/src/views/DashboardView.vue#L245)).
- **Queue:** local refs plus module-level `inFlight`/`pollHandle`. Concurrency is guarded so interval + visibility refreshes can't overlap (`if (inFlight) return`) ([frontend/src/views/QueueView.vue:36-37](../../frontend/src/views/QueueView.vue#L36)); the poll is torn down in `onBeforeUnmount` ([:68-71](../../frontend/src/views/QueueView.vue#L68)).

## Validation

No input validation exists in this module — neither view submits a form or performs a write. Defensive client guards: `Math.max(0, …)` on elapsed-hours formatting to avoid negative durations from clock skew ([frontend/src/views/QueueView.vue:84](../../frontend/src/views/QueueView.vue#L84)); the overdue pill renders only when `overdue_hours > 0` ([:140](../../frontend/src/views/QueueView.vue#L140)). Backend guards: `dashboard_summary` skips stages not in `STAGES` ([app/api/sop.py:306-307](../../app/api/sop.py#L306)); SLA override is applied only when it is an `int` ([app/api/queue.py:124-126](../../app/api/queue.py#L124); [app/api/sop.py:315](../../app/api/sop.py#L315)).

## Security

- All three endpoints require a valid JWT via the `CurrentUser` FastAPI dependency ([app/api/sessions.py:141](../../app/api/sessions.py#L141); [app/api/sop.py:280](../../app/api/sop.py#L280); [app/api/queue.py:46](../../app/api/queue.py#L46)). `get_current_user` decodes the JWT with `settings.API_SECRET_KEY`, verifies the user is active (DB lookup, env-CSV fallback so existing JWTs survive migration cutover), and returns `User(email=…)` ([app/auth.py:172-205](../../app/auth.py#L172)).
- SQL is parameterized via bound params (`:email`, `:ai`, `:f`, `:stage`, `:limit`, `:offset`); free-text is lower-cased and wrapped in `%…%` before binding, not string-interpolated ([app/api/sessions.py:159-160](../../app/api/sessions.py#L159); [app/api/queue.py:112](../../app/api/queue.py#L112)). The only string-interpolated SQL fragment in `list_sessions` is the static JOIN clause selected by the presence of `stage`, not the value ([app/api/sessions.py:167](../../app/api/sessions.py#L167)).
- `/v1/queue/mine` scopes rows to `user.email`, so a user cannot read another user's queue ([app/api/queue.py:104-112](../../app/api/queue.py#L104)).

## Permissions

Authorization is **JWT presence only**; there are no role tiers in effect for this module.

- `get_current_user` returns a `User` dataclass whose only field is `email` ([app/auth.py:37-38](../../app/auth.py#L37)); it never reads `auth_users.role`. The role-based scaffolding (`app/security/roles.py`) is not invoked by any of these endpoints. (Stated repo-wide reality: role auth is scaffold-only; `auth_users.role` from migration 045 is not read by `get_current_user`.)
- Endpoints bind the user as `_user`/`_u` and never branch on identity for the Dashboard/SOP-summary; `list_my_queue` uses the email purely as a data filter ([app/api/sessions.py:141](../../app/api/sessions.py#L141); [app/api/sop.py:280](../../app/api/sop.py#L280); [app/api/queue.py:46](../../app/api/queue.py#L46), [:112](../../app/api/queue.py#L112)).
- The router's only admin gate is the client-side `adminOnly` guard on `/admin/help`, comparing `auth.email` against the hardcoded `LEGACY_ADMIN_EMAIL = 'johndean@vin.com'` ([frontend/src/router/index.ts:51](../../frontend/src/router/index.ts#L51), [:63-66](../../frontend/src/router/index.ts#L63)). This does not touch `/dashboard` or `/queue`. The dashboard guard is just `isAuthenticated` ([frontend/src/router/index.ts:59-62](../../frontend/src/router/index.ts#L59)).

## Integrations

None specific to this module. The Dashboard consumes only first-party `/v1/*` endpoints over the shared `http()` client in [frontend/src/services/api.ts](../../frontend/src/services/api.ts). No GCS, STT, Gemini, SMTP, or third-party calls occur in the Dashboard/queue read path. NOT VERIFIED IN CODE: any external integration (none present).

## Background Jobs

- The Dashboard does not enqueue or read any Celery job. The "Jobs Queue" widget is a static "Celery queue is empty." placeholder ([frontend/src/views/DashboardView.vue:337](../../frontend/src/views/DashboardView.vue#L337)).
- The overdue logic surfaced on the Dashboard (`ATTN`) and in `/queue` (`OVERDUE`) is the *same* SLA rule used by the Celery task `sop_check_deadlines_task`, which reads `sop_state` against `_DEFAULT_SLA_HOURS` and per-session overrides ([app/tasks/sop_tasks.py:36-45](../../app/tasks/sop_tasks.py#L36), [:485-499](../../app/tasks/sop_tasks.py#L485)). That task runs on a Beat cadence and emits WS warnings; the Dashboard/queue only *read* the same inputs and re-derive the flag — they do not run the job ([app/api/sop.py:290-293](../../app/api/sop.py#L290)).

## Error Handling

- **Dashboard:** both mount fetches are `.catch(() => [])`, so a failed call degrades to empty rather than throwing; there is no error UI ([frontend/src/views/DashboardView.vue:30-31](../../frontend/src/views/DashboardView.vue#L30)). `loading` is always cleared in a `finally` ([:35-37](../../frontend/src/views/DashboardView.vue#L35)).
- **Queue:** errors set `error.value` and, on foreground loads only, push a toast; background refreshes swallow errors ([frontend/src/views/QueueView.vue:43-51](../../frontend/src/views/QueueView.vue#L43)). The view renders an explicit error branch ([:115](../../frontend/src/views/QueueView.vue#L115)).
- **Backend:** unknown stages are skipped rather than erroring ([app/api/sop.py:306-307](../../app/api/sop.py#L306)); `entered_current_at` null is tolerated (no overdue computed) ([app/api/queue.py:128](../../app/api/queue.py#L128); [app/api/sop.py:312-313](../../app/api/sop.py#L312)).

## Performance Considerations

- **Dashboard aggregates are capped at the default page size of 50.** `sessions.list({})` sends no `limit`; the backend defaults to 50 ([frontend/src/views/DashboardView.vue:30](../../frontend/src/views/DashboardView.vue#L30); [app/api/sessions.py:145](../../app/api/sessions.py#L145)). Counts derived client-side (AI Sessions, Segments, Words, CMS Published, Assignment Coverage) will under-report beyond 50 sessions and can disagree with the unbounded SOP Pipeline 2 counts. Flag for follow-up.
- **`dashboard_summary` scans all `sop_state` rows** (`SELECT … FROM sop_state` with no LIMIT) and aggregates in Python ([app/api/sop.py:295-298](../../app/api/sop.py#L295)) — O(n) over the SOP table per dashboard load. NOT VERIFIED IN CODE: index coverage on `sop_state`.
- **`/queue` polls every 30s** with an `inFlight` de-dupe and `LIMIT 200`, balancing freshness against API load (rationale documented inline) ([frontend/src/views/QueueView.vue:25-30](../../frontend/src/views/QueueView.vue#L25); [app/api/queue.py:109](../../app/api/queue.py#L109)).
- **Sparkline** is cheap and, given empty data, short-circuits to a div with no SVG math ([frontend/src/components/dashboard/Sparkline.vue:13-14](../../frontend/src/components/dashboard/Sparkline.vue#L13)).
- **No client cache:** the Dashboard re-fetches on every mount/navigation back to `/dashboard`; there is no memoization or store-backed cache.

## Source Verification
- **Files Used:** frontend/src/views/DashboardView.vue, frontend/src/views/QueueView.vue, frontend/src/components/dashboard/Sparkline.vue, frontend/src/components/shared/StageBadge.vue, frontend/src/fixtures/sop_stages.ts, frontend/src/router/index.ts, frontend/src/services/api.ts, app/api/queue.py, app/api/sop.py, app/api/sessions.py, app/tasks/sop_tasks.py, app/auth.py, app/main.py
- **Components Used:** DashboardView.vue, QueueView.vue, Sparkline.vue, StageBadge.vue, Icon.vue (imported)
- **APIs Used:** GET /v1/sessions, GET /v1/sop/dashboard-summary, GET /v1/queue/mine
- **Database Tables Used:** sessions, sop_state
- **Permission Logic Used:** JWT presence only via CurrentUser; no role read; client-side authenticated-route guard. LEGACY_ADMIN_EMAIL gate exists only on /admin/help, not this module.
- **Confidence Score:** High — endpoints, fields, SQL, and computed-prop wiring all read directly from source.
- **Evidence Links:** [DashboardView.vue:27-97](../../frontend/src/views/DashboardView.vue#L27), [queue.py:45-143](../../app/api/queue.py#L45), [sop.py:279-325](../../app/api/sop.py#L279), [sessions.py:138-175](../../app/api/sessions.py#L138), [api.ts:137-366](../../frontend/src/services/api.ts#L137), [auth.py:37-208](../../app/auth.py#L37)
