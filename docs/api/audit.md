# Audit API

Router for the global audit-event ledger and per-session correction history.

- **Source file:** [app/api/audit.py](../../app/api/audit.py)
- **Router prefix:** `/v1/audit` — declared at [app/api/audit.py:15](../../app/api/audit.py#L15)
- **Tag:** `audit`

This router contains two endpoints. Both are raw SQL handlers returning plain `list[dict]` (no `response_model` declared on either route).

---

## GET `/v1/audit`

- **Endpoint:** `/v1/audit`
- **Method:** `GET`
- **Decorator:** `@router.get("")` at [app/api/audit.py:18](../../app/api/audit.py#L18)
- **Handler:** `list_events` at [app/api/audit.py:19](../../app/api/audit.py#L19)

### Purpose

Return rows from the `audit_events` ledger, newest first, with optional filtering by session, actor, and event kind, plus pagination.

### Authentication

JWT bearer token required. The handler depends on `_u: CurrentUser` ([app/api/audit.py:20](../../app/api/audit.py#L20)). `CurrentUser` is `Annotated[User, Depends(get_current_user)]` ([app/auth.py:208](../../app/auth.py#L208)); `get_current_user` decodes the HS256 JWT and verifies the user is still active, raising `401` on a missing/invalid token ([app/auth.py:172-205](../../app/auth.py#L172)).

### Authorization

JWT-only. No admin gate — `audit.py` does not import or call `require_admin` / `is_admin` / `LEGACY_ADMIN_EMAIL`. Any authenticated user can read the global ledger. No per-actor or per-session ownership restriction is applied in code.

### Request Schema

| Parameter | In | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| `session_id` | query | UUID (optional) | no | `None` | When set, filters `session_id = :s` (bound as the string form of the UUID) ([app/api/audit.py:28-29](../../app/api/audit.py#L28)). |
| `actor` | query | string (optional) | no | `None` | When set, filters `actor_email = :a` with the value lower-cased ([app/api/audit.py:30-31](../../app/api/audit.py#L30)). |
| `kind` | query | string (optional) | no | `None` | When set, filters `kind = :k` ([app/api/audit.py:32-33](../../app/api/audit.py#L32)). |
| `limit` | query | int | no | `100` | Clamped to a max of `500` via `min(limit, 500)` ([app/api/audit.py:27](../../app/api/audit.py#L27)). |
| `offset` | query | int | no | `0` | Pagination offset ([app/api/audit.py:27](../../app/api/audit.py#L27)). |

No request body.

### Response Schema

`200 OK` → `list[dict]`. No Pydantic `response_model`; the shape is each `audit_events` row selected, with `occurred_at` ISO-formatted ([app/api/audit.py:35-42](../../app/api/audit.py#L35)):

| Field | Type | Notes |
|---|---|---|
| `id` | (row value) | Audit event id. |
| `session_id` | (row value) | Associated session, if any. |
| `actor_email` | string | Actor who triggered the event. |
| `kind` | string | Event kind. |
| `summary` | (row value) | Human summary. |
| `details` | (row value) | Event detail payload (column-typed). |
| `occurred_at` | string | ISO-8601 timestamp (`r["occurred_at"].isoformat()` at [app/api/audit.py:40](../../app/api/audit.py#L40)). |

Rows are ordered `occurred_at DESC` ([app/api/audit.py:37](../../app/api/audit.py#L37)). Exact column types are defined by the `audit_events` table, not this handler — NOT VERIFIED IN CODE here (the handler selects `*` of the listed columns and re-emits them via `dict(r)`).

The frontend client calls this as `audit.list(...)` typed `unknown[]` at [frontend/src/services/api.ts:941-943](../../frontend/src/services/api.ts#L941).

### Validation Rules

- `session_id`, if supplied, must be a valid UUID (FastAPI parses the query type); otherwise `422`.
- `limit` is server-clamped to `500` regardless of the requested value ([app/api/audit.py:27](../../app/api/audit.py#L27)). No clamp/validation on `offset` beyond integer parsing.
- `actor` is normalized to lowercase before matching ([app/api/audit.py:31](../../app/api/audit.py#L31)).
- Filters are AND-combined; with no filters the WHERE clause is omitted entirely ([app/api/audit.py:34](../../app/api/audit.py#L34)).

### Errors

| Status | Condition | Source |
|---|---|---|
| `401` | Missing/invalid/expired JWT, or user no longer active. | [app/auth.py:181-205](../../app/auth.py#L181) |
| `422` | `session_id`/`limit`/`offset` not valid for their declared types. | FastAPI parameter validation (framework default). |

No explicit `404` — an empty result set returns `200` with `[]`.

### Example

Request:

```
GET /v1/audit?actor=johndean@vin.com&kind=session.deleted&limit=50
Authorization: Bearer <jwt>
```

Response (`200`):

```json
[
  {
    "id": "e1...",
    "session_id": "3f1c...",
    "actor_email": "johndean@vin.com",
    "kind": "session.deleted",
    "summary": "Session moved to trash",
    "details": {},
    "occurred_at": "2026-06-08T12:00:00+00:00"
  }
]
```

`kind`/`summary`/`details` example values are illustrative; the response is the verbatim row plus ISO `occurred_at`.

### Related Screens

- Global audit view: [frontend/src/views/AuditView.vue](../../frontend/src/views/AuditView.vue) and the ledger component [frontend/src/components/audit/AuditLedger.vue](../../frontend/src/components/audit/AuditLedger.vue). (Association inferred from grep; exact call-site wiring NOT VERIFIED IN CODE for each.)

### Related Tables

- `audit_events` — the ledger this endpoint reads ([app/api/audit.py:37](../../app/api/audit.py#L37)).

---

## GET `/v1/audit/sessions/{session_id}/corrections`

- **Endpoint:** `/v1/audit/sessions/{session_id}/corrections`
- **Method:** `GET`
- **Decorator:** `@router.get("/sessions/{session_id}/corrections")` at [app/api/audit.py:45](../../app/api/audit.py#L45)
- **Handler:** `list_corrections` at [app/api/audit.py:46](../../app/api/audit.py#L46)

### Purpose

Return the active corrections for a session in the editor-frontend shape, reading from `correction_ledger` and filtering by the session's undo pointer so redo-tail entries don't surface. The output maps each ledger row to the `{id, t, type, actor, seg, prior, next, note}` shape expected by `AuditTabInline.vue` and `DecisionCard.vue` ([app/api/audit.py:47-53](../../app/api/audit.py#L47)).

> Note: this is a read-only **history** endpoint under the `/v1/audit` prefix. It is distinct from the editor's correction-write endpoints (`POST /v1/sessions/{sid}/corrections`, `.../undo`, `.../redo`) which live in a different router and are accessed in the frontend via separate client calls ([frontend/src/services/api.ts:522-589](../../frontend/src/services/api.ts#L522)). The audit-prefixed read endpoint is `audit.corrections(...)` at [frontend/src/services/api.ts:944-945](../../frontend/src/services/api.ts#L944).

### Authentication

JWT bearer token required. The handler depends on `_u: CurrentUser` ([app/api/audit.py:46](../../app/api/audit.py#L46)). Same `get_current_user` flow as above ([app/auth.py:172-205](../../app/auth.py#L172)).

### Authorization

JWT-only. No admin gate — `audit.py` does not import or call `require_admin` / `is_admin` / `LEGACY_ADMIN_EMAIL`. No per-session ownership check in code.

### Request Schema

| Parameter | In | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| `session_id` | path | UUID | yes | — | Session whose corrections to list ([app/api/audit.py:46](../../app/api/audit.py#L46)). |
| `limit` | query | int | no | `200` | Clamped to a max of `1000` via `min(limit, 1000)` ([app/api/audit.py:69](../../app/api/audit.py#L69)). |

No request body.

### Response Schema

`200 OK` → `list[dict]`. No Pydantic `response_model`; the per-row shape is hand-built ([app/api/audit.py:71-83](../../app/api/audit.py#L71)):

| Field | Type | Source column / value |
|---|---|---|
| `id` | string | `str(r["id"])`. |
| `t` | string \| null | `applied_at.isoformat()`, or `null` if unset ([app/api/audit.py:74](../../app/api/audit.py#L74)). |
| `type` | (row value) | `correction_type`. |
| `actor` | string | `applied_by` or `""` if null ([app/api/audit.py:76](../../app/api/audit.py#L76)). |
| `seg` | string | `str(segment_id)` or `""` if null ([app/api/audit.py:77](../../app/api/audit.py#L77)). |
| `prior` | (row value) | `old_text`. |
| `next` | (row value) | `new_text`. |
| `note` | null | Hardcoded `None` ([app/api/audit.py:80](../../app/api/audit.py#L80)). |

Selection logic ([app/api/audit.py:55-69](../../app/api/audit.py#L55)):
1. Read `current_pointer` from `ledger_pointers` for the session; default `-1` if no pointer row exists ([app/api/audit.py:55-58](../../app/api/audit.py#L55)).
2. Select from `correction_ledger` where `session_id` matches AND `sequence_number <= :ptr`, ordered `applied_at DESC`, limited ([app/api/audit.py:60-69](../../app/api/audit.py#L60)).

When `current_pointer` is `-1` (no pointer row), `sequence_number <= -1` matches nothing, so the result is `[]`.

### Validation Rules

- `session_id` must be a valid UUID (FastAPI path parsing); otherwise `422`. Bound to SQL as `CAST(:s AS uuid)` ([app/api/audit.py:57](../../app/api/audit.py#L57), [app/api/audit.py:64](../../app/api/audit.py#L64)).
- `limit` is server-clamped to `1000` ([app/api/audit.py:69](../../app/api/audit.py#L69)).
- Redo-tail suppression is enforced by the `sequence_number <= current_pointer` predicate ([app/api/audit.py:66](../../app/api/audit.py#L66)).

### Errors

| Status | Condition | Source |
|---|---|---|
| `401` | Missing/invalid/expired JWT, or user no longer active. | [app/auth.py:181-205](../../app/auth.py#L181) |
| `422` | `session_id` not a valid UUID, or `limit` not an int. | FastAPI parameter validation (framework default). |

No explicit `404` — an unknown session or empty pointer returns `200` with `[]`.

### Example

Request:

```
GET /v1/audit/sessions/3f1c.../corrections?limit=100
Authorization: Bearer <jwt>
```

Response (`200`):

```json
[
  {
    "id": "c1...",
    "t": "2026-06-08T12:00:00+00:00",
    "type": "find_replace",
    "actor": "johndean@vin.com",
    "seg": "b2c3...",
    "prior": "amoxacillin",
    "next": "amoxicillin",
    "note": null
  }
]
```

`type`/`prior`/`next` example values are illustrative; the field set and `note: null` are verified against code.

### Related Screens

- Editor inline audit tab + decision cards: [frontend/src/components/editor/AuditTabInline.vue](../../frontend/src/components/editor/AuditTabInline.vue), [frontend/src/components/editor/DecisionCard.vue](../../frontend/src/components/editor/DecisionCard.vue) (named in the handler docstring at [app/api/audit.py:52](../../app/api/audit.py#L52)). Client accessor `audit.corrections(...)` at [frontend/src/services/api.ts:944-945](../../frontend/src/services/api.ts#L944).

### Related Tables

- `correction_ledger` — the authoritative corrections table read here ([app/api/audit.py:62](../../app/api/audit.py#L62)).
- `ledger_pointers` — provides the per-session undo `current_pointer` ([app/api/audit.py:55-56](../../app/api/audit.py#L55)).

---

## Source Verification
- **Files Used:** app/api/audit.py, app/auth.py, app/security/roles.py, frontend/src/services/api.ts
- **Components Used:** frontend/src/views/AuditView.vue, frontend/src/components/audit/AuditLedger.vue, frontend/src/components/editor/AuditTabInline.vue, frontend/src/components/editor/DecisionCard.vue (AuditTabInline/DecisionCard named in the handler docstring; others inferred from grep — per-component wiring not individually verified)
- **APIs Used:** GET /v1/audit, GET /v1/audit/sessions/{session_id}/corrections
- **Database Tables Used:** audit_events, correction_ledger, ledger_pointers
- **Permission Logic Used:** JWT only (CurrentUser / get_current_user) on both routes. No admin gate — audit.py does not import require_admin/is_admin/LEGACY_ADMIN_EMAIL.
- **Confidence Score:** High — the router is 84 lines and was read in full; both decorators, SQL, and the hand-built response shapes verified directly. Column types of audit_events are owned by the table schema (not asserted here).
- **Evidence Links:** [app/api/audit.py:18](../../app/api/audit.py#L18) (list_events decorator), [app/api/audit.py:45](../../app/api/audit.py#L45) (list_corrections decorator), [app/api/audit.py:20](../../app/api/audit.py#L20) / [app/api/audit.py:46](../../app/api/audit.py#L46) (CurrentUser), [frontend/src/services/api.ts:943](../../frontend/src/services/api.ts#L943) / [frontend/src/services/api.ts:945](../../frontend/src/services/api.ts#L945) (client calls)
