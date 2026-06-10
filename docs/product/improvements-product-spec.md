# Improvements — Product Spec

> Module key: `improvements`. Route: `#/improvements` → [`frontend/src/views/ImprovementsView.vue`](../../frontend/src/views/ImprovementsView.vue). Backend: [`app/api/improvements.py`](../../app/api/improvements.py). Table: [`migrations/005_improvements.sql`](../../migrations/005_improvements.sql).

## Overview

Improvements is a master/detail tracker for product enhancement requests, bug reports, and operator suggestions about the Rounds transcript application. Each record carries a title, free-text description, a type/area tag, a priority, a risk classification, a workflow status, and four optional markdown "wizard" payloads (requirements / implementation / testing / review). The list is a single shared backlog — there is one `improvements` table with no per-tenant, per-project, or per-site scoping ([migrations/005_improvements.sql:3-24](../../migrations/005_improvements.sql#L3)).

The page header literally describes the feature as a "roadmap for product enhancements, bug fixes, and operator requests" ([frontend/src/views/ImprovementsView.vue:138-140](../../frontend/src/views/ImprovementsView.vue#L138)).

## Purpose

Capture and triage change requests for the Rounds app in one place:

- **Capture** — any authenticated user can file a suggestion through the "Suggest Improvement" modal ([SuggestImprovementModal.vue](../../frontend/src/components/overlays/SuggestImprovementModal.vue), wired to `POST /v1/improvements`).
- **Triage** — records carry `status`, `priority`, and `risk` fields and can be filtered by status tab ([ImprovementsView.vue:46-62](../../frontend/src/views/ImprovementsView.vue#L46)).
- **Plan** — a five-step "Action Plan Builder" detail pane displays generated requirements / implementation / testing / review documents and an admin-controls form ([ImprovDetail.vue](../../frontend/src/components/improvements/ImprovDetail.vue)).

## User Value

- A single backlog of app change requests with submitter attribution (`submitted_by` is set to the caller's JWT email on create — [app/api/improvements.py:103](../../app/api/improvements.py#L103)).
- Status, priority, and risk at a glance in the master list ([ImprovementsView.vue:164-215](../../frontend/src/views/ImprovementsView.vue#L164)).
- Client-side title search and status-tab filtering of the loaded list ([ImprovementsView.vue:57-62](../../frontend/src/views/ImprovementsView.vue#L57)).
- A structured 5-step action-plan view that can copy/export generated planning documents as markdown ([ImprovDetail.vue:108-129](../../frontend/src/components/improvements/ImprovDetail.vue#L108)).

## Navigation

- **Route:** hash route `#/improvements`, registered as the `improvements` route in [frontend/src/router/index.ts:39](../../frontend/src/router/index.ts#L39). No `meta.adminOnly` and no `meta.public` flag — it is gated only by the global authenticated-user guard ([router/index.ts:53-67](../../frontend/src/router/index.ts#L53)).
- **Within the page:**
  - Status filter tabs: All / Pending / Under Review / Approved / In Progress / Rolled Out / Declined / Archived ([ImprovementsView.vue:46-55](../../frontend/src/views/ImprovementsView.vue#L46)).
  - Master list rows; clicking a row selects it and loads the detail pane ([ImprovementsView.vue:184-189](../../frontend/src/views/ImprovementsView.vue#L184)).
  - Detail pane stepper: Overview → Requirements → Implementation → Testing → Review ([ImprovDetail.vue:25-31](../../frontend/src/components/improvements/ImprovDetail.vue#L25)).

## Screens

### 1. Improvements list (master/detail)

[`ImprovementsView.vue`](../../frontend/src/views/ImprovementsView.vue). Layout:

- Header: title "Improvements", a description line showing `{count} of {count} · roadmap…`, a search box (`data-test-id="improv-search"`), and a "Suggest Improvement" button (`data-test-id="improv-suggest"`) ([ImprovementsView.vue:133-151](../../frontend/src/views/ImprovementsView.vue#L133)).
- Status tabs with per-status counts computed from the loaded list ([ImprovementsView.vue:153-162](../../frontend/src/views/ImprovementsView.vue#L153)).
- Master table columns: checkbox, TITLE, STATUS, RISK, PRIORITY, SUBMITTED ([ImprovementsView.vue:166-173](../../frontend/src/views/ImprovementsView.vue#L166)). Each row also shows the submitter email under the title and a "Del" action (`data-test-id="improv-del-{id}"`) ([ImprovementsView.vue:191-212](../../frontend/src/views/ImprovementsView.vue#L191)).
- Loading, error, empty-filter, and empty-list states are all rendered inline ([ImprovementsView.vue:175-183](../../frontend/src/views/ImprovementsView.vue#L175)).
- Detail pane shows `ImprovDetail` for the selected row ([ImprovementsView.vue:217-219](../../frontend/src/views/ImprovementsView.vue#L217)).

### 2. Suggest Improvement modal

[`SuggestImprovementModal.vue`](../../frontend/src/components/overlays/SuggestImprovementModal.vue). Fields: Title (text), Surface (select from a fixed list of UI surfaces), Priority (Low/Medium/High/Critical), Description (textarea) ([SuggestImprovementModal.vue:36-74](../../frontend/src/components/overlays/SuggestImprovementModal.vue#L36)). On submit it requires a title, then invokes the `onSubmit` callback ([SuggestImprovementModal.vue:21-30](../../frontend/src/components/overlays/SuggestImprovementModal.vue#L21)).

The view's `suggest()` handler maps the modal's `surface` field to the API's `area` parameter and calls `improvApi.suggest(...)` ([ImprovementsView.vue:94-112](../../frontend/src/views/ImprovementsView.vue#L94)).

### 3. Action Plan Builder (detail pane)

[`ImprovDetail.vue`](../../frontend/src/components/improvements/ImprovDetail.vue). A 5-step stepper:

- **Step 0 — Overview:** Submitted by, Area, Created, Current Status, Type, Priority, Impact Scope (hardcoded "Single Page"), Affected Roles (hardcoded "—"), and Description ([ImprovDetail.vue:199-220](../../frontend/src/components/improvements/ImprovDetail.vue#L199)).
- **Steps 1–3 — Requirements / Implementation / Testing:** Each renders a generated markdown document in a `<pre>` block with a "Regenerate" button ([ImprovDetail.vue:222-243](../../frontend/src/components/improvements/ImprovDetail.vue#L222)). The documents are generated **client-side** from the item's fields via `reqDoc`/`implDoc`/`testDoc` computeds ([ImprovDetail.vue:43-104](../../frontend/src/components/improvements/ImprovDetail.vue#L43)) — they are not loaded from the backend wizard columns.
- **Step 4 — Review:** Accordion of the three generated sections with copy/expand controls, plus an "ADMIN CONTROLS" form (Status, Risk Level, Target Version, Admin Notes) ([ImprovDetail.vue:245-300](../../frontend/src/components/improvements/ImprovDetail.vue#L245)).
- An "AI Model" selector (Gemini 2.5 Pro / Flash, GPT-5, Claude Opus 4.5) sits above the body ([ImprovDetail.vue:186-195](../../frontend/src/components/improvements/ImprovDetail.vue#L186)). This is a local `ref` only; it is never sent anywhere — PARTIALLY IMPLEMENTED (UI control with no backing behavior).

## User Flows

### Suggest an improvement

1. User clicks "Suggest Improvement" ([ImprovementsView.vue:147](../../frontend/src/views/ImprovementsView.vue#L147)).
2. Modal opens; user fills Title (required), Surface, Priority, Description.
3. On submit, the view calls `improvApi.suggest({ title, description, priority, area: surface })` → `POST /v1/improvements` ([ImprovementsView.vue:98-103](../../frontend/src/views/ImprovementsView.vue#L98)).
4. Backend inserts a row (status defaults to `pending`, risk to `low`) and writes an `improvement.suggest` audit event ([app/api/improvements.py:96-110](../../app/api/improvements.py#L96)).
5. The created summary is prepended to the list, selected, and a success toast shows the new id prefix ([ImprovementsView.vue:104-106](../../frontend/src/views/ImprovementsView.vue#L104)).

### Browse / filter / search

1. On mount, `load()` calls `improvApi.list()` → `GET /v1/improvements` ([ImprovementsView.vue:30-44](../../frontend/src/views/ImprovementsView.vue#L30)).
2. The first item is auto-selected if none is selected ([ImprovementsView.vue:35-37](../../frontend/src/views/ImprovementsView.vue#L35)).
3. Status tabs filter the in-memory list; the search box filters by title substring ([ImprovementsView.vue:57-62](../../frontend/src/views/ImprovementsView.vue#L57)).

> **Note:** The view's `load()` calls `improvApi.list()` with **no** `statusFilter` argument, so the backend always returns all non-deleted rows; filtering is purely client-side ([ImprovementsView.vue:34](../../frontend/src/views/ImprovementsView.vue#L34)). The backend `status_filter` query param exists but is unused by this view ([app/api/improvements.py:77-89](../../app/api/improvements.py#L77)).

### Delete an improvement

1. User clicks "Del" on a row ([ImprovementsView.vue:208-212](../../frontend/src/views/ImprovementsView.vue#L208)).
2. A confirm dialog opens ([ImprovementsView.vue:116-121](../../frontend/src/views/ImprovementsView.vue#L116)).
3. On confirm, `improvApi.remove(id)` → `DELETE /v1/improvements/{id}` ([ImprovementsView.vue:124](../../frontend/src/views/ImprovementsView.vue#L124)).
4. Backend performs a soft delete (`deleted_at = now()`) and writes an `improvement.delete` audit event ([app/api/improvements.py:180-188](../../app/api/improvements.py#L180)).
5. The row is removed from the in-memory list ([ImprovementsView.vue:125](../../frontend/src/views/ImprovementsView.vue#L125)).

### Action Plan Builder save / regenerate — NOT WIRED

The detail pane's "Save Changes" and "Regenerate" buttons do **not** call the backend. Both call honest warning toasts:

- `save()` → toast "Improvement detail save not yet wired — ships with Phase 8 admin patch endpoints." ([ImprovDetail.vue:143-148](../../frontend/src/components/improvements/ImprovDetail.vue#L143)).
- `regenerate()` → toast "AI prompt regeneration not yet wired — ships with Phase 8 templates port." ([ImprovDetail.vue:136-141](../../frontend/src/components/improvements/ImprovDetail.vue#L136)).

The backend wizard-step (`PUT /v1/improvements/{id}/wizard/{step}`) and admin-patch (`PATCH /v1/improvements/{id}`) endpoints exist and are exposed in the API client (`improvApi.saveStep`, `improvApi.admin` — [frontend/src/services/api.ts:678-681](../../frontend/src/services/api.ts#L678)), but **no component currently calls them**. PARTIALLY IMPLEMENTED.

## Business Rules

- **Soft delete only.** Delete sets `deleted_at`; every read filters `deleted_at IS NULL` ([app/api/improvements.py:81-88](../../app/api/improvements.py#L81), [:117](../../app/api/improvements.py#L117), [:151](../../app/api/improvements.py#L151), [:171](../../app/api/improvements.py#L171)). Note the DELETE handler does **not** add a `deleted_at IS NULL` guard, so deleting an already-deleted id re-stamps `deleted_at` ([app/api/improvements.py:181-183](../../app/api/improvements.py#L181)).
- **Defaults on create.** New rows default `status='pending'`, `priority='medium'`, `risk='low'`, `is_security=FALSE` ([migrations/005_improvements.sql:8-13](../../migrations/005_improvements.sql#L8)). The create endpoint only accepts title/description/type/priority/area/is_security; `risk`, `status`, `target_version`, and the wizard columns are not settable at creation ([app/api/improvements.py:43-49](../../app/api/improvements.py#L43)).
- **Submitter attribution is server-set.** `submitted_by` is forced to the JWT user's email, not taken from the payload ([app/api/improvements.py:103](../../app/api/improvements.py#L103)).
- **Ordering.** Lists are ordered `submitted_at DESC` ([app/api/improvements.py:82](../../app/api/improvements.py#L82), [:88](../../app/api/improvements.py#L88)).
- **Risk vs. priority are distinct fields.** `priority` (low/medium/high/critical) is user-supplied; `risk` (low/medium/high) is server-defaulted and only changeable via the admin PATCH endpoint ([migrations/005_improvements.sql:9-10](../../migrations/005_improvements.sql#L9)).

## Validation Rules

- **Title:** required, length 3–512 on the create payload ([app/api/improvements.py:44](../../app/api/improvements.py#L44)). The modal also blocks submit if title is empty, with a "Title required" warning toast ([SuggestImprovementModal.vue:22-25](../../frontend/src/components/overlays/SuggestImprovementModal.vue#L22)).
- **Wizard step name:** must be one of `requirements`, `implementation`, `testing`, `review`; any other value returns `400 Unknown wizard step` ([app/api/improvements.py:136-148](../../app/api/improvements.py#L136)).
- **Admin patch:** if no non-null fields are supplied, returns `400 No fields to update` ([app/api/improvements.py:165-167](../../app/api/improvements.py#L165)). Accepted fields are `status`, `risk`, `target_version`, `admin_notes` ([app/api/improvements.py:56-60](../../app/api/improvements.py#L56)).
- **No server-side enum enforcement.** The DB columns are plain `TEXT` with comment-only enumerations; nothing in code validates that `status`/`priority`/`risk`/`type` are within the documented set ([migrations/005_improvements.sql:7-11](../../migrations/005_improvements.sql#L7)). NOT VERIFIED IN CODE that out-of-range values are rejected — they are not.

## States

### Record status values (DB comment, [migrations/005_improvements.sql:8](../../migrations/005_improvements.sql#L8))

`pending` | `under_review` | `approved` | `in_progress` | `rolled_out` | `declined` | `archived`. Default `pending`.

> **Discrepancy (verified):** The frontend status tabs and filter logic use **hyphenated** ids — `under-review`, `in-progress`, `rolled-out` ([ImprovementsView.vue:49-54](../../frontend/src/views/ImprovementsView.vue#L49)) — while the database stores **underscored** values per the migration comment. The pill rendering only special-cases `pending` and `rolled-out` (hyphen) ([ImprovementsView.vue:196-198](../../frontend/src/views/ImprovementsView.vue#L196)). Because backend rows carry underscored statuses, the hyphenated tabs for those three states will not match and their counts will read 0. There is no code path that normalizes between the two forms.

### Priority values

`low` | `medium` | `high` | `critical`, default `medium` ([migrations/005_improvements.sql:9](../../migrations/005_improvements.sql#L9)). The modal sends short forms (`low`/`med`/`high`/`crit`) ([SuggestImprovementModal.vue:18](../../frontend/src/components/overlays/SuggestImprovementModal.vue#L18)); the view passes the priority straight through to the API ([ImprovementsView.vue:101](../../frontend/src/views/ImprovementsView.vue#L101)), so `med`/`crit` short forms are stored verbatim. `priorityLabel()` maps both long and short forms for display ([ImprovementsView.vue:85-87](../../frontend/src/views/ImprovementsView.vue#L85)).

### Risk values

`low` | `medium` | `high`, default `low` ([migrations/005_improvements.sql:10](../../migrations/005_improvements.sql#L10)). Row pills also render a `critical` case defensively ([ImprovementsView.vue:201](../../frontend/src/views/ImprovementsView.vue#L201)) even though the migration comment lists only three risk levels.

### UI page states

Loading, error, empty-list ("No improvements yet — suggest one"), and empty-filter ("No improvements match this filter") ([ImprovementsView.vue:175-183](../../frontend/src/views/ImprovementsView.vue#L175)).

## Dependencies

- **Auth:** `CurrentUser` dependency (JWT bearer) on every endpoint ([app/api/improvements.py:14](../../app/api/improvements.py#L14), used at [:77](../../app/api/improvements.py#L77), [:94](../../app/api/improvements.py#L94), [:115](../../app/api/improvements.py#L115), [:145](../../app/api/improvements.py#L145), [:164](../../app/api/improvements.py#L164), [:180](../../app/api/improvements.py#L180)).
- **Database:** `improvements` table ([migrations/005_improvements.sql](../../migrations/005_improvements.sql)) and `audit_events` table ([migrations/004_audit.sql](../../migrations/004_audit.sql)).
- **Frontend composables:** `useToast`, `useConfirm`, `useModal` ([ImprovementsView.vue:17-19](../../frontend/src/views/ImprovementsView.vue#L17)).
- **API client:** `improvements` service object ([frontend/src/services/api.ts:671-684](../../frontend/src/services/api.ts#L671)).
- **Router guard:** global authenticated guard ([router/index.ts:53-67](../../frontend/src/router/index.ts#L53)).

## Error Handling

- **404 Improvement not found** — returned by `get`, `save_wizard_step`, and `admin_patch` when the id is missing or soft-deleted ([app/api/improvements.py:119-120](../../app/api/improvements.py#L119), [:153-154](../../app/api/improvements.py#L153), [:173-174](../../app/api/improvements.py#L173)).
- **400 Unknown wizard step** — invalid `{step}` ([app/api/improvements.py:147-148](../../app/api/improvements.py#L147)).
- **400 No fields to update** — empty admin patch ([app/api/improvements.py:166-167](../../app/api/improvements.py#L166)).
- **Frontend:** list-load failures set an inline error string ([ImprovementsView.vue:38-39](../../frontend/src/views/ImprovementsView.vue#L38)); suggest/delete failures raise error-tone toasts ([ImprovementsView.vue:107-108](../../frontend/src/views/ImprovementsView.vue#L107), [:127-128](../../frontend/src/views/ImprovementsView.vue#L127)).
- **DELETE is fire-and-mostly-silent on missing rows** — it issues the UPDATE unconditionally and returns 204 regardless of whether a row matched ([app/api/improvements.py:180-188](../../app/api/improvements.py#L180)).

## Permissions

**Verified reality for this module: JWT presence only. There is no admin gate on any Improvements endpoint.**

- Every endpoint depends on `CurrentUser` (a valid JWT) and nothing else ([app/api/improvements.py:77](../../app/api/improvements.py#L77), [:94](../../app/api/improvements.py#L94), [:115](../../app/api/improvements.py#L115), [:145](../../app/api/improvements.py#L145), [:164](../../app/api/improvements.py#L164), [:180](../../app/api/improvements.py#L180)).
- `app/api/improvements.py` does **not** import `require_admin` or `is_admin` from `app/security/roles.py`, and does not compare against `LEGACY_ADMIN_EMAIL`. The endpoint named `admin_patch` ([app/api/improvements.py:163](../../app/api/improvements.py#L163)) is, despite its name, callable by **any** authenticated user — the "admin" label is descriptive, not enforced.
- `auth_users.role` is not consulted by `get_current_user`; the `User` object carries only `email` ([app/auth.py:36-39](../../app/auth.py#L36), [:172-205](../../app/auth.py#L172)).
- The Improvements route has no `meta.adminOnly` client guard; it is reachable by any authenticated user ([router/index.ts:39](../../frontend/src/router/index.ts#L39)). (The only `adminOnly` route in the app is `/admin/help` — [router/index.ts:44](../../frontend/src/router/index.ts#L44).)

> Role tiers are not active for Improvements. `app/security/roles.py` exists and is wired into other modules (help, settings, email, sessions, locks), but it is intentionally not applied here. Treat Improvements authorization as "logged-in user" with no further differentiation.

## Reporting Impacts

- **No dedicated reporting/analytics surface exists for Improvements.** NOT VERIFIED IN CODE — no aggregate, count-export, or dashboard query over the `improvements` table was found beyond the in-page tab counts.
- The page header reports a count (`{n} of {n}`) and per-status tab counts, both computed client-side from the loaded list ([ImprovementsView.vue:138-140](../../frontend/src/views/ImprovementsView.vue#L138), [:46-55](../../frontend/src/views/ImprovementsView.vue#L46)).
- The list status-tab counts are derived from the in-memory list only, so they reflect the currently loaded page of data, not a server-side aggregate.

## Audit Requirements

The `audit_events` table is the append-only log ([migrations/004_audit.sql:3-11](../../migrations/004_audit.sql#L3)). Improvements writes:

- **`improvement.suggest`** on create, with summary `suggested: {title}` and the full payload JSON in `details` ([app/api/improvements.py:105-109](../../app/api/improvements.py#L105)).
- **`improvement.wizard`** on a wizard-step save, summary `updated {step} on {id}` ([app/api/improvements.py:155-158](../../app/api/improvements.py#L155)).
- **`improvement.delete`** on soft delete, summary `deleted {id}` ([app/api/improvements.py:184-186](../../app/api/improvements.py#L184)).

> **Audit gap (verified):** The admin PATCH endpoint (`admin_patch`) writes **no** audit event ([app/api/improvements.py:163-176](../../app/api/improvements.py#L163)). Status/risk/target-version/admin-notes changes are therefore not recorded in `audit_events`.

`actor_email` is the JWT user's email in every write. `session_id` is left NULL for improvement events (they are non-session events; the column allows NULL — [migrations/004_audit.sql:5](../../migrations/004_audit.sql#L5)).

## Data Relationships

- **`improvements`** is a standalone table with no foreign keys ([migrations/005_improvements.sql:3-24](../../migrations/005_improvements.sql#L3)). It does not reference `sessions`, `auth_users`, or any other entity. `submitted_by` is a free `TEXT` email, not an FK.
- **`audit_events`** rows generated by this module set `actor_email` (text) and leave `session_id` NULL; there is no FK from `audit_events` back to `improvements` ([migrations/004_audit.sql:3-11](../../migrations/004_audit.sql#L3)).
- Indexes: `improvements_status_idx` (partial, `WHERE deleted_at IS NULL`) and `improvements_submitted_at_idx` (partial, DESC) ([migrations/005_improvements.sql:26-27](../../migrations/005_improvements.sql#L26)).

## Known Constraints

- **Status form mismatch** between DB (underscored) and frontend tabs (hyphenated) means three status filters (Under Review / In Progress / Rolled Out) will not match real rows. See [States](#states).
- **Detail pane is read-mostly and front-loaded.** The view never calls `improvApi.get(id)`; the detail prop is adapted from the summary row, with the description hardcoded to a placeholder string ("(detail body loads from /v1/improvements/{id} once wired)") ([ImprovementsView.vue:66-83](../../frontend/src/views/ImprovementsView.vue#L66)). The backend `GET /v1/improvements/{id}` (which returns the wizard markdown columns) exists but is not invoked by the UI. PARTIALLY IMPLEMENTED.
- **Wizard documents are generated client-side**, not persisted. The Requirements/Implementation/Testing markdown shown in the detail pane is templated from the item's fields in the browser ([ImprovDetail.vue:43-104](../../frontend/src/components/improvements/ImprovDetail.vue#L43)); the stored `requirements_md`/`implementation_md`/`testing_md`/`review_md` columns are never read or written by the UI.
- **AI Model selector is inert** — local state only, never transmitted ([ImprovDetail.vue:15](../../frontend/src/components/improvements/ImprovDetail.vue#L15), [:186-195](../../frontend/src/components/improvements/ImprovDetail.vue#L186)).
- **No enum validation** on status/priority/risk/type at the API or DB layer (TEXT columns, no CHECK constraints) ([migrations/005_improvements.sql:7-11](../../migrations/005_improvements.sql#L7)).
- **No pagination** — `list_improvements` returns all matching rows; the partial DESC index supports ordering but there is no LIMIT/OFFSET ([app/api/improvements.py:76-90](../../app/api/improvements.py#L76)).

## Source Verification
- **Files Used:** `app/api/improvements.py`, `migrations/005_improvements.sql`, `migrations/004_audit.sql`, `frontend/src/views/ImprovementsView.vue`, `frontend/src/components/improvements/ImprovDetail.vue`, `frontend/src/components/overlays/SuggestImprovementModal.vue`, `frontend/src/services/api.ts`, `frontend/src/router/index.ts`, `app/auth.py`, `app/security/roles.py`
- **Components Used:** `ImprovementsView.vue`, `ImprovDetail.vue`, `SuggestImprovementModal.vue`
- **APIs Used:** `GET /v1/improvements`, `POST /v1/improvements`, `GET /v1/improvements/{id}`, `PUT /v1/improvements/{id}/wizard/{step}`, `PATCH /v1/improvements/{id}`, `DELETE /v1/improvements/{id}`
- **Database Tables Used:** `improvements`, `audit_events`
- **Permission Logic Used:** JWT presence only (`CurrentUser`) — no admin gate on any Improvements endpoint
- **Confidence Score:** High — every claim traced to a specific file:line; flagged gaps are verified discrepancies in the code, not assumptions.
- **Evidence Links:** [app/api/improvements.py:76](../../app/api/improvements.py#L76), [app/api/improvements.py:163](../../app/api/improvements.py#L163), [migrations/005_improvements.sql:8](../../migrations/005_improvements.sql#L8), [ImprovementsView.vue:49](../../frontend/src/views/ImprovementsView.vue#L49), [ImprovDetail.vue:143](../../frontend/src/components/improvements/ImprovDetail.vue#L143)
