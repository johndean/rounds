# Improvements Screen

Route: `#/improvements` — registered in [frontend/src/router/index.ts:39](../../frontend/src/router/index.ts#L39) as the `improvements` route (no `props`, no `meta`). Implemented by [frontend/src/views/ImprovementsView.vue](../../frontend/src/views/ImprovementsView.vue).

## Purpose

A master/detail roadmap board for product enhancements, bug fixes, and operator requests. The left "master" pane is a status-tabbed, searchable table of improvement items; the right "detail" pane is a 5-step Action Plan Builder for the selected item ([frontend/src/components/improvements/ImprovDetail.vue](../../frontend/src/components/improvements/ImprovDetail.vue)). Users can suggest a new improvement and delete existing rows.

## User Types

Any authenticated user. No role gate on this route (not `adminOnly`, no `LEGACY_ADMIN_EMAIL` check). Note: the detail pane contains an "ADMIN CONTROLS" block ([ImprovDetail.vue:274-299](../../frontend/src/components/improvements/ImprovDetail.vue#L274)), but it is rendered unconditionally for everyone and its Save action is not wired (see Actions). So "admin" here is cosmetic, not enforced. NOT VERIFIED IN CODE: any server-side role check for improvements writes.

## Entry Points

- Direct hash navigation to `#/improvements`. NOT VERIFIED IN CODE: the nav-bar/menu link into this route is not declared in this view file.

## Navigation Paths

- This view stays in place; there are no `RouterLink`s out. Selection (`selectedId`) and tab/search are all local state, not route changes.
- The detail pane's close button emits `close`, which clears `selectedId` ([frontend/src/views/ImprovementsView.vue:218](../../frontend/src/views/ImprovementsView.vue#L218)).

## Components

- `<main class="page" data-screen-label="Improvements">` root ([frontend/src/views/ImprovementsView.vue:134](../../frontend/src/views/ImprovementsView.vue#L134)).
- `Icon` shared component ([frontend/src/components/shared/Icon.vue](../../frontend/src/components/shared/Icon.vue)) — `search`, `circle-dot`.
- **Header** — title, a count line ("{N} of {N} · roadmap…"), a search box (`v-model="searchQ"`, `data-test-id="improv-search"`), and a "Suggest Improvement" button (`data-test-id="improv-suggest"`) ([frontend/src/views/ImprovementsView.vue:135-151](../../frontend/src/views/ImprovementsView.vue#L135)).
- **Status tabs** `.improv-tabs` — 8 filter tabs (All, Pending, Under Review, Approved, In Progress, Rolled Out, Declined, Archived) with live counts from `filters` ([frontend/src/views/ImprovementsView.vue:46-55](../../frontend/src/views/ImprovementsView.vue#L46), [153-162](../../frontend/src/views/ImprovementsView.vue#L153)).
- **Master table** `.improv-master` — head row (checkbox + TITLE/STATUS/RISK/PRIORITY/SUBMITTED) and a `.improv-master__list` of `.improv-row2` rows ([frontend/src/views/ImprovementsView.vue:165-215](../../frontend/src/views/ImprovementsView.vue#L165)). Each row shows title + submitter, a status pill, a risk pill, a priority label, a submitted-date, and a "Del" affordance (`data-test-id="improv-del-{id}"`).
- **Detail pane** `<ImprovDetail>` — rendered when `selectedForDetail` is non-null ([frontend/src/views/ImprovementsView.vue:217-219](../../frontend/src/views/ImprovementsView.vue#L217)).
- **`ImprovDetail`** child ([frontend/src/components/improvements/ImprovDetail.vue](../../frontend/src/components/improvements/ImprovDetail.vue)) — 5-step stepper (Overview, Requirements, Implementation, Testing, Review), an AI-model select, generated Requirements/Implementation/Test markdown blocks, a Review accordion, and the ADMIN CONTROLS block.
- **`SuggestImprovementModal`** overlay ([frontend/src/components/overlays/SuggestImprovementModal.vue](../../frontend/src/components/overlays/SuggestImprovementModal.vue)) — title / surface / priority / description form, opened via `modal.open(...)`.

## Actions

- **Search** — `v-model="searchQ"` filters `visibleItems` by title substring (case-insensitive) ([frontend/src/views/ImprovementsView.vue:57-62](../../frontend/src/views/ImprovementsView.vue#L57)).
- **Switch status tab** — sets `statusTab`; `visibleItems` filters by `i.status === statusTab` (except "all") ([frontend/src/views/ImprovementsView.vue:58](../../frontend/src/views/ImprovementsView.vue#L58)).
- **Select a row** — clicking a row sets `selectedId`, driving the detail pane ([frontend/src/views/ImprovementsView.vue:188](../../frontend/src/views/ImprovementsView.vue#L188)).
- **Suggest Improvement** — `suggest()` opens `SuggestImprovementModal`; on submit it calls `improvApi.suggest({ title, description, priority, area })` (`POST /v1/improvements`), prepends the created row, selects it, and toasts "Submitted as {id}…" ([frontend/src/views/ImprovementsView.vue:94-112](../../frontend/src/views/ImprovementsView.vue#L94)). This is a **real, wired write.**
- **Delete a row** — `delRow()` opens a confirm dialog, then calls `improvApi.remove(id)` (`DELETE /v1/improvements/{id}`), removes the row locally, toasts "Improvement deleted" ([frontend/src/views/ImprovementsView.vue:114-130](../../frontend/src/views/ImprovementsView.vue#L114)). Real write. The row checkbox click is stopped from selecting (`@click.stop`).

Inside `ImprovDetail` (PARTIALLY IMPLEMENTED):
- **Regenerate** (steps 1–3) → `regenerate()` only toasts a warn "AI prompt regeneration not yet wired — ships with Phase 8 templates port." No API call ([ImprovDetail.vue:136-141](../../frontend/src/components/improvements/ImprovDetail.vue#L136)).
- **Save Changes** (Review step) → `save()` only toasts a warn "Improvement detail save not yet wired — ships with Phase 8 admin patch endpoints." No API call — `improvementsApi.admin` / `saveStep` exist in api.ts but are **not** invoked from this component ([ImprovDetail.vue:143-148](../../frontend/src/components/improvements/ImprovDetail.vue#L143); unused wrappers at [api.ts:678-681](../../frontend/src/services/api.ts#L678)).
- **Copy / Export (.md)** → clipboard write + Blob download of the generated markdown; toasts on success ([ImprovDetail.vue:108-129](../../frontend/src/components/improvements/ImprovDetail.vue#L108)). The generated Requirements/Implementation/Test docs are **templated client-side from the item fields**, not fetched.

## States

- **Loading** — `loading` true shows "Loading improvements…" inside the master list ([frontend/src/views/ImprovementsView.vue:175](../../frontend/src/views/ImprovementsView.vue#L175)).
- **Error** — `error` set shows the message in red inside the master list ([frontend/src/views/ImprovementsView.vue:176](../../frontend/src/views/ImprovementsView.vue#L176)).
- **Populated** — rows render; first row auto-selected on load if none selected ([frontend/src/views/ImprovementsView.vue:35-37](../../frontend/src/views/ImprovementsView.vue#L35)).
- **Detail step** — `ImprovDetail` tracks its own `step` (0–4), `expandAll`, and per-section `openSections` ([ImprovDetail.vue:14-23](../../frontend/src/components/improvements/ImprovDetail.vue#L14)).
- **Detail data caveat** — the selected item is adapted to the legacy `ImprovementFixture` shape; `surface`/`area` default to "—" and `description` is the literal placeholder "(detail body loads from /v1/improvements/{id} once wired)" ([frontend/src/views/ImprovementsView.vue:67-83](../../frontend/src/views/ImprovementsView.vue#L67)). PARTIALLY IMPLEMENTED: the per-item detail body is not fetched from `GET /v1/improvements/{id}` (the `improvements.get` wrapper exists at [api.ts:674-675](../../frontend/src/services/api.ts#L674) but is not called here).

## Empty States

Both rendered inside `.improv-master__list` when `visibleItems.length === 0` ([frontend/src/views/ImprovementsView.vue:177-183](../../frontend/src/views/ImprovementsView.vue#L177)):
- **No improvements at all** (`items.length === 0`) → "No improvements yet —" followed by an inline "suggest one" button that calls `suggest()`.
- **None match the filter/search** (items exist but filtered out) → "No improvements match this filter."

## Error States

- **List load failure** → caught in `load()`, stored in `error`, rendered as the red message above ([frontend/src/views/ImprovementsView.vue:38-39](../../frontend/src/views/ImprovementsView.vue#L38), [176](../../frontend/src/views/ImprovementsView.vue#L176)).
- **Suggest failure** → caught, toasts the error message ([frontend/src/views/ImprovementsView.vue:107-108](../../frontend/src/views/ImprovementsView.vue#L107)).
- **Delete failure** → caught, toasts the error message ([frontend/src/views/ImprovementsView.vue:127-128](../../frontend/src/views/ImprovementsView.vue#L127)).
- **Clipboard blocked** (in detail copy) → toasts "Clipboard blocked" warn ([ImprovDetail.vue:113](../../frontend/src/components/improvements/ImprovDetail.vue#L113)).

## Loading States

Single `loading` boolean (init true, cleared in `load()`'s `finally`), gating only the master-list region — the header and tabs render immediately ([frontend/src/views/ImprovementsView.vue:23](../../frontend/src/views/ImprovementsView.vue#L23), [30-43](../../frontend/src/views/ImprovementsView.vue#L30)). There is no skeleton; just the centered "Loading improvements…" text.

## Permissions

JWT presence only via the global router guard ([frontend/src/router/index.ts:53-67](../../frontend/src/router/index.ts#L53)). This route is **not** `adminOnly` and has no `LEGACY_ADMIN_EMAIL` gate. The "ADMIN CONTROLS" panel in the detail pane is shown to all authenticated users and its Save is a no-op toast, so there is no effective client-side authorization here. Role-based authorization is scaffold-only and not wired into this screen. NOT VERIFIED IN CODE: server-side authorization on `POST/DELETE /v1/improvements`.

## Connected APIs

- `GET /v1/improvements` via `improvApi.list()` (initial load, `onMounted`) ([frontend/src/services/api.ts:672-673](../../frontend/src/services/api.ts#L672); called at [ImprovementsView.vue:34](../../frontend/src/views/ImprovementsView.vue#L34)). Returns `ImprovementSummary[]` ([api.ts:660](../../frontend/src/services/api.ts#L660)).
- `POST /v1/improvements` via `improvApi.suggest(...)` (Suggest submit) ([frontend/src/services/api.ts:676-677](../../frontend/src/services/api.ts#L676); called at [ImprovementsView.vue:98](../../frontend/src/views/ImprovementsView.vue#L98)).
- `DELETE /v1/improvements/{id}` via `improvApi.remove(id)` (row delete) ([frontend/src/services/api.ts:682-683](../../frontend/src/services/api.ts#L682); called at [ImprovementsView.vue:124](../../frontend/src/views/ImprovementsView.vue#L124)).

Not called from this view despite existing in api.ts: `improvements.get` (per-item detail), `improvements.saveStep` (wizard step PUT), `improvements.admin` (PATCH) ([api.ts:674-681](../../frontend/src/services/api.ts#L674)). The detail/admin save paths are stubbed to warn toasts.

## Data Sources

- **Live**: `items` ref from `improvApi.list()` ([frontend/src/views/ImprovementsView.vue:22](../../frontend/src/views/ImprovementsView.vue#L22), [34](../../frontend/src/views/ImprovementsView.vue#L34)).
- **Derived**: `filters` (tab counts), `visibleItems` (tab+search filtered), `selected`, `selectedForDetail` (shape adapter) ([frontend/src/views/ImprovementsView.vue:46-83](../../frontend/src/views/ImprovementsView.vue#L46)).
- **Detail generated text**: `reqDoc`/`implDoc`/`testDoc` are computed from the selected item's fields (title, area, risk, priority, description) — fully client-side templating, no fetch ([ImprovDetail.vue:43-104](../../frontend/src/components/improvements/ImprovDetail.vue#L43)).
- **Local form state**: `SuggestImprovementModal` holds `title`/`surface`/`priority`/`desc` and emits a `Submission` via `onSubmit` ([SuggestImprovementModal.vue:16-30](../../frontend/src/components/overlays/SuggestImprovementModal.vue#L16)).
- **Type adapter target**: `ImprovementFixture` ([frontend/src/fixtures/improvements.ts:4-16](../../frontend/src/fixtures/improvements.ts#L4)) — the legacy prop shape `ImprovDetail` expects.

## Source Verification
- **Files Used:** frontend/src/views/ImprovementsView.vue, frontend/src/components/improvements/ImprovDetail.vue, frontend/src/components/overlays/SuggestImprovementModal.vue, frontend/src/services/api.ts, frontend/src/fixtures/improvements.ts, frontend/src/router/index.ts, frontend/src/composables/useToast.ts (referenced), frontend/src/composables/useConfirm.ts (referenced), frontend/src/composables/useModal.ts (referenced)
- **Components Used:** Icon (shared), ImprovDetail, SuggestImprovementModal
- **APIs Used:** GET /v1/improvements, POST /v1/improvements, DELETE /v1/improvements/{id} (GET /v1/improvements/{id}, PUT wizard, PATCH admin exist in api.ts but are NOT called by this screen)
- **Database Tables Used:** none directly (frontend view; improvements reached via the listed endpoints)
- **Permission Logic Used:** JWT presence (global router beforeEach); no adminOnly / LEGACY_ADMIN_EMAIL gate; in-pane "ADMIN CONTROLS" is cosmetic (Save is a no-op toast)
- **Confidence Score:** High — every wired call traced to its api.ts wrapper; the unwired Save/Regenerate paths confirmed as warn-only toasts.
- **Evidence Links:** [ImprovementsView.vue:94-130](../../frontend/src/views/ImprovementsView.vue#L94), [ImprovDetail.vue:136-148](../../frontend/src/components/improvements/ImprovDetail.vue#L136), [api.ts:671-684](../../frontend/src/services/api.ts#L671), [router/index.ts:39](../../frontend/src/router/index.ts#L39)
