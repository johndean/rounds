# Queue (`#/queue`)

The per-user work queue. Lists sessions where the current user is the assignee for that session's **current SOP stage**, ordered server-side (longest-waiting first; the client does not re-sort). Implemented entirely in [frontend/src/views/QueueView.vue](../../frontend/src/views/QueueView.vue).

## Purpose

Surface the sessions a user needs to act on right now — those parked at a stage they own. Each row shows the session code, title, current stage, how long it has been in that stage, and an OVERDUE pill when past SLA. Clicking a row opens that session's SOP tab so the user can act on it ([QueueView.vue:90-92](../../frontend/src/views/QueueView.vue#L90)).

## User Types

Any authenticated user. There is no role gating on this screen — the queue is scoped per-user by the backend (`GET /v1/queue/mine`), which returns rows for the calling user only ([QueueView.vue:42](../../frontend/src/views/QueueView.vue#L42)). The header copy reads "Sessions where you're the current-stage assignee" ([QueueView.vue:104-106](../../frontend/src/views/QueueView.vue#L104)).

## Entry Points

- Hash route `#/queue`, registered as the `queue` named route ([frontend/src/router/index.ts:43](../../frontend/src/router/index.ts#L43)).
- Reachable by direct URL. NOT VERIFIED IN CODE: whether a top-nav/sidebar link points here (the view file does not declare its own inbound links; navigation chrome lives elsewhere).

## Navigation Paths

- Outbound: clicking any queue row calls `router.push('/e/<session_id>/sop')`, i.e. the session's SOP tab ([QueueView.vue:91](../../frontend/src/views/QueueView.vue#L91)).
- No other navigation actions exist in this view.

## Components

This view is self-contained — it renders raw markup, no imported child components.

- `main.route[data-test-id="route-queue"]` — page wrapper ([QueueView.vue:100](../../frontend/src/views/QueueView.vue#L100)).
- `header.route__header` — title "My queue", subtitle, and a header-meta cluster ([QueueView.vue:101-112](../../frontend/src/views/QueueView.vue#L101)).
  - `span.chip.chip--ghost[data-test-id="queue-count"]` — item count, singular/plural aware ([QueueView.vue:109](../../frontend/src/views/QueueView.vue#L109)).
  - `span.chip.chip--amber[data-test-id="queue-overdue-count"]` — overdue count, shown only when `overdueCount > 0` ([QueueView.vue:110](../../frontend/src/views/QueueView.vue#L110)).
- `div.queue-list` containing one `button.queue-row` per item ([QueueView.vue:120-148](../../frontend/src/views/QueueView.vue#L120)).
  - Row test id is templated: `queue-row-{{ it.code }}` ([QueueView.vue:127](../../frontend/src/views/QueueView.vue#L127)).
  - Row gets modifier class `queue-row--overdue` when `overdue_hours > 0` ([QueueView.vue:126](../../frontend/src/views/QueueView.vue#L126)).
  - Inner spans: `queue-row__code`, `queue-row__title`, `queue-row__stage`, `queue-row__age` (text "{n} in stage"), and a conditional `queue-row__overdue-pill` with test id `queue-row-{{ it.code }}-overdue` and text "+{{ overdue_hours }}h OVERDUE" ([QueueView.vue:132-143](../../frontend/src/views/QueueView.vue#L132)).
  - `div.queue-row__action` — "Open →" affordance ([QueueView.vue:146](../../frontend/src/views/QueueView.vue#L146)).

## Actions

- **Open a queue item** — click a row → navigate to `/e/<id>/sop` ([QueueView.vue:90-92](../../frontend/src/views/QueueView.vue#L90)).
- **Manual reload** — there is no manual refresh button. The view polls (see Loading States / States below).

## States

- **Loaded list** — `v-else` branch renders `div.queue-list` with rows ([QueueView.vue:120](../../frontend/src/views/QueueView.vue#L120)).
- **Background polling** — on mount the view starts a `setInterval` every `POLL_INTERVAL_MS = 30_000` ms calling `refreshSilently()` (no spinner, no error toast on failure) ([QueueView.vue:30](../../frontend/src/views/QueueView.vue#L30), [QueueView.vue:62-66](../../frontend/src/views/QueueView.vue#L62)).
- **Tab-focus refresh** — a `visibilitychange` listener triggers a silent refresh when the document becomes visible ([QueueView.vue:58-60](../../frontend/src/views/QueueView.vue#L58)).
- **Overlap guard** — an `inFlight` flag drops overlapping loads so interval + visibility events don't race ([QueueView.vue:36-38](../../frontend/src/views/QueueView.vue#L36)).
- **Overdue derivation** — `overdueCount` counts items whose `overdue_hours > 0` ([QueueView.vue:94-96](../../frontend/src/views/QueueView.vue#L94)). Time-in-stage is computed client-side from `entered_current_at`, with a `Math.max(0, …)` guard against client clock skew ([QueueView.vue:77-88](../../frontend/src/views/QueueView.vue#L77)).
- Cleanup: `onBeforeUnmount` clears the interval and removes the visibility listener ([QueueView.vue:68-71](../../frontend/src/views/QueueView.vue#L68)).

## Empty States

Implemented. When `items.length === 0` (and not loading / not errored), the `v-else-if` at [QueueView.vue:116-119](../../frontend/src/views/QueueView.vue#L116) renders `div.route__empty[data-test-id="queue-empty"]` with copy "You have no pending items." and "Sessions assigned to you at their current stage will appear here."

## Error States

Implemented. When `error` is set, the `v-else-if` at [QueueView.vue:115](../../frontend/src/views/QueueView.vue#L115) renders `div.route__error` with the error text. Error message is `e.message` or the fallback string "Failed to load queue" ([QueueView.vue:44](../../frontend/src/views/QueueView.vue#L44)). On a foreground (spinner-showing) load, a `toast.push(error, { tone: 'error' })` also fires; background refreshes suppress the toast ([QueueView.vue:45-47](../../frontend/src/views/QueueView.vue#L47)).

## Loading States

Implemented. Initial mount calls `load()` with the spinner on, rendering `div.route__loading` with text "Loading…" via the `v-if="loading"` branch ([QueueView.vue:114](../../frontend/src/views/QueueView.vue#L114), [QueueView.vue:62-63](../../frontend/src/views/QueueView.vue#L62)). Background refreshes pass `showSpinner: false` so the list does not flicker ([QueueView.vue:54-56](../../frontend/src/views/QueueView.vue#L54)).

## Permissions

JWT presence only. The global router guard requires authentication for any non-public route (`#/queue` has no `public` meta), redirecting unauthenticated users to login ([frontend/src/router/index.ts:53-62](../../frontend/src/router/index.ts#L53)). This screen has NO `adminOnly` meta and NO `johndean@vin.com` gate. Per-user scoping is enforced by the backend on `GET /v1/queue/mine`, not by any client-side role check. Role tiers are not active anywhere in this view.

## Connected APIs

- `GET /v1/queue/mine` via `queue.mine()` ([frontend/src/services/api.ts:362-367](../../frontend/src/services/api.ts#L362)), called from `load()` ([QueueView.vue:42](../../frontend/src/views/QueueView.vue#L42)). Returns `QueueItem[]`.

## Data Sources

`QueueItem` shape consumed by the view ([frontend/src/services/api.ts:350-360](../../frontend/src/services/api.ts#L350)):
`session_id`, `code`, `title`, `title_short`, `title_long`, `status`, `current_stage`, `entered_current_at`, `overdue_hours`.

`displayTitle()` prefers `title_long`, then `title_short`, then `title`, falling back to "(untitled)" ([QueueView.vue:73-75](../../frontend/src/views/QueueView.vue#L73)). The backend table(s) behind `/v1/queue/mine` are not declared in the frontend; not verified from this view.

## Source Verification
- **Files Used:** frontend/src/views/QueueView.vue; frontend/src/router/index.ts; frontend/src/services/api.ts; frontend/src/stores/auth.ts
- **Components Used:** none (self-contained markup)
- **APIs Used:** GET /v1/queue/mine
- **Database Tables Used:** none verifiable from the frontend (backend computes the queue server-side)
- **Permission Logic Used:** JWT presence (global router guard); no role gate on this screen
- **Confidence Score:** High — single self-contained view; every state branch and the one API call are present in the source read in full.
- **Evidence Links:** [QueueView.vue:42](../../frontend/src/views/QueueView.vue#L42), [QueueView.vue:114-119](../../frontend/src/views/QueueView.vue#L114), [api.ts:362](../../frontend/src/services/api.ts#L362)
