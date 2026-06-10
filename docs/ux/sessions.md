# Sessions List Screen

Route: `#/sessions`. View: [frontend/src/views/SessionsView.vue](../../frontend/src/views/SessionsView.vue).

## Purpose

The master list of continuing-education recordings in the transcription pipeline. Shows KPI tiles (In Workflow / Processing / Published / Total), a search + filter toolbar, and a table of sessions. Each row links to its editor or processing screen; rows can be deleted (soft-delete), and failed rows expose a failure-detail modal. Supports deep-link filtering by SOP stage or AI stage via query params.

## User Types

Any authenticated user. No per-user or per-role view variation is implemented — the same list, filters, and row actions (including delete) are available to every authenticated user.

## Entry Points

- App navigation chrome (header) and the dashboard "View all →" link / pipeline-step clicks land here, sometimes with query params: `?ai=<stageId>`, `?stage=<stageId>`, `?f=<filter>` ([SessionsView.vue:29-31](../../frontend/src/views/SessionsView.vue#L29-L31), and dashboard pipeline pushes).
- Direct navigation to `#/sessions`.

## Navigation Paths

- Row click → `routeFor(s)`: `/p/:id` when `status === 'ingesting'`, else `/s/:id` (session detail) ([SessionsView.vue:98-100](../../frontend/src/views/SessionsView.vue#L98), [:235](../../frontend/src/views/SessionsView.vue#L235)).
- "New upload" button → `/upload` ([SessionsView.vue:157](../../frontend/src/views/SessionsView.vue#L157)).
- Empty-state "upload one" button → `/upload` ([SessionsView.vue:277](../../frontend/src/views/SessionsView.vue#L277)).
- Clear-filter "×" → `router.push('/sessions')` (drops stage/ai params) ([SessionsView.vue:78-82](../../frontend/src/views/SessionsView.vue#L78), [:197](../../frontend/src/views/SessionsView.vue#L197)).
- Failure modal "Open audit log" → `/e/:sessionId/audit` ([SessionsView.vue:343](../../frontend/src/views/SessionsView.vue#L343)).

## Components

- **Icon** ([frontend/src/components/shared/Icon.vue](../../frontend/src/components/shared/Icon.vue)) — `download`, `circle-dot`, `search`, `x`.
- **StageBadge** ([frontend/src/components/shared/StageBadge.vue](../../frontend/src/components/shared/StageBadge.vue)) — rendered per row with a hard-coded `id="prep"` ([SessionsView.vue:258](../../frontend/src/views/SessionsView.vue#L258)); it does not reflect the row's actual SOP stage.
- **`toast`** ([frontend/src/composables/useToast](../../frontend/src/composables/useToast.ts)) and **`confirm`** ([frontend/src/composables/useConfirm](../../frontend/src/composables/useConfirm.ts)) composables for feedback and the delete confirmation dialog.

Template regions:
- Page eyebrow + title + description + actions (Export CSV, New upload) ([SessionsView.vue:144-161](../../frontend/src/views/SessionsView.vue#L144-L161)).
- KPI row, 4 tiles, all computed from `sessions` ([SessionsView.vue:163-180](../../frontend/src/views/SessionsView.vue#L163-L180)).
- Toolbar: search input, filter chips (with an active stage/ai chip), and a sort `<select>` ([SessionsView.vue:182-218](../../frontend/src/views/SessionsView.vue#L182-L218)).
- Sessions table with a head row + body rows + loading/error/empty footer rows ([SessionsView.vue:220-281](../../frontend/src/views/SessionsView.vue#L220-L281)).
- Failure-detail modal (inline, not a shared component) ([SessionsView.vue:283-349](../../frontend/src/views/SessionsView.vue#L283-L349)).

## Actions

- **Search** — `v-model="query"`; `@keyup.enter="load"` refetches with `f: query` ([SessionsView.vue:185](../../frontend/src/views/SessionsView.vue#L185), [:37-41](../../frontend/src/views/SessionsView.vue#L37)). Additionally, `filtered` does an extra client-side substring filter over title/presenter ([SessionsView.vue:66-72](../../frontend/src/views/SessionsView.vue#L66)).
- **Filter chips** (`All`, `In Workflow`, `Processing`, `Published`) — set `activeFilter`, applied client-side in `filtered` ([SessionsView.vue:84-89](../../frontend/src/views/SessionsView.vue#L84), [:200-208](../../frontend/src/views/SessionsView.vue#L200), [:61-65](../../frontend/src/views/SessionsView.vue#L61)).
- **Sort `<select>`** — `v-model="sortBy"` (updated / code / title). `sortBy` is bound but `filtered` does not apply any sort — the value is captured but unused for ordering ([SessionsView.vue:28](../../frontend/src/views/SessionsView.vue#L28), [:212-216](../../frontend/src/views/SessionsView.vue#L212)). `PARTIALLY IMPLEMENTED`.
- **Export CSV** — `exportCsv()` only pushes a success toast "Sessions CSV download started"; no fetch or file is generated ([SessionsView.vue:102-104](../../frontend/src/views/SessionsView.vue#L102)). `PARTIALLY IMPLEMENTED` (UI affordance with no backend call).
- **Delete row** — `deleteRow(s, e)`: opens a danger confirm dialog, then on confirm calls `sessionsApi.remove(s.id)`, removes the row locally, and toasts success/error ([SessionsView.vue:106-123](../../frontend/src/views/SessionsView.vue#L106)).
- **Show failure reason** — clicking the "Failed · why?" pill calls `showFailureReason(s, e)` → `sessionsApi.failureReason(s.id)`, populating the modal ([SessionsView.vue:129-139](../../frontend/src/views/SessionsView.vue#L129)).

## States

- **Loading** — `loading` ref true during `load()` ([SessionsView.vue:24](../../frontend/src/views/SessionsView.vue#L24), [:33-47](../../frontend/src/views/SessionsView.vue#L33)).
- **Error** — `error` string set when `load()` throws ([SessionsView.vue:42-43](../../frontend/src/views/SessionsView.vue#L42)).
- **Loaded with rows** — table body renders `filtered` ([SessionsView.vue:230-271](../../frontend/src/views/SessionsView.vue#L230)).
- **Reactive refetch** — a `watch` on `route.query.stage/ai/f` re-runs `load()` so deep-link changes refetch ([SessionsView.vue:51-59](../../frontend/src/views/SessionsView.vue#L51)).
- **Per-row AI status** — `aiStatusFor` maps status to a chip (Processing/amber, Published/green, Failed/red, else Ready/green) ([SessionsView.vue:91-96](../../frontend/src/views/SessionsView.vue#L91)).
- **Failure modal open/closed** — driven by `failureModal` ref ([SessionsView.vue:126](../../frontend/src/views/SessionsView.vue#L126), [:285](../../frontend/src/views/SessionsView.vue#L285)).

## Empty States

In the table footer, mutually exclusive with loading/error ([SessionsView.vue:274-280](../../frontend/src/views/SessionsView.vue#L274)):
- When `sessions.length === 0` (no sessions at all): "No sessions yet — [upload one]".
- When there are sessions but `filtered.length === 0` (filter excludes all): "No sessions match this filter."

The failure modal has its own empty branch: when no reason/category is recorded, it shows "No specific failure reason recorded — check audit log for the full trail." ([SessionsView.vue:323-325](../../frontend/src/views/SessionsView.vue#L323)).

## Error States

- **List load error** — when not loading and `error` is set, the table footer shows the error string in red: `${e.status}: ${e.message}` for `ApiError`, else the error message ([SessionsView.vue:42-43](../../frontend/src/views/SessionsView.vue#L42), [:273](../../frontend/src/views/SessionsView.vue#L273)).
- **Delete error** — toasted, not inline: "Failed to delete <code>: <msg>" ([SessionsView.vue:119-122](../../frontend/src/views/SessionsView.vue#L119)).
- **Failure-reason fetch error** — toasted "Could not load failure reason" ([SessionsView.vue:134-136](../../frontend/src/views/SessionsView.vue#L134)).

## Loading States

- **List loading** — table footer shows "Loading sessions…" while `loading` is true ([SessionsView.vue:272](../../frontend/src/views/SessionsView.vue#L272)).
- **Failure-reason loading** — `failureLoading` ref is set around `failureReason()` ([SessionsView.vue:127](../../frontend/src/views/SessionsView.vue#L127), [:130-138](../../frontend/src/views/SessionsView.vue#L130)) but it is not surfaced anywhere in the template (no spinner/disabled state bound to it). `PARTIALLY IMPLEMENTED`.

## Permissions

Guarded route — requires `isAuthenticated` ([router/index.ts:58-62](../../frontend/src/router/index.ts#L58)). No role gate on the view. The Delete action, Export CSV, and failure modal are available to every authenticated user — there is no `LEGACY_ADMIN_EMAIL` or role check anywhere in this view. The backend delete route is JWT-gated (`_user: CurrentUser`) with no role enforcement ([app/api/sessions.py:621-622](../../app/api/sessions.py#L621)).

## Connected APIs

- `GET /v1/sessions` via `sessionsApi.list({ stage, ai, f })` — called on mount and on every filter watch ([SessionsView.vue:37-41](../../frontend/src/views/SessionsView.vue#L37), [:49](../../frontend/src/views/SessionsView.vue#L49)). Wrapper: [api.ts:137-138](../../frontend/src/services/api.ts#L137). Backend: [app/api/sessions.py:138](../../app/api/sessions.py#L138).
- `DELETE /v1/sessions/{id}` via `sessionsApi.remove(s.id)` ([SessionsView.vue:116](../../frontend/src/views/SessionsView.vue#L116)). Wrapper: [api.ts:164-165](../../frontend/src/services/api.ts#L164). Backend: [app/api/sessions.py:621](../../app/api/sessions.py#L621).
- `GET /v1/sessions/{id}/failure-reason` via `sessionsApi.failureReason(s.id)` ([SessionsView.vue:133](../../frontend/src/views/SessionsView.vue#L133)). Wrapper: [api.ts:172-173](../../frontend/src/services/api.ts#L172). Backend: [app/api/sessions.py:753](../../app/api/sessions.py#L753).

Export CSV makes no API call (toast only — [SessionsView.vue:102-104](../../frontend/src/views/SessionsView.vue#L102)).

## Data Sources

- **`sessions` ref** ← `sessionsApi.list` ([SessionsView.vue:23](../../frontend/src/views/SessionsView.vue#L23), [:37](../../frontend/src/views/SessionsView.vue#L37)). KPI tiles and filter counts derive from it ([SessionsView.vue:84-89](../../frontend/src/views/SessionsView.vue#L84), [:164-179](../../frontend/src/views/SessionsView.vue#L164)).
- **`filtered` computed** — client-side filtering of `sessions` by `activeFilter` + `query` ([SessionsView.vue:61-74](../../frontend/src/views/SessionsView.vue#L61)).
- **`SOP_STAGE_BY_ID` fixture** ([frontend/src/fixtures/sop_stages](../../frontend/src/fixtures/sop_stages.ts)) — used to label the active stage chip via `stageMeta` ([SessionsView.vue:15](../../frontend/src/views/SessionsView.vue#L15), [:76](../../frontend/src/views/SessionsView.vue#L76)).
- **`failureModal` ref** ← `sessionsApi.failureReason` (`SessionFailureReason` shape: reason, category, ts, actor, log_tail) ([api.ts:114-124](../../frontend/src/services/api.ts#L114)).
- **Route query** (`stage`, `ai`, `f`) — initial filter state and the refetch watch ([SessionsView.vue:29-31](../../frontend/src/views/SessionsView.vue#L29), [:51-59](../../frontend/src/views/SessionsView.vue#L51)).

## Source Verification
- **Files Used:** frontend/src/views/SessionsView.vue, frontend/src/services/api.ts, frontend/src/components/shared/Icon.vue, frontend/src/components/shared/StageBadge.vue, frontend/src/router/index.ts, app/api/sessions.py
- **Components Used:** Icon, StageBadge; composables toast + confirm
- **APIs Used:** GET /v1/sessions, DELETE /v1/sessions/{id}, GET /v1/sessions/{id}/failure-reason
- **Database Tables Used:** none queried directly by the view (backend reads/writes the sessions table)
- **Permission Logic Used:** JWT presence (route guard); no role check on view or wired routes
- **Confidence Score:** High — view fully read; all three API calls trace to verified backend routes; unwired affordances (Export CSV, sort) confirmed in source.
- **Evidence Links:** [SessionsView.vue:33-47](../../frontend/src/views/SessionsView.vue#L33-L47), [SessionsView.vue:102-139](../../frontend/src/views/SessionsView.vue#L102-L139), [SessionsView.vue:272-281](../../frontend/src/views/SessionsView.vue#L272-L281), [app/api/sessions.py:138](../../app/api/sessions.py#L138), [app/api/sessions.py:753](../../app/api/sessions.py#L753)
