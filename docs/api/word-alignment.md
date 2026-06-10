# Word Alignment API

Router for fetching per-Gemini-word STT timing pairs for a session — the backbone for the editor's word-level ("L2") karaoke highlighting on the AI Transcript tab.

- **Source file:** [app/api/word_alignment.py](../../app/api/word_alignment.py)
- **Router prefix:** `/v1/sessions/{session_id}/word-alignment` — declared at [app/api/word_alignment.py:31-34](../../app/api/word_alignment.py#L31)
- **Tag:** `word-alignment`

Per the module docstring ([app/api/word_alignment.py:1-18](../../app/api/word_alignment.py#L1)), rows are written by `lcs_discrepancies_task`; sessions uploaded before migration 036 return no rows (the editor falls through to a legacy whole-text render). This router contains a single endpoint.

---

## GET `/v1/sessions/{session_id}/word-alignment`

- **Endpoint:** `/v1/sessions/{session_id}/word-alignment`
- **Method:** `GET`
- **Decorator:** `@router.get("", response_model=WordAlignmentResponse)` at [app/api/word_alignment.py:54](../../app/api/word_alignment.py#L54)
- **Handler:** `get_word_alignment` at [app/api/word_alignment.py:55](../../app/api/word_alignment.py#L55)

### Purpose

Return every Gemini word's alignment row for the session, grouped by `segment_id`. The frontend stores the result as `Map<segment_id, AlignmentEntry[]>` and looks up by index when rendering; the `g` field equals the 0-based index into `seg.text.split()` ([app/api/word_alignment.py:60-67](../../app/api/word_alignment.py#L60)).

### Authentication

JWT bearer token required. The handler depends on `_u: CurrentUser` ([app/api/word_alignment.py:58](../../app/api/word_alignment.py#L58)). `CurrentUser` is `Annotated[User, Depends(get_current_user)]` ([app/auth.py:208](../../app/auth.py#L208)); `get_current_user` decodes the HS256 JWT and verifies the user is still active, raising `401` on a missing/invalid token ([app/auth.py:172-205](../../app/auth.py#L172)).

### Authorization

JWT-only. There is no admin gate — `word_alignment.py` does not import or call `require_admin` / `is_admin` / `LEGACY_ADMIN_EMAIL`. Any authenticated user can call it. No ownership/session-membership check is performed in code.

### Request Schema

| Parameter | In | Type | Required | Notes |
|---|---|---|---|---|
| `session_id` | path | UUID | yes | Session whose alignment rows to fetch ([app/api/word_alignment.py:56](../../app/api/word_alignment.py#L56)). |

No query parameters. No request body.

### Response Schema

`200 OK` → `WordAlignmentResponse` ([app/api/word_alignment.py:47-51](../../app/api/word_alignment.py#L47)):

| Field | Type | Notes |
|---|---|---|
| `session_id` | UUID | Echoes the path param. |
| `count` | int | Total alignment rows (matched + unmatched) ([app/api/word_alignment.py:98](../../app/api/word_alignment.py#L98)). |
| `matched` | int | Count of rows with non-null `stt_start_ms` ([app/api/word_alignment.py:92-93](../../app/api/word_alignment.py#L92)). |
| `segments` | `dict[str, AlignmentEntry[]]` | Keyed by `segment_id` (text); value is the ordered list of that segment's entries ([app/api/word_alignment.py:82-94](../../app/api/word_alignment.py#L82)). |

`AlignmentEntry` — intentionally short field names to keep the payload compact ([app/api/word_alignment.py:37-44](../../app/api/word_alignment.py#L37)):

| Field | Type | Meaning |
|---|---|---|
| `g` | int | `gemini_idx` — 0-based position in `seg.text.split()`. |
| `s` | int \| null | `stt_start_ms` — `null` when `match_kind = 'unmatched'`. |
| `e` | int \| null | `stt_end_ms` — `null` when `match_kind = 'unmatched'`. |
| `k` | string | `match_kind`: `'exact'` \| `'unmatched'`. |

Rows are read from `word_alignment` joined to `segments` and filtered by `s.session_id`, ordered `wa.segment_id, wa.gemini_idx` ([app/api/word_alignment.py:68-80](../../app/api/word_alignment.py#L68)).

The frontend client mirrors these shapes as `WordAlignmentEntry` / `WordAlignmentResponse` at [frontend/src/services/api.ts:290-302](../../frontend/src/services/api.ts#L290).

### Validation Rules

- `session_id` is coerced to a UUID by FastAPI path parsing; a non-UUID path segment yields `422`.
- The query filters on the joined `segments.session_id = CAST(:sid AS uuid)` ([app/api/word_alignment.py:77](../../app/api/word_alignment.py#L77)) — alignment rows for segments belonging to other sessions are excluded by the JOIN.
- The `g` value preserves the 0-based split index invariant; the frontend must split on `seg.text.split()` with no trim/normalize to keep alignment ([app/api/word_alignment.py:63-67](../../app/api/word_alignment.py#L63)).

### Errors

| Status | Condition | Source |
|---|---|---|
| `401` | Missing/invalid/expired JWT, or user no longer active. | [app/auth.py:181-205](../../app/auth.py#L181) |
| `422` | `session_id` not a valid UUID. | FastAPI parameter validation (framework default). |

No explicit `404` is raised: an unknown but well-formed `session_id` (or a pre-migration-036 session) returns `200` with `count: 0`, `matched: 0`, and an empty `segments` object.

### Example

Request:

```
GET /v1/sessions/3f1c.../word-alignment
Authorization: Bearer <jwt>
```

Response (`200`):

```json
{
  "session_id": "3f1c0d9e-...",
  "count": 3,
  "matched": 2,
  "segments": {
    "b2c3d4e5-...": [
      { "g": 0, "s": 1200, "e": 1480, "k": "exact" },
      { "g": 1, "s": 1480, "e": 1900, "k": "exact" },
      { "g": 2, "s": null, "e": null, "k": "unmatched" }
    ]
  }
}
```

Example response values are illustrative; field names/types are verified against code.

### Related Screens

- Editor word-level highlighting consumers: [frontend/src/components/editor/SegmentText.vue](../../frontend/src/components/editor/SegmentText.vue), [frontend/src/components/editor/TranscriptPane.vue](../../frontend/src/components/editor/TranscriptPane.vue), [frontend/src/views/EditorView.vue](../../frontend/src/views/EditorView.vue). Client accessor `wordAlignment.get(...)` at [frontend/src/services/api.ts:304-307](../../frontend/src/services/api.ts#L304). (These components appear in a grep for `word-alignment`/`word_alignment`; exact call-site wiring for each not individually verified — PARTIALLY IMPLEMENTED verification.)

### Related Tables

- `word_alignment` — the per-word alignment rows ([app/api/word_alignment.py:75](../../app/api/word_alignment.py#L75)).
- `segments` — joined to scope alignment rows to the requested session ([app/api/word_alignment.py:76-77](../../app/api/word_alignment.py#L76)).

---

## Source Verification
- **Files Used:** app/api/word_alignment.py, app/auth.py, app/security/roles.py, frontend/src/services/api.ts
- **Components Used:** frontend/src/components/editor/SegmentText.vue, frontend/src/components/editor/TranscriptPane.vue, frontend/src/views/EditorView.vue (consumption inferred from grep; per-component wiring not individually verified)
- **APIs Used:** GET /v1/sessions/{session_id}/word-alignment
- **Database Tables Used:** word_alignment, segments
- **Permission Logic Used:** JWT only (CurrentUser / get_current_user). No admin gate — word_alignment.py does not import require_admin/is_admin/LEGACY_ADMIN_EMAIL.
- **Confidence Score:** High — the router is 102 lines and was read in full; SQL, response shape, and auth dependency verified directly.
- **Evidence Links:** [app/api/word_alignment.py:54](../../app/api/word_alignment.py#L54) (decorator), [app/api/word_alignment.py:58](../../app/api/word_alignment.py#L58) (CurrentUser), [app/api/word_alignment.py:68-80](../../app/api/word_alignment.py#L68) (SQL), [frontend/src/services/api.ts:306](../../frontend/src/services/api.ts#L306) (client call)
