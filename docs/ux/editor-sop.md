# Editor — SOP Workflow

Route: `#/e/:id/sop` ([frontend/src/router/index.ts:35](../../frontend/src/router/index.ts#L35)) → [frontend/src/views/SopView.vue](../../frontend/src/views/SopView.vue), `props: true` (`id`).

## Purpose

The per-session workflow board. It shows the current SOP stage, the stage stepper (Prep → Copy Draft → Medical → Copy Final → CMS → Captions → QA → Complete), per-stage acceptance checks, KPIs (current stage, assignee, dwell hours, checks passing, pipeline %), stage owner card, approvals, transition history, and SOP invariants. The operator can resolve checks, advance the session, reassign the stage owner, and add overrides/notes. See [SopView.vue:1-11](../../frontend/src/views/SopView.vue#L1).

## User Types

Any authenticated user. No `adminOnly` meta ([router/index.ts:35](../../frontend/src/router/index.ts#L35)); the view contains no role or admin gate of its own.

## Entry Points

- From the Editor: "Workflow" button and stepper items link to `/e/:id/sop` ([EditorView.vue:1187](../../frontend/src/views/EditorView.vue#L1187), [1241](../../frontend/src/views/EditorView.vue#L1241)).
- From the per-session Audit view "Full audit ledger" sibling links (`/e/:id/sop` is the editor's sibling).
- Direct hash navigation.

## Navigation Paths

- Breadcrumb: `/sessions`, `/s/:id` (session detail) ([SopView.vue:321-324](../../frontend/src/views/SopView.vue#L321)).
- Header buttons: "Back to editor" → `/e/:id`; "Viewer" → `/v/:id` ([SopView.vue:345-346](../../frontend/src/views/SopView.vue#L345)).
- Quick actions card: "Open editor" → `/e/:id`; "Full audit ledger" → `/e/:id/audit` ([SopView.vue:528-529](../../frontend/src/views/SopView.vue#L528)).
- SOP-invariants card links to `/improvements` ([SopView.vue:587](../../frontend/src/views/SopView.vue#L587)).

## Components

- `Icon` (shared) ([SopView.vue:13](../../frontend/src/views/SopView.vue#L13)).
- `StageBadge` (shared) — current-stage KPI and transition rows ([SopView.vue:14](../../frontend/src/views/SopView.vue#L14), [353](../../frontend/src/views/SopView.vue#L353), [551-553](../../frontend/src/views/SopView.vue#L551)).
- Composables: `useToast`, `useConfirm`, `useWsSubscriber` ([SopView.vue:17-19](../../frontend/src/views/SopView.vue#L17)).
- The rest of the screen is native markup (KPIs, stepper buttons, check rows, side cards, transition list) — no further child components.

## Actions

- **Select a stage in the stepper** — sets `selectedStage`; the detail card re-renders for that stage's checks (`viewChecks`) ([SopView.vue:388-416](../../frontend/src/views/SopView.vue#L388), [131-137](../../frontend/src/views/SopView.vue#L131)).
- **Prev / Next stage** in the detail card header — moves `selectedStage` ([SopView.vue:435-440](../../frontend/src/views/SopView.vue#L435)).
- **Resolve a check** — `resolveCheck(label)` slugs the label to a `check_id` and calls `sopApi.resolveCheck(...)`, then reloads ([SopView.vue:224-238](../../frontend/src/views/SopView.vue#L224)). The Resolve button only renders for checks in `fail` state ([SopView.vue:458-463](../../frontend/src/views/SopView.vue#L458)).
- **Advance** — `advance()` opens a confirm dialog, then `sopApi.advance(id, nextStage.id)`, toasts, reloads, and selects the next stage ([SopView.vue:239-255](../../frontend/src/views/SopView.vue#L239)). The Advance button is disabled unless `canAdvance` ([SopView.vue:478](../../frontend/src/views/SopView.vue#L478)).
- **Reassign owner** — `reassign(name)` uses `window.prompt` for an email or `group:NAME`, then `sopApi.assign(...)` ([SopView.vue:256-272](../../frontend/src/views/SopView.vue#L256)).
- **Ping owner** — `ping(name)` only pushes a warn toast: Slack integration is not wired ([SopView.vue:273-279](../../frontend/src/views/SopView.vue#L273)) — IMPLEMENTATION NOT FOUND (no backend call).
- **Override with reason** — `addOverride()` prompts, then `sopApi.annotate(..., { kind: 'override' })` ([SopView.vue:281-293](../../frontend/src/views/SopView.vue#L281)).
- **Add note** — `addNote()` prompts, then `sopApi.annotate(..., { kind: 'note' })` ([SopView.vue:295-306](../../frontend/src/views/SopView.vue#L295)).

## States

- **Stage detail badges:** CURRENT / COMPLETE / PENDING based on `viewIsCurrent`/`viewIsDone`/`viewIsPending` ([SopView.vue:424-432](../../frontend/src/views/SopView.vue#L424)).
- **Advance row:** "Ready to advance" (`is-ready`) vs "Cannot advance" (`is-blocked`) by `canAdvance` ([SopView.vue:469-481](../../frontend/src/views/SopView.vue#L469)).
- **Dwell color:** red when overdue, amber over 48h, else normal ([SopView.vue:366](../../frontend/src/views/SopView.vue#L366)).
- **Overdue badge:** "+Nh OVERDUE" badge (`data-test-id="sop-overdue-badge"`) when `currentOverdueHours > 0`; value is computed client-side from `entered_current_at` + per-stage SLA, and refreshed by the `sop.deadline_warning` WS event ([SopView.vue:185-208](../../frontend/src/views/SopView.vue#L185), [368-369](../../frontend/src/views/SopView.vue#L368)).
- **Check states:** each check renders pass / fail / pending icon + chip ([SopView.vue:444-466](../../frontend/src/views/SopView.vue#L444)).

## Empty States

- **No approvals yet:** "No approvals yet." when `approvers.length === 0` ([SopView.vue:513](../../frontend/src/views/SopView.vue#L513)).
- **No transitions yet:** "No transitions yet — session is still in <current>." when `transitions.length === 0` ([SopView.vue:544-546](../../frontend/src/views/SopView.vue#L544)).
- **Session not found:** title falls back to "Session not found" and meta fields show em-dashes when `session` is null ([SopView.vue:333-341](../../frontend/src/views/SopView.vue#L333)).

## Error States

- All four mutating actions (`resolveCheck`, `advance`, `reassign`, `addOverride`, `addNote`) wrap their API call in try/catch and surface an error toast on failure (`e.message` or a per-action fallback like "Advance failed") ([SopView.vue:235-237](../../frontend/src/views/SopView.vue#L235), [252-254](../../frontend/src/views/SopView.vue#L252), [269-271](../../frontend/src/views/SopView.vue#L269)).
- `load()` swallows fetch errors via `.catch(() => null)` on both calls, so a failed fetch yields the "Session not found" / default-`prep` fallback rather than an error banner ([SopView.vue:46-52](../../frontend/src/views/SopView.vue#L46)). No dedicated error panel — IMPLEMENTATION NOT FOUND for an explicit load-error UI.

## Loading States

- `loading` ref true during `load()`; the entire body is replaced by "Loading SOP state…" ([SopView.vue:328](../../frontend/src/views/SopView.vue#L328)). After load the `<template v-else>` block renders ([SopView.vue:329](../../frontend/src/views/SopView.vue#L329)).

## Permissions

JWT presence only via the global router guard ([router/index.ts:53-67](../../frontend/src/router/index.ts#L53)). No `adminOnly` meta on this route and no email/role gate inside `SopView.vue`. Advance/reassign/override/note are available to any authenticated user; the server is the authoritative check on the underlying SOP endpoints (not asserted from this file).

## Connected APIs

Through `@/services/api` ([SopView.vue:15](../../frontend/src/views/SopView.vue#L15)):
- `sessionsApi.get(id)` → `GET /v1/sessions/{id}` ([api.ts:139-140](../../frontend/src/services/api.ts#L139)).
- `sopApi.state(id)` → `GET /v1/sessions/{id}/sop` ([api.ts:629-632](../../frontend/src/services/api.ts#L629)).
- `sopApi.resolveCheck(id, checkId, label)` → `POST /v1/sessions/{id}/sop/checks/resolve` ([api.ts:640-641](../../frontend/src/services/api.ts#L640)).
- `sopApi.advance(id, toStage)` → `POST /v1/sessions/{id}/sop/advance` ([api.ts:638-639](../../frontend/src/services/api.ts#L638)).
- `sopApi.assign(id, assignee, { stage })` → `POST /v1/sessions/{id}/sop/assign` ([api.ts:643-647](../../frontend/src/services/api.ts#L643)).
- `sopApi.annotate(id, body, { stage, kind })` → `PATCH /v1/sessions/{id}/sop/annotations` (used for both override and note) ([api.ts:648-656](../../frontend/src/services/api.ts#L648)).
- WS: `useWsSubscriber(id, { 'sop.deadline_warning': ... })` updates `overdueByStage` ([SopView.vue:202-208](../../frontend/src/views/SopView.vue#L202)).

## Data Sources

- **Live (backend):** `current_stage`, `assignees` (JSONB), `sla_target_hours`, `entered_current_at`, `is_blocked`, `blockers` from `GET /v1/sessions/{id}/sop`; session meta from `GET /v1/sessions/{id}`.
- **Static / derived (matches React SSOT):**
  - `SOP_STAGES` fixture drives stepper + check labels ([SopView.vue:16](../../frontend/src/views/SopView.vue#L16), [58](../../frontend/src/views/SopView.vue#L58)).
  - `palette` is a decorative fallback (illustrative names/avatars/colors); live assignees from `sopState.assignees` are overlaid onto it via `stageMeta`/`_deriveAssigneeDisplay` ([SopView.vue:64-112](../../frontend/src/views/SopView.vue#L64)).
  - `_DEFAULT_SLA_HOURS` mirrors the backend default SLA per stage ([SopView.vue:34-37](../../frontend/src/views/SopView.vue#L34)).
  - `checkStates` are derived from the stage fixture's `checks` labels and are all `'pending'` with meta "awaiting check infrastructure (Phase 7)"; there is no real per-check status feed ([SopView.vue:114-122](../../frontend/src/views/SopView.vue#L114)) — PARTIALLY IMPLEMENTED. Because all checks are pending, `canAdvance` (requires every check `pass`) is `false` in the current code path ([SopView.vue:139](../../frontend/src/views/SopView.vue#L139)).
  - `transitions` are synthesized client-side from `currentIdx` (backdated timestamps), not read from a transition log ([SopView.vue:142-158](../../frontend/src/views/SopView.vue#L142)) — PARTIALLY IMPLEMENTED.

## Source Verification
- **Files Used:** frontend/src/views/SopView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** Icon (shared), StageBadge (shared)
- **APIs Used:** GET /v1/sessions/{id}, GET /v1/sessions/{id}/sop, POST /v1/sessions/{id}/sop/checks/resolve, POST /v1/sessions/{id}/sop/advance, POST /v1/sessions/{id}/sop/assign, PATCH /v1/sessions/{id}/sop/annotations; WS sop.deadline_warning
- **Database Tables Used:** none read directly by the view; server reads sop_state / sop_checks / audit_events per api.ts comments (not asserted from frontend)
- **Permission Logic Used:** JWT presence only (route guard); no admin/role gate in the view
- **Confidence Score:** High — claims traced to view + api.ts + router; static-vs-live data split documented.
- **Evidence Links:** [SopView.vue:43-56](../../frontend/src/views/SopView.vue#L43), [SopView.vue:224-306](../../frontend/src/views/SopView.vue#L224), [api.ts:628-657](../../frontend/src/services/api.ts#L628)
