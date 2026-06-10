# Processing Screen

Route: `#/p/:id` — registered in [frontend/src/router/index.ts:38](../../frontend/src/router/index.ts#L38) as the `processing` route (`props: true`). Implemented by [frontend/src/views/ProcessingView.vue](../../frontend/src/views/ProcessingView.vue).

## Purpose

A live "Building your output" status card shown while a session's ingest pipeline runs. It renders a 4–5 step progress list, a progress bar, an elapsed/estimated-remaining readout, and a 3-metric panel (Segments / Markers / Slides). Step set adapts to the detected AI MODE: AI Direct, AI Enhanced, or Standard ([frontend/src/views/ProcessingView.vue:39-70](../../frontend/src/views/ProcessingView.vue#L39)). On a pipeline failure it swaps the card for an error card with Retry / Delete actions. On completion it auto-redirects to the editor.

## User Types

Any authenticated user. No role gate on this route (not `adminOnly`, no `LEGACY_ADMIN_EMAIL` check). Auth presence is enforced by the global router guard ([frontend/src/router/index.ts:59-62](../../frontend/src/router/index.ts#L59)). NOT VERIFIED IN CODE: per-session ownership.

## Entry Points

- Reached after an upload kicks off ingest (the view drives the post-upload waiting experience). NOT VERIFIED IN CODE: the exact navigation from the Upload view to `/p/:id` is not declared in this file.
- Direct hash navigation to `#/p/:id`.
- The Retry action re-enters this same flow in place (calls `connect()` again) ([frontend/src/views/ProcessingView.vue:246-266](../../frontend/src/views/ProcessingView.vue#L246)).

## Navigation Paths

- **Auto-redirect to Editor** — when the WS `processingStage` reaches `'ready'`, a 600ms `setTimeout` pushes `/e/{id}` ([frontend/src/views/ProcessingView.vue:289-293](../../frontend/src/views/ProcessingView.vue#L289)). A second watcher on `session.status` redirects to `/e/{id}` when status transitions to `'ready'` or `'complete'` ([frontend/src/views/ProcessingView.vue:294-298](../../frontend/src/views/ProcessingView.vue#L294)).
- **Delete & start over** — on confirmed delete, pushes `/upload` ([frontend/src/views/ProcessingView.vue:281](../../frontend/src/views/ProcessingView.vue#L281)).

## Components

- `<main class="page proc-page" data-screen-label="Processing">` root with scoped styles defined in the same SFC ([frontend/src/views/ProcessingView.vue:331](../../frontend/src/views/ProcessingView.vue#L331), styles [421-475](../../frontend/src/views/ProcessingView.vue#L421)).
- **Failure card** `.proc-card` with `.proc-h--err` — title, file name, error message, category-specific tip, Retry/Delete buttons, retry-error line ([frontend/src/views/ProcessingView.vue:334-353](../../frontend/src/views/ProcessingView.vue#L334)).
- **Processing card** `.proc-card` — "Building your output" header, file name, optional template badge, step list, progress bar, metrics panel ([frontend/src/views/ProcessingView.vue:356-416](../../frontend/src/views/ProcessingView.vue#L356)).
- **Step list** `.steps` / `.step` — one row per step from the active `STEPS` computed; each shows a check (done), spinner (active), or number (waiting), plus label, hint (or live substage), and an "IIL" tag on IIL steps ([frontend/src/views/ProcessingView.vue:366-387](../../frontend/src/views/ProcessingView.vue#L366)).
- **Progress** `.prog-track` / `.prog-fill` + `.prog-meta` (percent, elapsed, est-remaining) ([frontend/src/views/ProcessingView.vue:390-397](../../frontend/src/views/ProcessingView.vue#L390)).
- **Metrics panel** `.metrics-panel` — Segments / Markers / Slides (aligned/total) ([frontend/src/views/ProcessingView.vue:400-415](../../frontend/src/views/ProcessingView.vue#L400)).

No imported child component files. WS plumbing comes from composables, not components: `useSyncController` and `useWsSubscriber`.

## Actions

- **Retry** → `onRetry()` calls `sessionsApi.retry(id)`, resets failure/stage refs, restarts the elapsed clock, re-`connect()`s the WS, re-fetches the session, toasts "Reingest queued" ([frontend/src/views/ProcessingView.vue:246-266](../../frontend/src/views/ProcessingView.vue#L246)). Disabled while `retrying`. Note: `sessionsApi.retry` POSTs to `/v1/diag/reingest/{id}` ([frontend/src/services/api.ts:178-182](../../frontend/src/services/api.ts#L178)).
- **Delete & start over** → `onDelete()` opens a confirm dialog, then calls `sessionsApi.remove(id)` (`DELETE /v1/sessions/{id}`), toasts "Session deleted", routes to `/upload` ([frontend/src/views/ProcessingView.vue:268-286](../../frontend/src/views/ProcessingView.vue#L268)). Disabled while `deleting`.
- Confirm dialog via the `confirm` composable ([frontend/src/composables/useConfirm.ts](../../frontend/src/composables/useConfirm.ts)); toasts via `toast` ([frontend/src/composables/useToast.ts](../../frontend/src/composables/useToast.ts)).

## States

The top-level template branches on `sessionStatus` ([frontend/src/views/ProcessingView.vue:194-197](../../frontend/src/views/ProcessingView.vue#L194)):

- **Failed** (`sessionStatus === 'failed'`, i.e. a failure category is set or stage is `'failed'`) → failure card. Title is mapped from `failureCategory` via `FAIL_TITLES` (gemini_overloaded, gemini_quota, gemini_config, gemini_error, gemini_context_overflow, storage_error, stt_error, unknown) ([frontend/src/views/ProcessingView.vue:199-209](../../frontend/src/views/ProcessingView.vue#L199)). Two categories get extra tips: `gemini_overloaded` and `gemini_context_overflow` ([frontend/src/views/ProcessingView.vue:338-343](../../frontend/src/views/ProcessingView.vue#L338)).
- **Processing** (default `v-else`) → step card. The active step is computed from WS `processingStage`/`processingProgress` mapped through the pipeline-specific `STAGE_TO_STEP` map, falling back to `session.status` ([frontend/src/views/ProcessingView.vue:142-167](../../frontend/src/views/ProcessingView.vue#L142)).
- **Pipeline variant** — `STEPS`/`STAGE_TO_STEP` switch among `AI_DIRECT_STEPS`, `AI_ENHANCED_STEPS`, `STANDARD_STEPS` based on `isAiMode` + `aiPipeline` from the pipeline-config fetch ([frontend/src/views/ProcessingView.vue:136-146](../../frontend/src/views/ProcessingView.vue#L136)).
- **Step sub-states** — each step row is `s-done` / `s-active` / `s-iil` / `s-wait`, with matching icon class ([frontend/src/views/ProcessingView.vue:371-379](../../frontend/src/views/ProcessingView.vue#L371)).
- **Toasts from WS subscribers** — `polls_autoplaced`, `align_gate_failed`, `gemini_loop_truncated` push info/warn toasts; `slide_progress` overwrites the active step's substage; `template_autodetect` pre-fills the template badge ([frontend/src/views/ProcessingView.vue:95-133](../../frontend/src/views/ProcessingView.vue#L95)).

## Empty States

- **No template detected** — the template badge (`.tmpl-proc-badge`) only renders when `templateId` is truthy ([frontend/src/views/ProcessingView.vue:361-363](../../frontend/src/views/ProcessingView.vue#L361)); otherwise absent.
- **No metrics yet** — each metric value renders `'—'` when its WS-fed value is `undefined` (`metrics.segments ?? '—'`, etc.), and the `/total` suffix on Slides only appears when `slides_total` is defined ([frontend/src/views/ProcessingView.vue:403-413](../../frontend/src/views/ProcessingView.vue#L403)). This is the empty-data representation; there is no separate "no data" panel.

## Error States

- **Pipeline failure** is a first-class state (the failure card described under States). The user message comes from the WS `session_failed` event (`failureUserMessage`), defaulting to "Something went wrong. Try again." ([frontend/src/views/ProcessingView.vue:337](../../frontend/src/views/ProcessingView.vue#L337)).
- **Failure-reason hydration** — if `session.status` becomes `'failed'` but no WS message was captured, `hydrateFailureReason()` fetches `GET /v1/sessions/{id}/failure-reason` to backfill the reason/category ([frontend/src/views/ProcessingView.vue:300-311](../../frontend/src/views/ProcessingView.vue#L300)).
- **Retry/Delete action errors** — caught and shown inline in `.proc-retry-error` (`retryError`), formatted as `{status} — {message}` for `ApiError` ([frontend/src/views/ProcessingView.vue:262](../../frontend/src/views/ProcessingView.vue#L262), [283](../../frontend/src/views/ProcessingView.vue#L283), [352](../../frontend/src/views/ProcessingView.vue#L352)).
- **Session fetch failure** during polling is swallowed silently (`catch { /* keep polling */ }`) so the poll loop continues ([frontend/src/views/ProcessingView.vue:215-222](../../frontend/src/views/ProcessingView.vue#L215)).
- **Pipeline-config fetch failure** falls back to the Standard pipeline display (`catch { /* fall back to standard pipeline display */ }`) ([frontend/src/views/ProcessingView.vue:240-242](../../frontend/src/views/ProcessingView.vue#L240)).

## Loading States

There is no full-page "loading" gate; the processing card *is* the loading-equivalent UI. Progress and step state populate as WS events and the 3-second polling fallback arrive:

- `onMounted` sets the start time, does an initial `fetchSession()`, loads pipeline config, calls `connect()` (WS), and starts two intervals: `fetchSession` every 3000ms and `updateElapsed` every 1000ms ([frontend/src/views/ProcessingView.vue:314-321](../../frontend/src/views/ProcessingView.vue#L314)).
- Estimated remaining shows "Estimating…" early, then "< 1 min" / "~M:SS remaining" / "Finishing up…" derived from elapsed vs percent ([frontend/src/views/ProcessingView.vue:178-192](../../frontend/src/views/ProcessingView.vue#L178)).
- Intervals + WS are torn down in `onUnmounted` (`clearInterval` x2, `disconnect()`) ([frontend/src/views/ProcessingView.vue:323-327](../../frontend/src/views/ProcessingView.vue#L323)).

## Permissions

JWT presence only via the global router guard ([frontend/src/router/index.ts:53-67](../../frontend/src/router/index.ts#L53)). Not `adminOnly`; no email gate. Role-based authorization is scaffold-only and not applied here. NOT VERIFIED IN CODE: per-session access control.

## Connected APIs

- `GET /v1/sessions/{id}` via `sessionsApi.get` — initial fetch + 3s poll ([frontend/src/services/api.ts:139-140](../../frontend/src/services/api.ts#L139); called at [ProcessingView.vue:217](../../frontend/src/views/ProcessingView.vue#L217)).
- `GET /v1/sessions/{id}/pipeline-config` via `sessionsApi.pipelineConfig` ([frontend/src/services/api.ts:174-177](../../frontend/src/services/api.ts#L174); called at [ProcessingView.vue:234](../../frontend/src/views/ProcessingView.vue#L234)).
- `POST /v1/diag/reingest/{id}` via `sessionsApi.retry` (the Retry button) ([frontend/src/services/api.ts:178-182](../../frontend/src/services/api.ts#L178); called at [ProcessingView.vue:251](../../frontend/src/views/ProcessingView.vue#L251)).
- `DELETE /v1/sessions/{id}` via `sessionsApi.remove` (the Delete button) ([frontend/src/services/api.ts:164-165](../../frontend/src/services/api.ts#L164); called at [ProcessingView.vue:279](../../frontend/src/views/ProcessingView.vue#L279)).
- `GET /v1/sessions/{id}/failure-reason` via `sessionsApi.failureReason` (on-demand failure hydration) ([frontend/src/services/api.ts:172-173](../../frontend/src/services/api.ts#L172); called at [ProcessingView.vue:303](../../frontend/src/views/ProcessingView.vue#L303)).
- **WebSocket** `/v1/ws/sessions/{id}` (per the view's header comment, [ProcessingView.vue:6](../../frontend/src/views/ProcessingView.vue#L6)) via the connection pool, consumed through `useSyncController` ([frontend/src/composables/useSyncController.ts](../../frontend/src/composables/useSyncController.ts)) and `useWsSubscriber` ([frontend/src/composables/useWsSubscriber.ts](../../frontend/src/composables/useWsSubscriber.ts)).

## Data Sources

- **WS-driven refs** from `useSyncController(id)`: `processingStage`, `processingProgress`, `processingSubstage`, `metrics` (segments/markers/slides_total/slides_aligned/...), `failureCategory`, `failureUserMessage` ([frontend/src/composables/useSyncController.ts:27-114](../../frontend/src/composables/useSyncController.ts#L27)). Dispatched from `processing_update`, `metrics_update`, `session_failed` WS messages ([frontend/src/composables/useSyncController.ts:40-83](../../frontend/src/composables/useSyncController.ts#L40)).
- **Additional WS events** via `useWsSubscriber`: `slide_progress`, `template_autodetect`, `polls_autoplaced`, `align_gate_failed`, `gemini_loop_truncated` ([frontend/src/views/ProcessingView.vue:95-133](../../frontend/src/views/ProcessingView.vue#L95)).
- **REST refs**: `session` (from `sessions.get`), `templateId`/`aiPipeline`/`isAiMode` (from `pipelineConfig`) ([frontend/src/views/ProcessingView.vue:232-243](../../frontend/src/views/ProcessingView.vue#L232)).
- **Static**: the three step-set arrays and three stage→step maps are hardcoded literals ([frontend/src/views/ProcessingView.vue:39-70](../../frontend/src/views/ProcessingView.vue#L39)); `FAIL_TITLES` map ([199-208](../../frontend/src/views/ProcessingView.vue#L199)).
- **Local timers**: `startTime`, `now`, `elapsedDisplay` for the elapsed clock ([frontend/src/views/ProcessingView.vue:78-83](../../frontend/src/views/ProcessingView.vue#L78), [224-230](../../frontend/src/views/ProcessingView.vue#L224)).

## Source Verification
- **Files Used:** frontend/src/views/ProcessingView.vue, frontend/src/services/api.ts, frontend/src/composables/useSyncController.ts, frontend/src/composables/useWsSubscriber.ts, frontend/src/router/index.ts, frontend/src/composables/useToast.ts (referenced), frontend/src/composables/useConfirm.ts (referenced)
- **Components Used:** none (no imported child components; WS plumbing via composables)
- **APIs Used:** GET /v1/sessions/{id}, GET /v1/sessions/{id}/pipeline-config, POST /v1/diag/reingest/{id}, DELETE /v1/sessions/{id}, GET /v1/sessions/{id}/failure-reason, WS /v1/ws/sessions/{id}
- **Database Tables Used:** none directly (frontend view; reached via the listed endpoints)
- **Permission Logic Used:** JWT presence (global router beforeEach); no adminOnly / LEGACY_ADMIN_EMAIL gate on this route
- **Confidence Score:** High — endpoints traced to api.ts wrappers; WS event shape traced to useSyncController/useWsSubscriber. The WS path string is taken from the view's header comment, not re-verified against the backend route file.
- **Evidence Links:** [ProcessingView.vue:246-298](../../frontend/src/views/ProcessingView.vue#L246), [useSyncController.ts:40-83](../../frontend/src/composables/useSyncController.ts#L40), [api.ts:178-182](../../frontend/src/services/api.ts#L178), [router/index.ts:38](../../frontend/src/router/index.ts#L38)
