# API Reference — Add To Session (`/v1/sessions/{session_id}/...`)

File management for an already-created session: detect which sidecar files are missing, mint a staging signed-URL, and add slides / chat / manifest files (either by multipart upload or by referencing a previously-uploaded staging `gcs_uri`). Uploads land in a session-scoped staging prefix `gs://<bucket>/sessions/{id}/staging/phase6/<uuid>/<filename>` ([app/api/add_to_session.py:92](../../app/api/add_to_session.py#L92)).

- **Source file:** [`app/api/add_to_session.py`](../../app/api/add_to_session.py)
- **Router prefix / tag:** `/v1/sessions`, tag `add-to-session` — [app/api/add_to_session.py:50](../../app/api/add_to_session.py#L50)
- **Mounted in:** [app/main.py:216](../../app/main.py#L216) (`app.include_router(add_to_session_router.router)`)
- **Endpoints found:** 5 (`GET /{id}/missing`, `POST /{id}/add/signed-url`, `POST /{id}/add/slides`, `POST /{id}/add/chat`, `POST /{id}/add/manifest`)

## Authentication & Authorization (router-wide)

Every handler takes `_u: CurrentUser`, so **a valid JWT bearer token is required** on all five routes — `CurrentUser = Annotated[User, Depends(get_current_user)]` ([app/auth.py:208](../../app/auth.py#L208)).

**Authorization is JWT-only.** No `LEGACY_ADMIN_EMAIL`, `require_admin`, `is_admin`, or `johndean@vin.com` gate exists in this router — verified by grep over [app/api/add_to_session.py](../../app/api/add_to_session.py) (no matches). The module docstring calls these "admin file management" routes ([app/api/add_to_session.py:2](../../app/api/add_to_session.py#L2)), but **no code enforces an admin role** — any authenticated user may call them. (Role tiers are scaffold-only; not enforced here — IMPLEMENTATION NOT FOUND for a role check on these routes.)

Every endpoint first calls `_require_session(db, session_id)` ([app/api/add_to_session.py:167](../../app/api/add_to_session.py#L167)), which loads the session (`deleted_at IS NULL`) and raises `NotFoundError` if absent.

### Shared upload intake (`_intake_upload`)
All three `add/*` endpoints share `_intake_upload` ([app/api/add_to_session.py:279](../../app/api/add_to_session.py#L279)). It accepts **either** a multipart file **or** a JSON body `{gcs_uri}`:
- **Multipart path:** reads the file, validates MIME, uploads to a fresh staging blob, returns `(gcs_uri, mime_type, filename, size_bytes)`.
- **`{gcs_uri}` path:** the URI must be inside the session's Phase-6 staging scope (`_is_phase6_staging_uri`, [:97](../../app/api/add_to_session.py#L97)), else `ValidationFailedError`; then it `reload()`s the blob to read content-type/size/filename (404 if the blob is gone).

MIME guards used across intake:
- `_reject_primary_av` ([:179](../../app/api/add_to_session.py#L179)) — rejects primary A/V MIME types (must go through `/upload`), `ValidationFailedError`.
- `_reject_bad_type_mime` ([:186](../../app/api/add_to_session.py#L186)) — for `type=slides`, requires PDF or PPTX.

Signed URL TTL is `_SIGNED_URL_TTL_SECONDS = 3600` ([:69](../../app/api/add_to_session.py#L69)) (BR-013).

---

## `GET /v1/sessions/{session_id}/missing`

- **Decorator:** `@router.get("/{session_id}/missing")` — [app/api/add_to_session.py:228](../../app/api/add_to_session.py#L228)
- **Handler:** `get_missing(session_id, db, _u)` — [:229](../../app/api/add_to_session.py#L229)

### Purpose
Returns per-type presence booleans for a session's sidecar inputs (slides / chat / manifest / bios), so the UI can show which files are still missing.

### Authentication / Authorization
JWT required; JWT-only (no admin gate).

### Request Schema
Path param `session_id: str`. No body.

### Response Schema
Plain `dict` (envelope `data`), computed by `_compute_missing` ([:194](../../app/api/add_to_session.py#L194)):

| Field | Type | Derived from |
|---|---|---|
| `has_slides` | `bool` | `count(*) > 0` in `slides` |
| `has_chat` | `bool` | `count(*) > 0` in `chat_messages` |
| `has_manifest` | `bool` | `sessions.title_long` is non-empty |
| `has_bios` | `bool` | `session_speakers` rows with non-empty `bio` |

### Validation Rules
Session must exist (`deleted_at IS NULL`).

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| Session not found | `NOT_FOUND` / 404 | [:231](../../app/api/add_to_session.py#L231) |

### Example
`GET /v1/sessions/3f...uuid/missing` → `data`: `{ "has_slides": true, "has_chat": false, "has_manifest": true, "has_bios": false }`

### Related Screens
- `api.ts` `missing(id)` ([frontend/src/services/api.ts:186](../../frontend/src/services/api.ts#L186)); surfaced via the Add-file flow (`AddFileModal.vue`, `SessionDetailView.vue`).

### Related Tables
`slides`, `chat_messages`, `sessions`, `session_speakers` (all read-only).

---

## `POST /v1/sessions/{session_id}/add/signed-url`

- **Decorator:** `@router.post("/{session_id}/add/signed-url")` — [app/api/add_to_session.py:237](../../app/api/add_to_session.py#L237)
- **Handler:** `add_signed_url(session_id, request, db, _u)` — [:238](../../app/api/add_to_session.py#L238)

### Purpose
Mints a v4 PUT signed URL into the session's Phase-6 staging prefix for a browser-side upload of a slides/chat/manifest file.

### Authentication / Authorization
JWT required; JWT-only.

### Request Schema
Raw JSON body (parsed via `request.json()`):

| Field | Type | Required | Notes |
|---|---|---|---|
| `filename` | `str` | yes | required, else `InvalidInputError` ([:253](../../app/api/add_to_session.py#L253)) |
| `type` | `str` | yes | must be one of `slides`, `chat`, `manifest` ([:254](../../app/api/add_to_session.py#L254)) |
| `mime_type` | `str` | no | defaults to `application/octet-stream` ([:249](../../app/api/add_to_session.py#L249)) |

### Response Schema
Plain `dict` (envelope `data`) — [:268](../../app/api/add_to_session.py#L268):

| Field | Type | Notes |
|---|---|---|
| `signed_url` | `str` | v4 PUT URL |
| `gcs_uri` | `str` | `gs://<bucket>/sessions/{id}/staging/phase6/<uuid>/<filename>` |
| `blob_name` | `str` | object name |
| `mime_type` | `str` | echoes / defaulted |
| `expires_in` | `int` | `3600` |

### Validation Rules
- Body must be JSON (`InvalidInputError` otherwise, [:246](../../app/api/add_to_session.py#L246)).
- `filename` required; `type` must be a known key.
- `_reject_primary_av` and (for `slides`) `_reject_bad_type_mime` on `mime_type` ([:257](../../app/api/add_to_session.py#L257)).

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| Session not found | `NOT_FOUND` / 404 | [:242](../../app/api/add_to_session.py#L242) |
| Body not JSON / missing `filename` / bad `type` | `INVALID_INPUT` / 400 | [:246](../../app/api/add_to_session.py#L246)–[:255](../../app/api/add_to_session.py#L255) |
| Primary A/V MIME or non-PDF/PPTX slides | `VALIDATION_FAILED` / 400 | [:259](../../app/api/add_to_session.py#L259) |
| GCS sign failure | `INTERNAL_ERROR` / 500 | [:266](../../app/api/add_to_session.py#L266) |

### Example
```http
POST /v1/sessions/3f...uuid/add/signed-url
Authorization: Bearer <jwt>
{ "filename": "deck.pdf", "type": "slides", "mime_type": "application/pdf" }
```

### Related Screens
- `AddFileModal.vue` ([frontend/src/components/session/AddFileModal.vue:154](../../frontend/src/components/session/AddFileModal.vue#L154)); `api.ts` `addSignedUrl` ([frontend/src/services/api.ts:190](../../frontend/src/services/api.ts#L190)).

### Related Tables
None (signing only; nothing persisted).

---

## `POST /v1/sessions/{session_id}/add/slides`

- **Decorator:** `@router.post("/{session_id}/add/slides")` — [app/api/add_to_session.py:450](../../app/api/add_to_session.py#L450)
- **Handler:** `add_slides(session_id, request, db, _u, slide_file=File(), mode=Query())` — [:451](../../app/api/add_to_session.py#L451)

### Purpose
Adds a slide deck (PDF/PPTX) to a session via multipart `slide_file` or JSON `{gcs_uri}`. Detects existing decks and, on conflict, returns thumbnails + page metadata so the UI can prompt for a resolution mode. On success it inserts a `sources` row and dispatches `slide_extract_task`.

### Authentication / Authorization
JWT required; JWT-only.

### Request Schema
- Path: `session_id`.
- Query: `mode` (`str | null`) — one of `replace`, `append`, `replace_selected` (or omitted).
- Body: multipart `slide_file` **OR** JSON `{gcs_uri}` (via `_intake_upload`). For `mode=replace_selected`, an additional JSON body `{slide_numbers: [int, ...]}` (≥1 positive int) is required ([:489](../../app/api/add_to_session.py#L489)).

### Response Schema
Plain `dict` (envelope `data`) — [:546](../../app/api/add_to_session.py#L546):

| Field | Type | Notes |
|---|---|---|
| `source_id` | `str \| null` | new `sources.id`, or null if `ON CONFLICT` skipped |
| `gcs_uri` | `str` | staging URI used |
| `mode` | `str` | given `mode`, else `append` (if decks exist) or `first-add` |
| `dispatched_task` | `str` | `"slide_extract_task"` |
| `new_deck_pages` | `int \| null` | PDF page count (PDF only) |
| `selected_slide_numbers` | `list[int] \| null` | only when `mode=replace_selected` |

### Validation Rules
- `_intake_upload` MIME guards (PDF/PPTX only for slides).
- **Conflict gate:** if existing decks are present and `mode` is not one of `replace`/`append`/`replace_selected`, raises `ConflictError` with thumbnails (`current_pages`, `new_pages`), `existing_decks`, `new_deck_pages`, `new_deck_filename`/`new_filename`, `gcs_uri` ([:472](../../app/api/add_to_session.py#L472)).
- `replace_selected`: `slide_numbers` must be a non-empty list of positive ints ([:495](../../app/api/add_to_session.py#L495)); numbers exceeding `new_deck_pages` → `ValidationFailedError` ([:508](../../app/api/add_to_session.py#L508)).

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| Session not found | `NOT_FOUND` / 404 | [:459](../../app/api/add_to_session.py#L459) |
| `gcs_uri` outside staging scope | `VALIDATION_FAILED` / 400 | [:311](../../app/api/add_to_session.py#L311) |
| Staging blob missing | `NOT_FOUND` / 404 | [:325](../../app/api/add_to_session.py#L325) / [:328](../../app/api/add_to_session.py#L328) |
| Existing decks + no resolution mode | `CONFLICT` / 409 (with thumbnail details) | [:472](../../app/api/add_to_session.py#L472) |
| `replace_selected` bad/empty `slide_numbers` | `INVALID_INPUT` / 400 | [:496](../../app/api/add_to_session.py#L496) |
| `slide_numbers` exceed deck pages | `VALIDATION_FAILED` / 400 | [:508](../../app/api/add_to_session.py#L508) |
| GCS upload failure | `INTERNAL_ERROR` / 500 | [:299](../../app/api/add_to_session.py#L299) |
| Source committed but task dispatch failed | `INTERNAL_ERROR` / 500 | [:544](../../app/api/add_to_session.py#L544) |

### Example
```http
POST /v1/sessions/3f...uuid/add/slides?mode=replace
Authorization: Bearer <jwt>
{ "gcs_uri": "gs://video-pipeline-uploads-mic/sessions/3f...uuid/staging/phase6/<uuid>/deck.pdf" }
```

### Related Screens
- `AddFileModal.vue`; `api.ts` `addSlides(id, body, mode)` ([frontend/src/services/api.ts:194](../../frontend/src/services/api.ts#L194)).

### Related Tables
`slides` (DELETE on `replace` / `replace_selected`), `sources` (INSERT `role='slide'`, [:524](../../app/api/add_to_session.py#L524)). Reads `sources` for existing-deck detection.

---

## `POST /v1/sessions/{session_id}/add/chat`

- **Decorator:** `@router.post("/{session_id}/add/chat")` — [app/api/add_to_session.py:597](../../app/api/add_to_session.py#L597)
- **Handler:** `add_chat(session_id, request, db, _u, chat_file=File(), confirm=Query(), start_time=Query())` — [:598](../../app/api/add_to_session.py#L598)

### Purpose
Adds a chat transcript to a session via multipart `chat_file` or JSON `{gcs_uri}`. If chat already exists, returns previews and requires `?confirm=true` to replace. On confirm it deletes existing `chat_messages`, parses the file, inserts new messages, and records a `sources` row. **Replace-only** (always `DELETE` then re-insert).

### Authentication / Authorization
JWT required; JWT-only.

### Request Schema
- Path: `session_id`.
- Query: `confirm` (`bool | null`), `start_time` (`str | null`, parser override).
- Body: multipart `chat_file` **OR** JSON `{gcs_uri}`.

### Response Schema
Plain `dict` (envelope `data`) — [:674](../../app/api/add_to_session.py#L674):

| Field | Type | Notes |
|---|---|---|
| `messages_written` | `int` | parsed message count inserted |
| `replaced_existing` | `int` | count of prior chat messages deleted |
| `gcs_uri` | `str` | staging URI used |

### Validation Rules
- `_intake_upload` MIME guards (`_CHAT_MIMES`: `text/plain`, `text/csv`, `application/octet-stream`).
- **Conflict gate:** if `existing_cnt > 0` and `confirm` is falsy → `ConflictError` with `existing_count`, `new_count`, `current_preview` (≤10), `new_preview` (≤10), `gcs_uri`, `new_filename` ([:622](../../app/api/add_to_session.py#L622)).
- Chat file must be readable from GCS (`NotFoundError` otherwise, [:636](../../app/api/add_to_session.py#L636)).
- `parse_chat_file` failure → `ValidationFailedError` ([:643](../../app/api/add_to_session.py#L643)).

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| Session not found | `NOT_FOUND` / 404 | [:607](../../app/api/add_to_session.py#L607) |
| `gcs_uri` outside staging scope | `VALIDATION_FAILED` / 400 | [:311](../../app/api/add_to_session.py#L311) |
| Existing chat + no `confirm` | `CONFLICT` / 409 (with previews) | [:622](../../app/api/add_to_session.py#L622) |
| Chat file unreadable | `NOT_FOUND` / 404 | [:636](../../app/api/add_to_session.py#L636) |
| Parse failure | `VALIDATION_FAILED` / 400 | [:643](../../app/api/add_to_session.py#L643) |

### Example
```http
POST /v1/sessions/3f...uuid/add/chat?confirm=true
Authorization: Bearer <jwt>
{ "gcs_uri": "gs://.../sessions/3f...uuid/staging/phase6/<uuid>/chat.txt" }
```

### Related Screens
- `AddFileModal.vue` (posts `add/chat?confirm=true`, [frontend/src/components/session/AddFileModal.vue:262](../../frontend/src/components/session/AddFileModal.vue#L262)); `api.ts` `addChat` ([frontend/src/services/api.ts:200](../../frontend/src/services/api.ts#L200)).

### Related Tables
`chat_messages` (DELETE all for session, then INSERT each parsed message, [:645](../../app/api/add_to_session.py#L645)/[:650](../../app/api/add_to_session.py#L650)), `sources` (INSERT `role='chat'`, [:663](../../app/api/add_to_session.py#L663)).

---

## `POST /v1/sessions/{session_id}/add/manifest`

- **Decorator:** `@router.post("/{session_id}/add/manifest")` — [app/api/add_to_session.py:711](../../app/api/add_to_session.py#L711)
- **Handler:** `add_manifest(session_id, request, db, _u, manifest_file=File(), mode=Query())` — [:712](../../app/api/add_to_session.py#L712)

### Purpose
Adds/replaces a session manifest (extras2.txt) via multipart `manifest_file` or JSON `{gcs_uri}`. Parses it with `parse_extras2`, and if a manifest already exists requires an explicit `mode`. On `use_new` it clears existing speakers/resources and updates session metadata; on `keep_current` it deletes the staged file and no-ops.

### Authentication / Authorization
JWT required; JWT-only.

### Request Schema
- Path: `session_id`.
- Query: `mode` (`str | null`) — `use_new` or `keep_current` when a manifest already exists.
- Body: multipart `manifest_file` **OR** JSON `{gcs_uri}`. (`_MANIFEST_MIMES`: `text/plain`, `application/octet-stream`.)

### Response Schema
Plain `dict` (envelope `data`). Two shapes:
- `keep_current` ([:753](../../app/api/add_to_session.py#L753)): `{ "session_updated": false, "mode": "keep_current" }`
- otherwise ([:818](../../app/api/add_to_session.py#L818)):

| Field | Type | Notes |
|---|---|---|
| `session_updated` | `bool` | `true` |
| `mode` | `str` | given `mode`, else `first-add` |
| `fields_updated` | `list[str]` | column names updated on `sessions` |
| `speakers_written` | `int` | rows inserted into `session_speakers` |
| `resources_written` | `int` | rows inserted into `session_slide_resources` |

Parsed fields come from `ParsedManifest` ([app/services/extras2_parser.py:40](../../app/services/extras2_parser.py#L40)): `code`, `title_long`, `title_short`, `ce_broker_id`, `class_id`, `tags`, `publishing_links`, `polls`/`polls_parsed`, `speakers`, `slide_resources`.

### Validation Rules
- Manifest file must be readable from GCS (`NotFoundError` otherwise, [:728](../../app/api/add_to_session.py#L728)).
- `parse_extras2` failure → `ValidationFailedError` ([:736](../../app/api/add_to_session.py#L736)).
- **Conflict gate:** if the session already has a manifest (`sess.title_long` truthy) and `mode` is not `use_new`/`keep_current` → `ConflictError` with `current_summary`, `new_summary`, `gcs_uri`, `new_filename` ([:741](../../app/api/add_to_session.py#L741)).

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| Session not found | `NOT_FOUND` / 404 | [:722](../../app/api/add_to_session.py#L722) |
| `gcs_uri` outside staging scope | `VALIDATION_FAILED` / 400 | [:311](../../app/api/add_to_session.py#L311) |
| Manifest file unreadable | `NOT_FOUND` / 404 | [:729](../../app/api/add_to_session.py#L729) |
| Parse failure | `VALIDATION_FAILED` / 400 | [:736](../../app/api/add_to_session.py#L736) |
| Existing manifest + no `mode` | `CONFLICT` / 409 (summaries) | [:741](../../app/api/add_to_session.py#L741) |

### Example
```http
POST /v1/sessions/3f...uuid/add/manifest?mode=use_new
Authorization: Bearer <jwt>
{ "gcs_uri": "gs://.../sessions/3f...uuid/staging/phase6/<uuid>/extras2.txt" }
```

### Related Screens
- `AddFileModal.vue`; `api.ts` `addManifest(id, body, mode)` ([frontend/src/services/api.ts:203](../../frontend/src/services/api.ts#L203)).

### Related Tables
`sessions` (UPDATE metadata columns, [:778](../../app/api/add_to_session.py#L778)), `session_slide_resources` (DELETE on `use_new` + INSERT, [:757](../../app/api/add_to_session.py#L757)/[:797](../../app/api/add_to_session.py#L797)), `session_speakers` (DELETE on `use_new` + INSERT, [:760](../../app/api/add_to_session.py#L760)/[:785](../../app/api/add_to_session.py#L785)), `sources` (INSERT `role='manifest'`, [:807](../../app/api/add_to_session.py#L807)).

---

## Source Verification
- **Files Used:** [app/api/add_to_session.py](../../app/api/add_to_session.py), [app/auth.py](../../app/auth.py), [app/middleware/envelope.py](../../app/middleware/envelope.py), [app/services/gcs.py](../../app/services/gcs.py), [app/services/extras2_parser.py](../../app/services/extras2_parser.py), [app/main.py](../../app/main.py), frontend/src/services/api.ts, frontend/src/components/session/AddFileModal.vue
- **Components Used:** AddFileModal.vue, SessionDetailView.vue
- **APIs Used:** `GET /v1/sessions/{id}/missing`, `POST /v1/sessions/{id}/add/signed-url`, `POST /v1/sessions/{id}/add/slides`, `POST /v1/sessions/{id}/add/chat`, `POST /v1/sessions/{id}/add/manifest`
- **Database Tables Used:** sessions, slides, chat_messages, session_speakers, session_slide_resources, sources
- **Permission Logic Used:** JWT presence only (`CurrentUser` → `get_current_user`). No admin/role gate present despite the "admin file management" docstring.
- **Confidence Score:** High — all 5 decorators, the shared `_intake_upload` paths, conflict/validation branches, and error classes were read directly; router mount confirmed in main.py.
- **Evidence Links:** [router app/api/add_to_session.py:50](../../app/api/add_to_session.py#L50), [GET /missing :228](../../app/api/add_to_session.py#L228), [/add/signed-url :237](../../app/api/add_to_session.py#L237), [/add/slides :450](../../app/api/add_to_session.py#L450), [/add/chat :597](../../app/api/add_to_session.py#L597), [/add/manifest :711](../../app/api/add_to_session.py#L711), [mount app/main.py:216](../../app/main.py#L216)
