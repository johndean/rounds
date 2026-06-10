# Dashboard Screen

Route: `#/dashboard`. View: [frontend/src/views/DashboardView.vue](../../frontend/src/views/DashboardView.vue).

## Purpose

Landing screen after sign-in (the root `/` redirects here — [frontend/src/router/index.ts:28](../../frontend/src/router/index.ts#L28)). It presents a personalized greeting, KPI tiles, a "Your Queue" of the most recent sessions, a two-row pipeline visualization (7-stage AI pipeline + 8-stage SOP pipeline), an operations section (KPIs, SLA-by-stage grid, time-range tabs), and several widget cards.

A key code-reality note: only a subset of this screen is wired to live data. KPI counts, the queue, the AI pipeline counts, and the SOP pipeline counts derive from two live endpoints. The remaining widgets (operations KPIs beyond counts, SLA grid, age alerts, correction hotspots, storage, jobs queue, storage breakdown) render their chrome with hard-coded zero/empty/`—` values — they are not backed by a stats endpoint yet ([DashboardView.vue:61-73](../../frontend/src/views/DashboardView.vue#L61-L73), [:298-362](../../frontend/src/views/DashboardView.vue#L298-L362)). The view's own header comment documents this.

## User Types

Any authenticated user. The greeting derives the first name from `auth.email` ([DashboardView.vue:110-113](../../frontend/src/views/DashboardView.vue#L110-L113)). No role distinction is applied — every authenticated user sees the same dashboard.

## Entry Points

- Default redirect from `/` ([router/index.ts:28](../../frontend/src/router/index.ts#L28)) and the catch-all redirect ([router/index.ts:45](../../frontend/src/router/index.ts#L45)).
- The router guard redirects an `adminOnly` route attempt by a non-admin user here ([router/index.ts:63-66](../../frontend/src/router/index.ts#L63)).
- Reachable from the app chrome/navigation (header) — navigation chrome is outside this view file.

## Navigation Paths

- "New upload" button → `/upload` ([DashboardView.vue:129](../../frontend/src/views/DashboardView.vue#L129)).
- "Your Queue" card click → `/p/:id` if status is `ingesting`, else `/e/:id` (editor) ([DashboardView.vue:157](../../frontend/src/views/DashboardView.vue#L157)).
- Queue empty-state "upload one" button → `/upload` ([DashboardView.vue:175](../../frontend/src/views/DashboardView.vue#L175)).
- "View all →" link → `/sessions` ([DashboardView.vue:150](../../frontend/src/views/DashboardView.vue#L150)).
- AI pipeline step click → `/sessions?ai=<stageId>` ([DashboardView.vue:205](../../frontend/src/views/DashboardView.vue#L205)).
- SOP pipeline step click → `/sessions?stage=<stageId>` ([DashboardView.vue:226](../../frontend/src/views/DashboardView.vue#L226)).
- Widget "All →" anchors → `#/sessions` ([DashboardView.vue:302](../../frontend/src/views/DashboardView.vue#L302), [:312](../../frontend/src/views/DashboardView.vue#L312), [:322](../../frontend/src/views/DashboardView.vue#L322)).

## Components

- **Icon** ([frontend/src/components/shared/Icon.vue](../../frontend/src/components/shared/Icon.vue)) — `circle-dot`, `chevron-right`.
- **StageBadge** ([frontend/src/components/shared/StageBadge.vue](../../frontend/src/components/shared/StageBadge.vue)) — rendered with a hard-coded `id="prep"` on each queue card ([DashboardView.vue:161](../../frontend/src/views/DashboardView.vue#L161)); it does not reflect the session's real SOP stage.
- **Sparkline** ([frontend/src/components/dashboard/Sparkline.vue](../../frontend/src/components/dashboard/Sparkline.vue)) — rendered inside every KPI tile but always passed an empty `spark: []` array ([DashboardView.vue:142](../../frontend/src/views/DashboardView.vue#L142), [:262](../../frontend/src/views/DashboardView.vue#L262)).

Major template regions:
- Header with eyebrow date, greeting, lead line, and "New upload" action ([DashboardView.vue:119-133](../../frontend/src/views/DashboardView.vue#L119-L133)).
- Top KPI grid (`dash-kpis--6`) of 6 tiles ([DashboardView.vue:135-144](../../frontend/src/views/DashboardView.vue#L135-L144)).
- "Your Queue" section, up to 3 cards ([DashboardView.vue:146-178](../../frontend/src/views/DashboardView.vue#L146-L178)).
- "Pipeline" section with type chips and the two pipeline cards ([DashboardView.vue:180-237](../../frontend/src/views/DashboardView.vue#L180-L237)).
- Operations section: ops KPI grid, SLA-by-stage grid, time-range tabs ([DashboardView.vue:239-295](../../frontend/src/views/DashboardView.vue#L239-L295)).
- Two `dash-three` widget rows (age alerts, hotspots, storage; jobs queue, storage breakdown, assignment coverage) ([DashboardView.vue:297-362](../../frontend/src/views/DashboardView.vue#L297-L362)).

## Actions

- **Pipeline type filter chips** (`All types`, `ARAV`, `NAVAS`) — set `pipelineFilter` ([DashboardView.vue:185-191](../../frontend/src/views/DashboardView.vue#L185-L191)). This is local UI state only; it does not re-filter the data shown (the pipeline counts are not recomputed from it). `PARTIALLY IMPLEMENTED`.
- **Time-range tabs** (`7d`, `30d`, `90d`, `All`) — set `timeRange` ([DashboardView.vue:246-251](../../frontend/src/views/DashboardView.vue#L246-L251)). Local UI state only; no data refetch is keyed off it. `PARTIALLY IMPLEMENTED`.
- **New upload / queue navigation / pipeline-step navigation** — see Navigation Paths above; all are `router.push`.

No mutating actions (create/edit/delete) occur on this screen.

## States

- **Loading** — `loading` ref starts `true`, set `false` in the `onMounted` `finally` ([DashboardView.vue:26-38](../../frontend/src/views/DashboardView.vue#L26-L38)). While loading, the lead line shows "Loading sessions…" ([DashboardView.vue:124](../../frontend/src/views/DashboardView.vue#L124)).
- **Loaded** — lead line shows the dual-pipeline summary with counts ([DashboardView.vue:125](../../frontend/src/views/DashboardView.vue#L125)).
- KPI/pipeline values are computed from `allSessions` and `sopSummary` refs ([DashboardView.vue:43-97](../../frontend/src/views/DashboardView.vue#L43-L97)).

## Empty States

- **Your Queue** — when `!loading && queue.length === 0`, shows "No sessions yet — [upload one]" ([DashboardView.vue:173-176](../../frontend/src/views/DashboardView.vue#L173-L176)).
- **SOP Age Alerts / Correction Hotspots / Storage Top Sessions** — each renders a static "No data yet." block unconditionally ([DashboardView.vue:305](../../frontend/src/views/DashboardView.vue#L305), [:315](../../frontend/src/views/DashboardView.vue#L315), [:325](../../frontend/src/views/DashboardView.vue#L325)). These are not data-driven empties — they are always shown. `PARTIALLY IMPLEMENTED`.
- **Jobs Queue** — static "Celery queue is empty." ([DashboardView.vue:337](../../frontend/src/views/DashboardView.vue#L337)). Always shown; not data-driven.
- **Storage Breakdown** — static "No data yet." ([DashboardView.vue:345](../../frontend/src/views/DashboardView.vue#L345)). Always shown.
- **Assignment Coverage** — shows a single "Unassigned / pool" row whose load count is `aiCount` (total session count) ([DashboardView.vue:353-359](../../frontend/src/views/DashboardView.vue#L353-L359)).

## Error States

`IMPLEMENTATION NOT FOUND` — there is no error branch in the template. Both data fetches in `onMounted` use `.catch(() => [])`, so any failure silently degrades to empty arrays; the screen renders with zero counts and no error banner ([DashboardView.vue:29-32](../../frontend/src/views/DashboardView.vue#L29-L32)).

## Loading States

The only loading affordance is the "Loading sessions…" lead-line text driven by `loading` ([DashboardView.vue:124](../../frontend/src/views/DashboardView.vue#L124)). KPI tiles, queue cards, and pipeline cards do not render skeletons during load — they render with their initial empty/zero computed values until data arrives.

## Permissions

Guarded route — requires `isAuthenticated` (JWT present) ([router/index.ts:58-62](../../frontend/src/router/index.ts#L58)). No role gate on this view. Every authenticated user sees the full dashboard; no element is hidden or shown based on `LEGACY_ADMIN_EMAIL` or any role. The auth store is read only for the greeting name ([DashboardView.vue:110-113](../../frontend/src/views/DashboardView.vue#L110-L113)).

## Connected APIs

Both fired once in parallel from `onMounted` ([DashboardView.vue:29-32](../../frontend/src/views/DashboardView.vue#L29-L32)):

- `GET /v1/sessions` via `sessionsApi.list({})` ([frontend/src/services/api.ts:137-138](../../frontend/src/services/api.ts#L137)). Backend: [app/api/sessions.py:138](../../app/api/sessions.py#L138). Drives top KPIs, queue, AI pipeline counts, assignment-coverage count.
- `GET /v1/sop/dashboard-summary` via `sopApi.dashboardSummary()` ([frontend/src/services/api.ts:634-637](../../frontend/src/services/api.ts#L634)). Backend: [app/api/sop.py:279](../../app/api/sop.py#L279). Drives the SOP pipeline per-stage `count` and `overdue_count` (ATTN badge).

No other endpoints are called. The operations KPIs, SLA grid, and the three widget rows have no backing API call in this view.

## Data Sources

- **`sessionsApi.list`** → `allSessions` ref ([DashboardView.vue:23](../../frontend/src/views/DashboardView.vue#L23), [:33](../../frontend/src/views/DashboardView.vue#L33)). Counts derived: `aiCount`, `readyCount`, `processingCount`, `segmentTotal`, `wordTotal` ([DashboardView.vue:43-47](../../frontend/src/views/DashboardView.vue#L43-L47)).
- **`sopApi.dashboardSummary`** → `sopSummary` ref ([DashboardView.vue:24](../../frontend/src/views/DashboardView.vue#L24), [:34](../../frontend/src/views/DashboardView.vue#L34)), matched against `SOP_STAGES` to build the SOP pipeline ([DashboardView.vue:90-97](../../frontend/src/views/DashboardView.vue#L90-L97)).
- **`SOP_STAGES` fixture** ([frontend/src/fixtures/sop_stages](../../frontend/src/fixtures/sop_stages.ts)) — drives the SLA grid rows and SOP pipeline labels ([DashboardView.vue:16](../../frontend/src/views/DashboardView.vue#L16), [:71-73](../../frontend/src/views/DashboardView.vue#L71), [:90](../../frontend/src/views/DashboardView.vue#L90)).
- **Auth store** — `auth.email` for the greeting ([DashboardView.vue:18](../../frontend/src/views/DashboardView.vue#L18), [:110-113](../../frontend/src/views/DashboardView.vue#L110)).
- **Hard-coded literals** — `opsKpis`, `sla` (all `state: 'empty'`, `dAvg: null`), `aiPipeline` non-count fields, type chips, downloads/publishing lists. These are not data-sourced ([DashboardView.vue:61-101](../../frontend/src/views/DashboardView.vue#L61-L101)).

## Source Verification
- **Files Used:** frontend/src/views/DashboardView.vue, frontend/src/services/api.ts, frontend/src/components/shared/Icon.vue, frontend/src/components/shared/StageBadge.vue, frontend/src/stores/auth.ts, frontend/src/router/index.ts, app/api/sessions.py, app/api/sop.py
- **Components Used:** Icon, StageBadge, Sparkline (Sparkline.vue contents not read; referenced as a child)
- **APIs Used:** GET /v1/sessions, GET /v1/sop/dashboard-summary
- **Database Tables Used:** none queried directly by the view (backend endpoints read sessions + sop_state; not touched in frontend code)
- **Permission Logic Used:** JWT presence (route guard); no role check on the view
- **Confidence Score:** High — view fully read; both API calls trace to verified backend routes; non-wired widgets explicitly confirmed as hard-coded in source.
- **Evidence Links:** [DashboardView.vue:27-38](../../frontend/src/views/DashboardView.vue#L27-L38), [DashboardView.vue:61-97](../../frontend/src/views/DashboardView.vue#L61-L97), [api.ts:137](../../frontend/src/services/api.ts#L137), [api.ts:634](../../frontend/src/services/api.ts#L634), [app/api/sop.py:279](../../app/api/sop.py#L279)
