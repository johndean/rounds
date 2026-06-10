# Segments API

Router source: [app/api/segments.py](../../app/api/segments.py)

Backs the editor's segment list and the inline edit / reassign / speaker actions. All routes are mounted under the prefix `/v1/sessions/{session_id}/segments` with tag `segments` ([app/api/segments.py:19](../../app/api/segments.py#L19)).

Three `@router` decorators are defined in this file:

| # | Method | Path | Handler | Decorator line |
|---|--------|------|---------|----------------|
| 1 | GET | `/v1/sessions/{session_id}/segments` | `list_segments` | [segments.py:70](../../app/api/segments.py#L70) |
| 2 | PATCH | `/v1/sessions/{session_id}/segments/{segment_id}` | `edit_segment` | [segments.py:120](../../app/api/segments.py#L120) |
| 3 | POST | `/v1/sessions/{session_id}/segments/{segment_id}/reassign` | `reassign_segment` | [segments.py:224](../../app/api/segments.py#L224) |

## Authentication & authorization (applies to every endpoint below)

- **Authentication:** Every handler depends on `CurrentUser` or its alias `_u` ([segments.py:16](../../app/api/segments.py#L16)). `CurrentUser` resolves to `get_current_user`, which requires a valid HS256 JWT bearer token; a missing or invalid token raises 401 ([app/auth.py:172](../../app/auth.py#L172), [app/auth.py:208](../../app/auth.py#L208)).
- **Authorization:** None of the three handlers contain any `LEGACY_ADMIN_EMAIL` / `require_admin` / role check (verified by grep — no matches). **All three routes are JWT-only.** Any authenticated user may call them. The `User` object exposes only `email` ([app/auth.py:36-38](../../app/auth.py#L36)); there is no role attribute read here.

---

## 1. GET `/v1/sessions/{session_id}/segments`

**Endpoint** [segments.py:70](../../app/api/segments.py#L70)
**Method:** GET
**Purpose:** Return all segments for a session, ordered by `seq`, with the *effective* text resolved through a 3-layer precedence: a user `text_edit` from `correction_ledger` at or below the current ledger pointer → `normalization_results.normalized_text` (optional, migration 012) → raw `segments.text` ([segments.py:77-116](../../app/api/segments.py#L77)).
**Authentication:** JWT required (`_u: CurrentUser`).
**Authorization:** JWT-only. No admin gate.

**Request Schema**
- Path parameter: `session_id: UUID`.
- No request body.

**Response Schema** — `list[SegmentOut]` ([segments.py:22-34](../../app/api/segments.py#L22), `response_model=list[SegmentOut]`):

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | segment id |
| `seq` | int | ordering key |
| `start_ms` | int | start offset in ms |
| `end_ms` | int | end offset in ms |
| `text` | str | effective text after 3-layer resolution |
| `confidence` | float \| null | |
| `flags` | list[str] | |
| `is_anchor` | bool | |
| `anchor_kind` | str \| null | |
| `slide_id` | UUID \| null | |
| `speaker_id` | UUID \| null | |

**Validation Rules**
- No payload validation. The ledger-pointer lookup defaults to `-1` when no `ledger_pointers` row exists ([segments.py:81](../../app/api/segments.py#L81)).
- The `normalization_results` read is wrapped in try/except; a missing table is tolerated and the layer is skipped ([segments.py:96-103](../../app/api/segments.py#L96)).

**Errors**
- 401 — missing/invalid JWT.
- Note: this handler does **not** verify the session exists; an unknown `session_id` returns an empty list rather than 404.

**Example**
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  https://rounds.vin/v1/sessions/<SESSION_ID>/segments
```

**Related Screens:** Editor view (AI / STT / Discrepancies tabs and segment cards). The handler docstring cites `EditorView::activeSegment` click→seek + time→highlight wiring ([segments.py:2-5](../../app/api/segments.py#L2), [segments.py:48-50](../../app/api/segments.py#L48)).
**Related Tables:** `segments`, `correction_ledger`, `ledger_pointers`, `normalization_results` (optional).

---

## 2. PATCH `/v1/sessions/{session_id}/segments/{segment_id}`

**Endpoint** [segments.py:120](../../app/api/segments.py#L120)
**Method:** PATCH
**Purpose:** Inline-edit a single segment: text, slide assignment, speaker assignment, flags, and/or timestamp bounds (`start_ms` / `end_ms`). Writes a row to `corrections` and an `audit_events` row, then commits ([segments.py:202-220](../../app/api/segments.py#L202)).
**Authentication:** JWT required (`user: CurrentUser`); `user.email` is recorded as the actor in both the `corrections` and `audit_events` inserts ([segments.py:208](../../app/api/segments.py#L208), [segments.py:216](../../app/api/segments.py#L216)).
**Authorization:** JWT-only. No admin gate.

**Request Schema** — `SegmentPatch` ([segments.py:37-55](../../app/api/segments.py#L37)). All fields optional:

| Field | Type | Constraint |
|-------|------|-----------|
| `text` | str \| null | |
| `slide_id` | UUID \| null | |
| `speaker_id` | UUID \| null | |
| `flags` | list[str] \| null | stored as jsonb |
| `start_ms` | int \| null | `ge=0` (Pydantic Field) |
| `end_ms` | int \| null | `ge=0` (Pydantic Field) |

Path parameters: `session_id: UUID`, `segment_id: UUID`.

**Response Schema** — `SegmentOut` (same shape as endpoint 1), built from the `RETURNING` row of the UPDATE ([segments.py:177-181](../../app/api/segments.py#L177)).

**Validation Rules**
- **Containment + soft-delete guard:** the prior-state lookup joins `segments` to `sessions` and requires `s.deleted_at IS NULL`. A segment that doesn't belong to the session, or belongs to a soft-deleted session, is treated as not found ([segments.py:133-140](../../app/api/segments.py#L133)). The file notes Rounds has no per-session membership model today (single-tenant operator pool) ([segments.py:126-132](../../app/api/segments.py#L126)).
- **Timestamp validation** (only when `start_ms` and/or `end_ms` supplied): the effective bounds (supplied value, else prior value) must satisfy `start >= 0`, `end >= 0`, and `end > start`. Validated before any write ([segments.py:146-158](../../app/api/segments.py#L146)).
- **Empty patch guard:** if no updatable field is present, returns 400 "No fields to update" ([segments.py:173-174](../../app/api/segments.py#L173)).

**Audit kind selection** — if the only changed fields are `start_ms`/`end_ms` (no text/slide/speaker/flags), the audit kind is `segment.time_edit`; otherwise `segment.edit` ([segments.py:188-200](../../app/api/segments.py#L188)).

**Errors**

| Status | Condition | Detail |
|--------|-----------|--------|
| 401 | missing/invalid JWT | "Could not validate credentials" |
| 404 | segment not found / not in session / session soft-deleted | `"Segment not found"` ([segments.py:139-140](../../app/api/segments.py#L139)) |
| 400 | negative timestamp | `{"code": "INVALID_TIMESTAMP", "message": "start_ms and end_ms must be non-negative"}` ([segments.py:150-153](../../app/api/segments.py#L150)) |
| 400 | `end_ms <= start_ms` | `{"code": "INVALID_TIMESTAMP", "message": "end_ms (...) must be greater than start_ms (...)"}` ([segments.py:155-158](../../app/api/segments.py#L155)) |
| 400 | no fields supplied | `"No fields to update"` ([segments.py:174](../../app/api/segments.py#L174)) |
| 422 | `start_ms`/`end_ms` < 0 in the payload itself | Pydantic `ge=0` rejection before handler runs |

**Example**
```bash
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"corrected words","flags":["reviewed"]}' \
  https://rounds.vin/v1/sessions/<SESSION_ID>/segments/<SEGMENT_ID>
```

**Related Screens:** Editor inline edit / flag actions; SOP timeline / deadline-warning views consume the `segment.time_edit` vs `segment.edit` distinction ([segments.py:42-50](../../app/api/segments.py#L42)).
**Related Tables:** `segments`, `sessions` (join for soft-delete guard), `corrections` (write), `audit_events` (write).

---

## 3. POST `/v1/sessions/{session_id}/segments/{segment_id}/reassign`

**Endpoint** [segments.py:224](../../app/api/segments.py#L224)
**Method:** POST
**Purpose:** Reassign a segment to a different slide. Updates `segments.slide_id`, writes a `slide_reassigned` row to `corrections`, and writes a `segment.reassign` `audit_events` row ([segments.py:233-253](../../app/api/segments.py#L233)).
**Authentication:** JWT required (`user: CurrentUser`); `user.email` recorded as actor ([segments.py:243](../../app/api/segments.py#L243), [segments.py:250](../../app/api/segments.py#L250)).
**Authorization:** JWT-only. No admin gate.

**Request Schema** — `ReassignPayload` ([segments.py:58-59](../../app/api/segments.py#L58)):

| Field | Type | Required |
|-------|------|----------|
| `slide_id` | UUID | yes |

Path parameters: `session_id: UUID`, `segment_id: UUID`.

**Response Schema** — `SegmentOut` (same shape as endpoint 1), from the UPDATE `RETURNING` row ([segments.py:233-237](../../app/api/segments.py#L233)).

**Validation Rules**
- Prior-state lookup requires the segment to belong to the session (`WHERE id = :id AND session_id = :s`) — note this lookup does **not** include the `deleted_at IS NULL` join that endpoint 2 has ([segments.py:227-229](../../app/api/segments.py#L227)).

**Errors**

| Status | Condition | Detail |
|--------|-----------|--------|
| 401 | missing/invalid JWT | "Could not validate credentials" |
| 404 | segment not found / not in session | `"Segment not found"` ([segments.py:230-231](../../app/api/segments.py#L230)) |
| 422 | missing/invalid `slide_id` | Pydantic rejection (required UUID) |

**Example**
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"slide_id":"<SLIDE_UUID>"}' \
  https://rounds.vin/v1/sessions/<SESSION_ID>/segments/<SEGMENT_ID>/reassign
```

**Related Screens:** Editor slide-reassignment action on a segment card.
**Related Tables:** `segments` (update), `corrections` (write), `audit_events` (write).

---

## Source Verification
- **Files Used:** [app/api/segments.py](../../app/api/segments.py), [app/auth.py](../../app/auth.py)
- **Components Used:** none (backend-only; frontend `EditorView` referenced only in code comments, not read)
- **APIs Used:** `GET /v1/sessions/{session_id}/segments`, `PATCH /v1/sessions/{session_id}/segments/{segment_id}`, `POST /v1/sessions/{session_id}/segments/{segment_id}/reassign`
- **Database Tables Used:** `segments`, `sessions`, `correction_ledger`, `ledger_pointers`, `normalization_results` (optional), `corrections`, `audit_events`
- **Permission Logic Used:** JWT presence only (`CurrentUser` → `get_current_user`). No `LEGACY_ADMIN_EMAIL` / `require_admin` gate in this router (grep-confirmed: no matches).
- **Confidence Score:** High — every claim is read directly from the router source and the auth dependency it imports.
- **Evidence Links:** decorators at [segments.py:70](../../app/api/segments.py#L70), [segments.py:120](../../app/api/segments.py#L120), [segments.py:224](../../app/api/segments.py#L224); auth at [app/auth.py:172](../../app/auth.py#L172); schemas at [segments.py:22](../../app/api/segments.py#L22), [segments.py:37](../../app/api/segments.py#L37), [segments.py:58](../../app/api/segments.py#L58).
