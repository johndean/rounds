# Discrepancies API

Router for listing LCS-detected diffs between the AI-normalized transcript text and the raw STT text for a session, classified as meaningful vs. noise.

- **Source file:** [app/api/discrepancies.py](../../app/api/discrepancies.py)
- **Router prefix:** `/v1/sessions/{session_id}/discrepancies` — declared at [app/api/discrepancies.py:26](../../app/api/discrepancies.py#L26)
- **Tag:** `discrepancies`

This router reads from the `transcription_discrepancies` table (written by `lcs_discrepancies_task` and updated by `classify_task`, per the module docstring at [app/api/discrepancies.py:1-13](../../app/api/discrepancies.py#L1)). It contains a single endpoint.

---

## GET `/v1/sessions/{session_id}/discrepancies`

- **Endpoint:** `/v1/sessions/{session_id}/discrepancies`
- **Method:** `GET`
- **Decorator:** `@router.get("", response_model=DiscrepancyListResponse)` at [app/api/discrepancies.py:49](../../app/api/discrepancies.py#L49)
- **Handler:** `list_discrepancies` at [app/api/discrepancies.py:50](../../app/api/discrepancies.py#L50)

### Purpose

Return all per-segment LCS diffs for a session. Each row carries the AI fragment (`ai_text`), the raw STT fragment (`stt_text`), the classifier's category + meaningful flag, and a `segment_id` so the editor can anchor a side-by-side AI ↔ STT render to a specific segment. See the handler docstring at [app/api/discrepancies.py:57-65](../../app/api/discrepancies.py#L57).

### Authentication

JWT bearer token required. The handler depends on `_u: CurrentUser` ([app/api/discrepancies.py:53](../../app/api/discrepancies.py#L53)). `CurrentUser` is `Annotated[User, Depends(get_current_user)]` ([app/auth.py:208](../../app/auth.py#L208)); `get_current_user` decodes the HS256 JWT and verifies the user is still active, raising `401 Could not validate credentials` on a missing/invalid token ([app/auth.py:172-205](../../app/auth.py#L172)).

### Authorization

JWT-only. There is no admin gate on this endpoint — `discrepancies.py` does not import or call `require_admin` / `is_admin` / `LEGACY_ADMIN_EMAIL`. Any authenticated user can call it. (No ownership/session-membership check is performed in code either.)

### Request Schema

| Parameter | In | Type | Required | Default | Notes |
|---|---|---|---|---|---|
| `session_id` | path | UUID | yes | — | Session whose discrepancies to list ([app/api/discrepancies.py:51](../../app/api/discrepancies.py#L51)). |
| `category` | query | string (optional) | no | `None` | Filters `category = :cat` ([app/api/discrepancies.py:67-68](../../app/api/discrepancies.py#L67)). Docstring lists allowed values: `medication`, `terminology`, `filler`, `punctuation`, `drift`, `low_confidence`, `other` ([app/api/discrepancies.py:59](../../app/api/discrepancies.py#L59)). NOT VERIFIED IN CODE: this enum is not enforced server-side — any string is accepted and used in the WHERE clause. |
| `meaningful_only` | query | bool | no | `false` | When `true`, appends `is_meaningful = TRUE` to the WHERE clause, excluding noise rows ([app/api/discrepancies.py:69-70](../../app/api/discrepancies.py#L69)). |

No request body.

### Response Schema

`200 OK` → `DiscrepancyListResponse` ([app/api/discrepancies.py:41-46](../../app/api/discrepancies.py#L41)):

| Field | Type | Notes |
|---|---|---|
| `session_id` | UUID | Echoes the path param. |
| `count` | int | Total rows returned. |
| `classified_count` | int | Count of rows where `is_meaningful is not None` ([app/api/discrepancies.py:95](../../app/api/discrepancies.py#L95)). |
| `classification_status` | string | `'complete'` \| `'partial'` \| `'pending'`. Derivation below. |
| `discrepancies` | `DiscrepancyOut[]` | See nested shape. |

`classification_status` derivation ([app/api/discrepancies.py:96-103](../../app/api/discrepancies.py#L96)):
- `total == 0` → `complete`
- `classified == total` → `complete`
- `classified > 0` → `partial`
- otherwise → `pending`

`DiscrepancyOut` ([app/api/discrepancies.py:29-38](../../app/api/discrepancies.py#L29)):

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Discrepancy row id. |
| `segment_id` | UUID \| null | Segment the diff anchors to. |
| `ai_text` | string \| null | AI-normalized fragment. |
| `stt_text` | string \| null | Raw STT fragment. |
| `category` | string \| null | Classifier category. |
| `is_meaningful` | bool \| null | `null` until the classify task runs. |
| `classifier_model` | string \| null | Model that produced the classification. |
| `classified_at` | string \| null | ISO-8601 timestamp; `None` when unset ([app/api/discrepancies.py:89](../../app/api/discrepancies.py#L89)). |
| `created_at` | string \| null | ISO-8601 timestamp; `None` when unset ([app/api/discrepancies.py:90](../../app/api/discrepancies.py#L90)). |

Rows are ordered `created_at ASC` ([app/api/discrepancies.py:77](../../app/api/discrepancies.py#L77)).

The frontend client mirrors these shapes as `DiscrepancyRow` / `DiscrepancyListResponse` at [frontend/src/services/api.ts:241-259](../../frontend/src/services/api.ts#L241).

### Validation Rules

- `session_id` is coerced to a UUID by FastAPI path parsing; a non-UUID path segment yields `422`.
- `meaningful_only` is parsed as a bool by FastAPI; a non-bool query value yields `422`.
- `category` accepts any string (no server-side enum enforcement) — see request table note.
- The session-scope predicate is `session_id = CAST(:s AS uuid)` ([app/api/discrepancies.py:66](../../app/api/discrepancies.py#L66)).

### Errors

| Status | Condition | Source |
|---|---|---|
| `401` | Missing/invalid/expired JWT, or user no longer active. | [app/auth.py:181-205](../../app/auth.py#L181) |
| `422` | `session_id` not a valid UUID, or `meaningful_only` not a valid bool. | FastAPI parameter validation (framework default). |

No explicit `404` is raised: an unknown but well-formed `session_id` returns `200` with `count: 0` and `classification_status: "complete"` (the `total == 0` branch at [app/api/discrepancies.py:96-97](../../app/api/discrepancies.py#L96)).

### Example

Request:

```
GET /v1/sessions/3f1c.../discrepancies?meaningful_only=true&category=medication
Authorization: Bearer <jwt>
```

Response (`200`):

```json
{
  "session_id": "3f1c0d9e-...",
  "count": 2,
  "classified_count": 2,
  "classification_status": "complete",
  "discrepancies": [
    {
      "id": "a1...",
      "segment_id": "b2...",
      "ai_text": "amoxicillin 500 mg",
      "stt_text": "a mox a sillin 500 mg",
      "category": "medication",
      "is_meaningful": true,
      "classifier_model": "gemini-...",
      "classified_at": "2026-06-08T12:00:00+00:00",
      "created_at": "2026-06-08T11:59:00+00:00"
    }
  ]
}
```

Example response values are illustrative; exact field types/keys are verified against code.

### Related Screens

- Discrepancies pane in the editor: [frontend/src/components/editor/DiscrepanciesPane.vue](../../frontend/src/components/editor/DiscrepanciesPane.vue). Client accessor `discrepancies.list(...)` at [frontend/src/services/api.ts:261-266](../../frontend/src/services/api.ts#L261).
- Discrepancy settings section: [frontend/src/components/settings/SectionDiscrepancy.vue](../../frontend/src/components/settings/SectionDiscrepancy.vue). (Relationship inferred from filename/grep — NOT VERIFIED IN CODE that it calls this endpoint.)

### Related Tables

- `transcription_discrepancies` — the table this endpoint reads ([app/api/discrepancies.py:75](../../app/api/discrepancies.py#L75)).

---

## Source Verification
- **Files Used:** app/api/discrepancies.py, app/auth.py, app/security/roles.py, frontend/src/services/api.ts
- **Components Used:** frontend/src/components/editor/DiscrepanciesPane.vue, frontend/src/components/settings/SectionDiscrepancy.vue (settings relationship not verified)
- **APIs Used:** GET /v1/sessions/{session_id}/discrepancies
- **Database Tables Used:** transcription_discrepancies
- **Permission Logic Used:** JWT only (CurrentUser / get_current_user). No admin gate — discrepancies.py does not import require_admin/is_admin/LEGACY_ADMIN_EMAIL.
- **Confidence Score:** High — the entire router is 112 lines and was read in full; auth dependency and absence of admin gate verified directly.
- **Evidence Links:** [app/api/discrepancies.py:49](../../app/api/discrepancies.py#L49) (decorator), [app/api/discrepancies.py:53](../../app/api/discrepancies.py#L53) (CurrentUser), [app/auth.py:208](../../app/auth.py#L208) (CurrentUser def), [frontend/src/services/api.ts:264](../../frontend/src/services/api.ts#L264) (client call)
