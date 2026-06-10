# Improvements API — `/v1/improvements`

Master/detail list plus a 5-step authoring wizard for improvement suggestions (feature requests, bugs, UX notes). Backs the Improvements screen.

Router declaration: [app/api/improvements.py:17](../../app/api/improvements.py#L17) — `APIRouter(prefix="/v1/improvements", tags=["improvements"])`.

The router defines **six** endpoints: list, suggest (create), get detail, save wizard step, patch, delete.

> **Authorization reality:** every endpoint in this router is **JWT-only**. There is **no** `LEGACY_ADMIN_EMAIL` / `require_admin` / `is_admin` gate anywhere in this file — the `admin_patch` and `delete_improvement` handlers are named "admin" but enforce nothing beyond a valid JWT. Any authenticated user can patch status/risk/target_version or soft-delete any improvement. (IMPLEMENTATION NOT FOUND: any role check on these routes.)

---

## Shared schemas

`ImprovementSummary` ([app/api/improvements.py:20](../../app/api/improvements.py#L20)) — list + create response shape:

| Field | Type |
|---|---|
| `id` | `UUID` |
| `title` | `str` |
| `status` | `str` |
| `risk` | `str` |
| `priority` | `str` |
| `submitted_at` | `str` (ISO-8601) |
| `submitted_by` | `str` |
| `is_security` | `bool` |

`ImprovementDetail` ([app/api/improvements.py:31](../../app/api/improvements.py#L31)) — extends `ImprovementSummary` with:

| Field | Type |
|---|---|
| `description` | `str \| null` |
| `type` | `str \| null` |
| `area` | `str \| null` |
| `target_version` | `str \| null` |
| `admin_notes` | `str \| null` |
| `requirements_md` | `str \| null` |
| `implementation_md` | `str \| null` |
| `testing_md` | `str \| null` |
| `review_md` | `str \| null` |

`submitted_at` is serialized via `_row_to_summary` ([app/api/improvements.py:63](../../app/api/improvements.py#L63)), which calls `.isoformat()` when the value supports it.

---

## `GET /v1/improvements`

- **Decorator:** [app/api/improvements.py:76](../../app/api/improvements.py#L76) — `@router.get("", response_model=list[ImprovementSummary])`
- **Handler:** `list_improvements` ([app/api/improvements.py:77](../../app/api/improvements.py#L77))
- **Purpose:** List non-deleted improvements, newest first, optionally filtered by status.
- **Authentication:** JWT (dependency `_u: CurrentUser`, [app/api/improvements.py:77](../../app/api/improvements.py#L77)).
- **Authorization:** JWT only.
- **Request Schema:** query param `status_filter: str | null` (optional). When present and not `"all"`, filters `status = :st`; otherwise returns all non-deleted rows ([app/api/improvements.py:78](../../app/api/improvements.py#L78)).
- **Response Schema:** `200` — `list[ImprovementSummary]`.
- **Validation Rules:** always filters `deleted_at IS NULL`; orders `submitted_at DESC`.
- **Errors:** `401` (no/invalid JWT). No `4xx` raised in the handler; unknown `status_filter` simply returns an empty list.

### Example

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://rounds.vin/v1/improvements?status_filter=pending"
```

Frontend: `improvements.list(statusFilter)` ([frontend/src/services/api.ts:673](../../frontend/src/services/api.ts#L673)).

---

## `POST /v1/improvements`

- **Decorator:** [app/api/improvements.py:93](../../app/api/improvements.py#L93) — `@router.post("", response_model=ImprovementSummary, status_code=201)`
- **Handler:** `suggest` ([app/api/improvements.py:94](../../app/api/improvements.py#L94))
- **Purpose:** Create a new improvement suggestion. Records an audit event.
- **Authentication:** JWT (`user: CurrentUser`).
- **Authorization:** JWT only.

### Request Schema — `SuggestPayload` ([app/api/improvements.py:43](../../app/api/improvements.py#L43))

| Field | Type | Default | Validation |
|---|---|---|---|
| `title` | `str` | required | `min_length=3`, `max_length=512` ([app/api/improvements.py:44](../../app/api/improvements.py#L44)) |
| `description` | `str \| null` | `null` | |
| `type` | `str \| null` | `null` | |
| `priority` | `str` | `"medium"` | |
| `area` | `str \| null` | `null` | |
| `is_security` | `bool` | `false` | |

### Response Schema

`201 Created` — `ImprovementSummary`. The DB defaults `status='pending'`, `risk='low'` ([migrations/005_improvements.sql:8](../../migrations/005_improvements.sql#L8)).

### Behavior

`INSERT INTO improvements (...) RETURNING ...` ([app/api/improvements.py:96](../../app/api/improvements.py#L96)); `submitted_by` is set to `user.email`. Then inserts an `audit_events` row with `kind='improvement.suggest'`, summary `"suggested: <title>"`, and `details` = the JSON-dumped payload ([app/api/improvements.py:105](../../app/api/improvements.py#L105)). Commits once.

### Errors

| Status | Cause |
|---|---|
| `401` | No/invalid JWT. |
| `422` | `title` shorter than 3 or longer than 512 chars (Pydantic validation). |

### Example

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Add keyboard nav to editor","priority":"high","area":"editor"}' \
  https://rounds.vin/v1/improvements
```

Frontend: `improvements.suggest(payload)` ([frontend/src/services/api.ts:676](../../frontend/src/services/api.ts#L676)).

---

## `GET /v1/improvements/{improvement_id}`

- **Decorator:** [app/api/improvements.py:114](../../app/api/improvements.py#L114) — `@router.get("/{improvement_id}", response_model=ImprovementDetail)`
- **Handler:** `get_improvement` ([app/api/improvements.py:115](../../app/api/improvements.py#L115))
- **Purpose:** Fetch a single improvement with all wizard/detail fields.
- **Authentication:** JWT (`_u: CurrentUser`).
- **Authorization:** JWT only.
- **Request Schema:** path `improvement_id: UUID`; no body.
- **Response Schema:** `200` — `ImprovementDetail`.
- **Behavior:** `SELECT * FROM improvements WHERE id = :id AND deleted_at IS NULL` ([app/api/improvements.py:116](../../app/api/improvements.py#L116)); composes summary + detail fields.
- **Errors:** `404 "Improvement not found"` when no matching non-deleted row ([app/api/improvements.py:119](../../app/api/improvements.py#L119)); `401`; `422` if `improvement_id` is not a UUID.

Frontend: `improvements.get(id)` ([frontend/src/services/api.ts:675](../../frontend/src/services/api.ts#L675)).

---

## `PUT /v1/improvements/{improvement_id}/wizard/{step}`

- **Decorator:** [app/api/improvements.py:144](../../app/api/improvements.py#L144) — `@router.put("/{improvement_id}/wizard/{step}", response_model=ImprovementDetail)`
- **Handler:** `save_wizard_step` ([app/api/improvements.py:145](../../app/api/improvements.py#L145))
- **Purpose:** Save one markdown wizard step (requirements / implementation / testing / review) onto an improvement.
- **Authentication:** JWT (`user: CurrentUser`).
- **Authorization:** JWT only.

### Request Schema

- Path: `improvement_id: UUID`, `step: str`.
- Body: `WizardStepPayload` ([app/api/improvements.py:52](../../app/api/improvements.py#L52)) — `{ "body_md": str }` (required).

### Validation Rules

`step` must be one of the keys in `_WIZARD_COLUMNS` ([app/api/improvements.py:136](../../app/api/improvements.py#L136)), which map step → column:

| `step` | column written |
|---|---|
| `requirements` | `requirements_md` |
| `implementation` | `implementation_md` |
| `testing` | `testing_md` |
| `review` | `review_md` |

There are **four** valid steps (the file/route call it a "5-step wizard," but only four map to a markdown column — the fifth step has no column here). PARTIALLY IMPLEMENTED: the "5-step" naming vs. the 4-column map.

### Behavior

`UPDATE improvements SET <col> = :body, updated_at = now() WHERE id = :id AND deleted_at IS NULL RETURNING *` ([app/api/improvements.py:149](../../app/api/improvements.py#L149)). Inserts an `audit_events` row (`kind='improvement.wizard'`, summary `"updated <step> on <id>"`, [app/api/improvements.py:155](../../app/api/improvements.py#L155)). Returns the refreshed detail via `get_improvement`.

### Errors

| Status | Cause |
|---|---|
| `400` | Unknown wizard step: `{"detail": "Unknown wizard step: <step>"}` ([app/api/improvements.py:148](../../app/api/improvements.py#L148)). |
| `404` | Improvement not found / already deleted ([app/api/improvements.py:153](../../app/api/improvements.py#L153)). |
| `401` | No/invalid JWT. |
| `422` | `improvement_id` not a UUID, or body missing `body_md`. |

### Example

```bash
curl -s -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"body_md":"## Requirements\n- ..."}' \
  https://rounds.vin/v1/improvements/<id>/wizard/requirements
```

Frontend: `improvements.saveWizard(id, step, body_md)` → `PUT .../wizard/<step>` ([frontend/src/services/api.ts:679](../../frontend/src/services/api.ts#L679)).

---

## `PATCH /v1/improvements/{improvement_id}`

- **Decorator:** [app/api/improvements.py:163](../../app/api/improvements.py#L163) — `@router.patch("/{improvement_id}", response_model=ImprovementDetail)`
- **Handler:** `admin_patch` ([app/api/improvements.py:164](../../app/api/improvements.py#L164))
- **Purpose:** Update administrative fields on an improvement (status / risk / target_version / admin_notes).
- **Authentication:** JWT (`user: CurrentUser`).
- **Authorization:** JWT only — **despite the handler name `admin_patch`, no admin gate is applied.** Any authenticated user can call it.

### Request Schema — `AdminPatch` ([app/api/improvements.py:56](../../app/api/improvements.py#L56))

| Field | Type | Default |
|---|---|---|
| `status` | `str \| null` | `null` |
| `risk` | `str \| null` | `null` |
| `target_version` | `str \| null` | `null` |
| `admin_notes` | `str \| null` | `null` |

### Behavior

Only non-`None` fields are applied (`model_dump(exclude_none=True)`, [app/api/improvements.py:165](../../app/api/improvements.py#L165)). The SET clause is built dynamically from those keys plus `updated_at = now()` ([app/api/improvements.py:168](../../app/api/improvements.py#L168)) and run against `WHERE id = :id AND deleted_at IS NULL`. No `audit_events` row is written by this handler (unlike suggest/wizard/delete). Returns the refreshed detail.

### Errors

| Status | Cause |
|---|---|
| `400` | No fields to update (all payload fields `None`): `{"detail": "No fields to update"}` ([app/api/improvements.py:167](../../app/api/improvements.py#L167)). |
| `404` | Improvement not found / deleted ([app/api/improvements.py:174](../../app/api/improvements.py#L174)). |
| `401` | No/invalid JWT. |
| `422` | `improvement_id` not a UUID. |

### Example

```bash
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"approved","target_version":"4.1.0"}' \
  https://rounds.vin/v1/improvements/<id>
```

Frontend: `improvements.patch(id, patch)` ([frontend/src/services/api.ts:681](../../frontend/src/services/api.ts#L681)).

---

## `DELETE /v1/improvements/{improvement_id}`

- **Decorator:** [app/api/improvements.py:179](../../app/api/improvements.py#L179) — `@router.delete("/{improvement_id}", status_code=204, response_class=Response)`
- **Handler:** `delete_improvement` ([app/api/improvements.py:180](../../app/api/improvements.py#L180))
- **Purpose:** Soft-delete an improvement. Records an audit event.
- **Authentication:** JWT (`user: CurrentUser`).
- **Authorization:** JWT only — no admin gate.
- **Request Schema:** path `improvement_id: UUID`; no body.
- **Response Schema:** `204 No Content`, empty body (`response_class=Response`, returns `Response(status_code=204)`).

### Behavior ([app/api/improvements.py:181](../../app/api/improvements.py#L181))

`UPDATE improvements SET deleted_at = now() WHERE id = :id` (soft delete — note this `UPDATE` has **no** `deleted_at IS NULL` guard, so re-deleting is idempotent in effect). Inserts an `audit_events` row (`kind='improvement.delete'`, summary `"deleted <id>"`). Always returns `204` — there is no existence check, so deleting a non-existent id still returns `204`.

### Errors

| Status | Cause |
|---|---|
| `401` | No/invalid JWT. |
| `422` | `improvement_id` not a UUID. |

(No `404` — the handler does not check whether a row matched.)

### Example

```bash
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
  https://rounds.vin/v1/improvements/<id>
```

Frontend: `improvements.delete(id)` ([frontend/src/services/api.ts:683](../../frontend/src/services/api.ts#L683)).

---

## Related Screens

- **ImprovementsView** — route `/improvements`, name `improvements` ([frontend/src/router/index.ts:39](../../frontend/src/router/index.ts#L39)); component `frontend/src/views/ImprovementsView.vue`.
- **ImprovDetail** — detail/wizard sub-component (`frontend/src/components/improvements/ImprovDetail.vue`).
- API client surface: `frontend/src/services/api.ts:671` (`export const improvements = { ... }`).

## Related Tables

- **`improvements`** — all columns (`id`, `title`, `description`, `type`, `status`, `priority`, `risk`, `area`, `target_version`, `is_security`, `submitted_by`, `submitted_at`, `admin_notes`, `requirements_md`, `implementation_md`, `testing_md`, `review_md`, `deleted_at`, `updated_at`) defined in [migrations/005_improvements.sql:3](../../migrations/005_improvements.sql#L3).
- **`audit_events`** — written by suggest, save_wizard_step, and delete (NOT by admin_patch). Columns from [migrations/004_audit.sql:3](../../migrations/004_audit.sql#L3).

---

## Source Verification
- **Files Used:** app/api/improvements.py, app/auth.py, migrations/005_improvements.sql, migrations/004_audit.sql, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** ImprovementsView.vue, ImprovDetail.vue
- **APIs Used:** `GET /v1/improvements`, `POST /v1/improvements`, `GET /v1/improvements/{id}`, `PUT /v1/improvements/{id}/wizard/{step}`, `PATCH /v1/improvements/{id}`, `DELETE /v1/improvements/{id}`
- **Database Tables Used:** improvements, audit_events
- **Permission Logic Used:** JWT only on all six routes. `admin_patch` and `delete_improvement` are named "admin" but apply NO admin gate — no LEGACY_ADMIN_EMAIL / require_admin / is_admin check exists in this router.
- **Confidence Score:** High — all six handlers and all four Pydantic models read in full; column list verified against migration 005; the missing admin gate on patch/delete confirmed by absence of any is_admin import/call in the file.
- **Evidence Links:** [app/api/improvements.py:76](../../app/api/improvements.py#L76) (list), [app/api/improvements.py:93](../../app/api/improvements.py#L93) (suggest), [app/api/improvements.py:144](../../app/api/improvements.py#L144) (wizard), [app/api/improvements.py:163](../../app/api/improvements.py#L163) (patch — no gate), [app/api/improvements.py:179](../../app/api/improvements.py#L179) (delete), [migrations/005_improvements.sql:3](../../migrations/005_improvements.sql#L3)
