# Improvements — Technical Spec

> Module key: `improvements`. Backend router: [`app/api/improvements.py`](../../app/api/improvements.py). Table: [`migrations/005_improvements.sql`](../../migrations/005_improvements.sql). Frontend root: [`frontend/src/views/ImprovementsView.vue`](../../frontend/src/views/ImprovementsView.vue).

## Architecture

A thin FastAPI CRUD router over a single Postgres table, fronted by a Vue 3 master/detail view. There is no service layer between the router and SQL — the endpoints execute raw `text()` SQL against the request-scoped async session ([app/api/improvements.py:12](../../app/api/improvements.py#L12), [:79-89](../../app/api/improvements.py#L79)).

```
ImprovementsView.vue ──(api.ts improvements.*)──> /v1/improvements/* (app/api/improvements.py)
   ├── SuggestImprovementModal.vue                       │
   └── ImprovDetail.vue (local-only; not wired to API)   └──> improvements table + audit_events table
```

The router is registered in [app/main.py:42](../../app/main.py#L42) and mounted at [app/main.py:225](../../app/main.py#L225) with prefix `/v1/improvements` and tag `improvements` ([app/api/improvements.py:17](../../app/api/improvements.py#L17)).

> **Scope note on `app/iil/adaptive_learning.py`:** This file was listed alongside Improvements but is **not part of this module**. It updates `instructor_profiles` from a session's normalization audit and is invoked by `learn_iil_task` ([app/tasks/kp_task.py:179-390](../../app/tasks/kp_task.py#L179), [:289-295](../../app/tasks/kp_task.py#L289)) in the transcript processing pipeline. It does not touch the `improvements` table and shares no code path with the Improvements router. It is covered only in [Background Jobs](#background-jobs) for completeness.

## Frontend Components

### `ImprovementsView.vue` ([frontend/src/views/ImprovementsView.vue](../../frontend/src/views/ImprovementsView.vue))

- Owns the page state: `items` (loaded summaries), `loading`, `error`, `statusTab`, `selectedId`, `searchQ` ([:22-28](../../frontend/src/views/ImprovementsView.vue#L22)).
- `load()` fetches the list on mount; auto-selects the first item ([:30-44](../../frontend/src/views/ImprovementsView.vue#L30)).
- `filters` computes per-status tab counts; `visibleItems` applies status + title-search filtering ([:46-62](../../frontend/src/views/ImprovementsView.vue#L46)).
- `selectedForDetail` adapts the lightweight `ImprovementSummary` into the legacy `ImprovementFixture` shape `ImprovDetail` expects, supplying placeholder values for `surface`, `area`, `url`, and `description` ([:66-83](../../frontend/src/views/ImprovementsView.vue#L66)).
- Handlers: `suggest()` (opens modal → POST), `delRow()` (confirm → DELETE) ([:94-130](../../frontend/src/views/ImprovementsView.vue#L94)).

### `SuggestImprovementModal.vue` ([frontend/src/components/overlays/SuggestImprovementModal.vue](../../frontend/src/components/overlays/SuggestImprovementModal.vue))

- Local refs: `title`, `surface`, `priority` (`'low'|'med'|'high'|'crit'`), `desc` ([:16-19](../../frontend/src/components/overlays/SuggestImprovementModal.vue#L16)).
- `submit()` validates title is non-empty, generates a throwaway client id `IMP-{Date.now()}`, fires the `onSubmit` callback, toasts, and closes the modal ([:21-30](../../frontend/src/components/overlays/SuggestImprovementModal.vue#L21)). The client id is not the persisted id; the persisted UUID comes back from the POST response.

### `ImprovDetail.vue` ([frontend/src/components/improvements/ImprovDetail.vue](../../frontend/src/components/improvements/ImprovDetail.vue))

- Pure presentational + local-state component. Props: `item: ImprovementFixture`. Emits: `close` ([:11-12](../../frontend/src/components/improvements/ImprovDetail.vue#L11)).
- Local refs: `step`, `model` (AI model selector), `adminStatus`, `adminRisk`, `adminVersion`, `adminNotes`, `expandAll`, `openSections` ([:14-23](../../frontend/src/components/improvements/ImprovDetail.vue#L14)).
- `reqDoc`/`implDoc`/`testDoc` are computeds that template markdown from `item` fields — generated entirely in the browser ([:43-104](../../frontend/src/components/improvements/ImprovDetail.vue#L43)).
- `copyText()`, `exportMd()` use the Clipboard API and a Blob download ([:108-129](../../frontend/src/components/improvements/ImprovDetail.vue#L108)).
- `regenerate()` and `save()` are no-ops that emit honest warning toasts — they do not call the API ([:136-148](../../frontend/src/components/improvements/ImprovDetail.vue#L136)).

### Fixture / type shapes

- `ImprovementFixture` (the detail prop shape) lives in [frontend/src/fixtures/improvements.ts:4-16](../../frontend/src/fixtures/improvements.ts#L4) and includes UI-only fields (`surface`, `url`, `area`) that the backend summary does not carry.
- `ImprovementSummary` (the API shape) is in [frontend/src/services/api.ts:660-669](../../frontend/src/services/api.ts#L660): `id, title, status, risk, priority, submitted_at, submitted_by, is_security`.

## Backend Services

There is no separate service module. All logic is in the router functions ([app/api/improvements.py](../../app/api/improvements.py)):

| Function | Method/path | Lines |
|---|---|---|
| `list_improvements` | `GET /v1/improvements` | [76-90](../../app/api/improvements.py#L76) |
| `suggest` | `POST /v1/improvements` | [93-111](../../app/api/improvements.py#L93) |
| `get_improvement` | `GET /v1/improvements/{id}` | [114-133](../../app/api/improvements.py#L114) |
| `save_wizard_step` | `PUT /v1/improvements/{id}/wizard/{step}` | [144-160](../../app/api/improvements.py#L144) |
| `admin_patch` | `PATCH /v1/improvements/{id}` | [163-176](../../app/api/improvements.py#L163) |
| `delete_improvement` | `DELETE /v1/improvements/{id}` | [179-188](../../app/api/improvements.py#L179) |

`_row_to_summary()` ([:63-73](../../app/api/improvements.py#L63)) normalizes a DB row into the summary dict, ISO-formatting `submitted_at`. `get_improvement` reuses the summary and adds the detail-only columns ([:121-132](../../app/api/improvements.py#L121)). `save_wizard_step` and `admin_patch` both re-query through `get_improvement` to return the post-update detail ([:160](../../app/api/improvements.py#L160), [:176](../../app/api/improvements.py#L176)).

## APIs

All routes require a valid JWT (`CurrentUser`). Base prefix `/v1/improvements`.

### `GET /v1/improvements`
Query param `status_filter` (optional). If present and not `"all"`, filters `status = :st`; otherwise returns all non-deleted rows. Always ordered `submitted_at DESC`. Returns `list[ImprovementSummary]` ([:76-90](../../app/api/improvements.py#L76)).

### `POST /v1/improvements`  →  `201`
Body `SuggestPayload`: `title` (3–512, required), `description?`, `type?`, `priority` (default `"medium"`), `area?`, `is_security` (default `false`) ([:43-49](../../app/api/improvements.py#L43)). Inserts the row (other columns take DB defaults), writes an `improvement.suggest` audit event, commits, returns the summary ([:93-111](../../app/api/improvements.py#L93)). `submitted_by` is set from `user.email`, not the payload.

### `GET /v1/improvements/{id}`
Returns `ImprovementDetail` (summary + `description, type, area, target_version, admin_notes, requirements_md, implementation_md, testing_md, review_md`). 404 if missing/soft-deleted ([:114-133](../../app/api/improvements.py#L114)).

### `PUT /v1/improvements/{id}/wizard/{step}`
`step` ∈ {`requirements`, `implementation`, `testing`, `review`} mapped to the matching `*_md` column ([:136-141](../../app/api/improvements.py#L136)). Body `WizardStepPayload.body_md`. Updates the column + `updated_at`, writes `improvement.wizard` audit, returns the refreshed detail. 400 on unknown step, 404 on missing id ([:144-160](../../app/api/improvements.py#L144)).

### `PATCH /v1/improvements/{id}`
Body `AdminPatch`: `status?`, `risk?`, `target_version?`, `admin_notes?` ([:56-60](../../app/api/improvements.py#L56)). Builds a dynamic `SET` clause from non-null fields plus `updated_at = now()`. 400 if no fields, 404 if missing. **Writes no audit event.** ([:163-176](../../app/api/improvements.py#L163)).

### `DELETE /v1/improvements/{id}`  →  `204`
Soft delete (`deleted_at = now()`), writes `improvement.delete` audit, returns `Response(status_code=204)` ([:179-188](../../app/api/improvements.py#L179)). Uses `response_class=Response` per the project's 204 convention. The UPDATE has no `deleted_at IS NULL` guard.

### API client ([frontend/src/services/api.ts:671-684](../../frontend/src/services/api.ts#L671))
`improvements.list/get/suggest/saveStep/admin/remove`. `saveStep` → PUT wizard, `admin` → PATCH. The view currently calls only `list`, `suggest`, and `remove`.

## Data Models

### `improvements` ([migrations/005_improvements.sql:3-24](../../migrations/005_improvements.sql#L3))

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `DEFAULT gen_random_uuid()` |
| `title` | TEXT NOT NULL | |
| `description` | TEXT | |
| `type` | TEXT | "feature"/"bug"/"ux"/etc. (comment only) |
| `status` | TEXT NOT NULL | default `'pending'`; comment lists 7 values |
| `priority` | TEXT NOT NULL | default `'medium'` |
| `risk` | TEXT NOT NULL | default `'low'` |
| `area` | TEXT | |
| `target_version` | TEXT | |
| `is_security` | BOOLEAN NOT NULL | default `FALSE` |
| `submitted_by` | TEXT NOT NULL | server-set to JWT email |
| `submitted_at` | TIMESTAMPTZ NOT NULL | default `now()` |
| `admin_notes` | TEXT | |
| `requirements_md` | TEXT | wizard step payload |
| `implementation_md` | TEXT | wizard step payload |
| `testing_md` | TEXT | wizard step payload |
| `review_md` | TEXT | wizard step payload |
| `deleted_at` | TIMESTAMPTZ | NULL = live |
| `updated_at` | TIMESTAMPTZ NOT NULL | default `now()` |

Indexes (both partial, `WHERE deleted_at IS NULL`): `improvements_status_idx` on `status`, `improvements_submitted_at_idx` on `submitted_at DESC` ([:26-27](../../migrations/005_improvements.sql#L26)). No CHECK constraints, no foreign keys.

### `audit_events` ([migrations/004_audit.sql:3-11](../../migrations/004_audit.sql#L3))
`id, session_id (FK sessions, ON DELETE SET NULL, nullable), actor_email, kind NOT NULL, summary, details JSONB DEFAULT '{}', occurred_at`. Improvements writes leave `session_id` NULL.

### Pydantic models ([app/api/improvements.py:20-60](../../app/api/improvements.py#L20))
`ImprovementSummary`, `ImprovementDetail(ImprovementSummary)`, `SuggestPayload`, `WizardStepPayload`, `AdminPatch`.

## Events

This module emits **audit log rows** (not a pub/sub bus) into `audit_events`:

- `improvement.suggest` — on create; `details` carries `payload.model_dump()` as JSONB ([app/api/improvements.py:106-109](../../app/api/improvements.py#L106)).
- `improvement.wizard` — on wizard-step save ([:155-158](../../app/api/improvements.py#L155)).
- `improvement.delete` — on soft delete ([:184-186](../../app/api/improvements.py#L184)).

No `improvement.patch`/`improvement.admin` event is emitted ([:163-176](../../app/api/improvements.py#L163)). No Celery task is dispatched by any Improvements endpoint.

## State Management

- **Frontend:** Component-local reactive state only. No Pinia store is used for Improvements; `ImprovementsView.vue` holds `items` in a local `ref` ([frontend/src/views/ImprovementsView.vue:22](../../frontend/src/views/ImprovementsView.vue#L22)). The only store imported is `useAuthStore` in the router guard ([router/index.ts:23](../../frontend/src/router/index.ts#L23)).
- **Optimistic list mutation:** create prepends to `items`; delete filters out the row — both update local state directly after the API call resolves ([ImprovementsView.vue:104](../../frontend/src/views/ImprovementsView.vue#L104), [:125](../../frontend/src/views/ImprovementsView.vue#L125)).
- **Backend:** Stateless per-request; each handler uses the injected `DbSession` and commits explicitly ([app/api/improvements.py:110](../../app/api/improvements.py#L110), [:159](../../app/api/improvements.py#L159), [:175](../../app/api/improvements.py#L175), [:187](../../app/api/improvements.py#L187)).

## Validation

- **Pydantic:** `title` constrained `min_length=3, max_length=512` ([app/api/improvements.py:44](../../app/api/improvements.py#L44)). All other fields are optional/defaulted; types coerce per Pydantic.
- **Wizard step whitelist:** dict lookup in `_WIZARD_COLUMNS`; unknown → 400 ([:136-148](../../app/api/improvements.py#L136)). This whitelist also prevents SQL injection via `{step}` since only the four mapped column names can reach the f-string ([:146-151](../../app/api/improvements.py#L146)).
- **AdminPatch dynamic SET:** keys come only from `payload.model_dump(exclude_none=True)`, whose keys are the fixed Pydantic field names; values are bound parameters ([:165-172](../../app/api/improvements.py#L165)).
- **No enum/domain validation** on `status`/`priority`/`risk`/`type` at any layer (TEXT columns, no CHECK) — arbitrary strings persist. NOT VERIFIED IN CODE that invalid enum values are rejected; they are not.
- **Frontend:** modal blocks empty title only ([SuggestImprovementModal.vue:22-25](../../frontend/src/components/overlays/SuggestImprovementModal.vue#L22)).

## Security

- **Auth:** Every route depends on `CurrentUser` → `get_current_user`, which decodes the HS256 JWT and verifies the user is active (DB lookup with env-CSV fallback) ([app/auth.py:172-208](../../app/auth.py#L172)).
- **SQL safety:** All values are passed as bound parameters via SQLAlchemy `text()`; the only string-interpolated SQL fragments are column names sourced from server-controlled whitelists (`_WIZARD_COLUMNS` and the fixed `AdminPatch` field set) — not from raw user input ([app/api/improvements.py:150](../../app/api/improvements.py#L150), [:168-171](../../app/api/improvements.py#L168)).
- **Submitter spoofing prevention:** `submitted_by` cannot be set by the client; it is forced to the JWT email ([:103](../../app/api/improvements.py#L103)).
- **No object-level access control:** any authenticated user can read, patch, or delete any improvement by id — there is no per-record ownership check ([:114-188](../../app/api/improvements.py#L114)).

## Permissions

**JWT presence only — no role/admin gate on this module.**

- `app/api/improvements.py` imports `CurrentUser` and `DbSession` and nothing from `app/security/roles.py` ([:14-15](../../app/api/improvements.py#L14)). Verified by grep: `require_admin`/`is_admin` appear in `help.py`, `settings.py`, `email_templates.py`, `email_debug.py`, `sessions.py`, `locks.py` — **but not** in `improvements.py`.
- The handler `admin_patch` is named "admin" for intent only; it is reachable by any authenticated user ([:163-164](../../app/api/improvements.py#L163)).
- `app/security/roles.py` defines `is_admin`/`require_admin` against `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` ([app/security/roles.py:54](../../app/security/roles.py#L54), [:62-92](../../app/security/roles.py#L62)); `auth_users.role` is not loaded by `get_current_user` ([app/auth.py:172-205](../../app/auth.py#L172)). None of that gating is applied to Improvements.
- Client router: the `improvements` route carries no `meta.adminOnly`; the only admin-gated client route is `/admin/help` ([router/index.ts:39](../../frontend/src/router/index.ts#L39), [:44](../../frontend/src/router/index.ts#L44), [:63](../../frontend/src/router/index.ts#L63)).

## Integrations

- **None for the live data path.** No external service (GCS, Gemini, Vertex, STT, SMTP) is called by any Improvements endpoint or by `ImprovementsView`/`ImprovDetail`.
- The "AI Model" dropdown (Gemini/GPT-5/Claude) in `ImprovDetail` is inert local state — no AI integration is wired ([ImprovDetail.vue:15](../../frontend/src/components/improvements/ImprovDetail.vue#L15), [:186-195](../../frontend/src/components/improvements/ImprovDetail.vue#L186)). The `regenerate()` toast explicitly says AI regeneration is "not yet wired" ([:136-141](../../frontend/src/components/improvements/ImprovDetail.vue#L136)). IMPLEMENTATION NOT FOUND for any AI prompt-generation backend tied to Improvements.

## Background Jobs

- **None are triggered by the Improvements module.** No Celery `apply_async`/`delay` call exists in `app/api/improvements.py`.
- `app/iil/adaptive_learning.py::update_instructor_profile` is a **separate** pipeline concern, not part of Improvements. It is a pure function that computes a rolling-average filler rate, rolling-average compression ratio, and a frequency-discovered filler-word list (>3% threshold) for an instructor, returning a `ProfileUpdate` dataclass ([app/iil/adaptive_learning.py:28-104](../../app/iil/adaptive_learning.py#L28)). It is idempotent and non-fatal (catches all exceptions, returns the prior profile on failure — [:96-104](../../app/iil/adaptive_learning.py#L96)). It is invoked by `learn_iil_task`, which runs after key-points processing and writes `instructor_profiles`/`session_instructor_map`/`session_patterns` ([app/tasks/kp_task.py:148-150](../../app/tasks/kp_task.py#L148), [:179-390](../../app/tasks/kp_task.py#L179)). It does not read or write the `improvements` table.

## Error Handling

- **HTTP errors:** `404 Improvement not found` (get/wizard/patch), `400 Unknown wizard step`, `400 No fields to update` ([app/api/improvements.py:120](../../app/api/improvements.py#L120), [:148](../../app/api/improvements.py#L148), [:154](../../app/api/improvements.py#L154), [:167](../../app/api/improvements.py#L167), [:174](../../app/api/improvements.py#L174)).
- **Commit discipline:** writes commit only after both the data mutation and (where present) the audit insert succeed ([:110](../../app/api/improvements.py#L110), [:159](../../app/api/improvements.py#L159), [:187](../../app/api/improvements.py#L187)); a failure before commit rolls back the unit of work via the `DbSession` dependency lifecycle.
- **Frontend:** `load()` traps exceptions into `error` ([ImprovementsView.vue:38-39](../../frontend/src/views/ImprovementsView.vue#L38)); `suggest()`/`delRow()` toast the error message ([:107-108](../../frontend/src/views/ImprovementsView.vue#L107), [:127-128](../../frontend/src/views/ImprovementsView.vue#L127)). `copyText()` falls back to a "Clipboard blocked" warn toast ([ImprovDetail.vue:112-114](../../frontend/src/components/improvements/ImprovDetail.vue#L112)).

## Performance Considerations

- **No pagination / LIMIT** — `GET /v1/improvements` returns every matching row ([app/api/improvements.py:76-90](../../app/api/improvements.py#L76)). For large backlogs this loads the entire table client-side; all tab counts and search are computed in the browser over the full list ([ImprovementsView.vue:46-62](../../frontend/src/views/ImprovementsView.vue#L46)).
- **Indexing** — both query shapes (status filter, submitted_at ordering) are backed by partial indexes excluding soft-deleted rows ([migrations/005_improvements.sql:26-27](../../migrations/005_improvements.sql#L26)).
- **`SELECT *`** in `get_improvement` ([:117](../../app/api/improvements.py#L117)) pulls all columns including the four potentially large `*_md` markdown bodies; acceptable for a single-row detail fetch.
- **Update round-trips** — `save_wizard_step` and `admin_patch` each do an UPDATE…RETURNING then a second SELECT via `get_improvement` ([:149-160](../../app/api/improvements.py#L149), [:170-176](../../app/api/improvements.py#L170)), i.e. two queries per mutation.

## Source Verification
- **Files Used:** `app/api/improvements.py`, `migrations/005_improvements.sql`, `migrations/004_audit.sql`, `app/iil/adaptive_learning.py`, `app/tasks/kp_task.py`, `app/auth.py`, `app/security/roles.py`, `app/main.py`, `frontend/src/views/ImprovementsView.vue`, `frontend/src/components/improvements/ImprovDetail.vue`, `frontend/src/components/overlays/SuggestImprovementModal.vue`, `frontend/src/services/api.ts`, `frontend/src/fixtures/improvements.ts`, `frontend/src/router/index.ts`
- **Components Used:** `ImprovementsView.vue`, `ImprovDetail.vue`, `SuggestImprovementModal.vue`
- **APIs Used:** `GET/POST /v1/improvements`, `GET/PUT/PATCH/DELETE /v1/improvements/{id}[/wizard/{step}]`
- **Database Tables Used:** `improvements`, `audit_events` (and, for the unrelated IIL job only: `instructor_profiles`, `session_instructor_map`, `session_patterns`)
- **Permission Logic Used:** JWT presence only (`CurrentUser`); no `require_admin`/`is_admin` in this module
- **Confidence Score:** High — router, migration, and frontend all read in full; permission claim verified by grep showing `require_admin`/`is_admin` absent from `improvements.py`.
- **Evidence Links:** [app/api/improvements.py:14](../../app/api/improvements.py#L14), [app/api/improvements.py:163](../../app/api/improvements.py#L163), [app/main.py:225](../../app/main.py#L225), [migrations/005_improvements.sql:26](../../migrations/005_improvements.sql#L26), [app/iil/adaptive_learning.py:28](../../app/iil/adaptive_learning.py#L28)
