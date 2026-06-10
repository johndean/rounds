# API Reference — GCS Upload (`/v1/gcs`)

Signed-URL minting plus upload confirmation with the R7 scope-validation invariant. This router issues a v4 PUT signed URL for a client-side browser upload, then confirms the upload, writes `sources` rows, parses manifest/chat sidecar files, and kicks off the Celery ingest pipeline.

- **Source file:** [`app/api/gcs_upload.py`](../../app/api/gcs_upload.py)
- **Router prefix / tag:** `/v1/gcs`, tag `gcs` — [app/api/gcs_upload.py:46](../../app/api/gcs_upload.py#L46)
- **Mounted in:** [app/main.py:213](../../app/main.py#L213) (`app.include_router(gcs_router.router)`)
- **Endpoints found:** 2 (`POST /upload-url`, `POST /upload-complete`)

## Authentication & Authorization (router-wide)

Both endpoints take a `CurrentUser` dependency (`_user`), so **a valid JWT bearer token is required**. `CurrentUser = Annotated[User, Depends(get_current_user)]` decodes the HS256 JWT, checks `auth_users.is_active`, and falls back to the `AUTH_USERS` env CSV — see [app/auth.py:172](../../app/auth.py#L172) and [app/auth.py:208](../../app/auth.py#L208).

**Authorization is JWT-only.** Neither endpoint contains any `LEGACY_ADMIN_EMAIL`, `require_admin`, `is_admin`, or `johndean@vin.com` gate — verified by grep over [app/api/gcs_upload.py](../../app/api/gcs_upload.py) (no matches). Any authenticated user may call these routes. (`get_current_user` does not read `auth_users.role`; role-based authorization is scaffold-only — NOT VERIFIED IN CODE that any role check applies here, because none exists.)

---

## `POST /v1/gcs/upload-url`

- **Endpoint:** `/v1/gcs/upload-url`
- **Method:** `POST`
- **Decorator:** `@router.post("/upload-url", response_model=UploadUrlResponse)` — [app/api/gcs_upload.py:69](../../app/api/gcs_upload.py#L69)
- **Handler:** `async def signed_url(payload, _user)` — [app/api/gcs_upload.py:70](../../app/api/gcs_upload.py#L70)

### Purpose
Returns a 60-minute v4 PUT signed URL for the given `session_id` / `role` / `filename` so the browser can upload the object directly to GCS. The handler docstring states "Returns a 60-minute v4 PUT signed URL for the given session/role/filename" ([app/api/gcs_upload.py:71](../../app/api/gcs_upload.py#L71)).

### Authentication
JWT required (`_user: CurrentUser`) — [app/api/gcs_upload.py:70](../../app/api/gcs_upload.py#L70).

### Authorization
JWT-only. Before signing, `check_user_quota(_user)` runs ([app/api/gcs_upload.py:74](../../app/api/gcs_upload.py#L74)), which enforces a per-user concurrent-session quota / global queue cap and raises HTTP 429 (`RATE_LIMIT_USER`) when exceeded — see [app/middleware/rate_limit.py:33](../../app/middleware/rate_limit.py#L33). This is a rate-limit gate, not a permission gate.

### Request Schema
Body model `UploadUrlRequest` — [app/api/gcs_upload.py:54](../../app/api/gcs_upload.py#L54):

| Field | Type | Required | Constraints |
|---|---|---|---|
| `session_id` | `str` | yes | `min_length=1` |
| `filename` | `str` | yes | `min_length=1`, `max_length=512` |
| `role` | `str \| null` | no | default `null`, `max_length=64` |
| `mime_type` | `str \| null` | no | default `null`, `max_length=128` |

`role` is mapped to a bucket subdirectory by `make_signed_put_url` → `blob_name_for_role` ([app/services/gcs.py:40](../../app/services/gcs.py#L40)); known roles: `video` (session root), `slide` (`slides/`), `manifest` (`manifest/`), `audio_enhance`/`audio`/`other` (`uploads/`), `chat` (`chat/`). Unknown/`null` roles fall back to `uploads/`.

### Response Schema
Model `UploadUrlResponse` — [app/api/gcs_upload.py:61](../../app/api/gcs_upload.py#L61). All payloads are wrapped in the standard `{success, data, error, meta}` envelope by `EnvelopeMiddleware` ([app/middleware/envelope.py:196](../../app/middleware/envelope.py#L196)); the table is the `data` object:

| Field | Type | Notes |
|---|---|---|
| `signed_url` | `str` | v4 PUT signed URL |
| `gcs_uri` | `str` | canonical `gs://<bucket>/sessions/<id>/.../<filename>` |
| `blob_name` | `str` | object name after the bucket — `uri.split("/", 3)[-1]` ([app/api/gcs_upload.py:79](../../app/api/gcs_upload.py#L79)) |
| `mime_type` | `str \| null` | echoes the request `mime_type` |
| `expires_in_seconds` | `int` | `3600` — `_DEFAULT_SIGNED_URL_TTL_SECONDS` ([app/api/gcs_upload.py:50](../../app/api/gcs_upload.py#L50)) |

The TTL is sourced from `make_signed_put_url(..., ttl_minutes=60)` in [app/services/gcs.py:73](../../app/services/gcs.py#L73) (BR-013: signed-URL TTL = 3600s).

### Validation Rules
- Pydantic enforces non-empty `session_id`/`filename` and the length caps above (422 on violation, surfaced through the envelope).
- `check_user_quota` enforces concurrency/queue caps before signing.

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| Body fails Pydantic validation | FastAPI 422 (validation) | model at [:54](../../app/api/gcs_upload.py#L54) |
| Concurrency / queue cap hit | HTTP 429 (`RATE_LIMIT_USER`) | [app/middleware/rate_limit.py:44](../../app/middleware/rate_limit.py#L44) |
| GCS SDK sign failure | `INTERNAL_ERROR` / 500 — `InternalError(f"GCS sign failed: {exc.__class__.__name__}")` | [app/api/gcs_upload.py:78](../../app/api/gcs_upload.py#L78) |

### Example
```http
POST /v1/gcs/upload-url
Authorization: Bearer <jwt>
Content-Type: application/json

{ "session_id": "3f...uuid", "filename": "lecture.mp4", "role": "video", "mime_type": "video/mp4" }
```
Response `data`:
```json
{
  "signed_url": "https://storage.googleapis.com/...&X-Goog-Signature=...",
  "gcs_uri": "gs://video-pipeline-uploads-mic/sessions/3f...uuid/lecture.mp4",
  "blob_name": "sessions/3f...uuid/lecture.mp4",
  "mime_type": "video/mp4",
  "expires_in_seconds": 3600
}
```

### Related Screens
- `UploadView.vue` — calls `/v1/gcs/upload-url` ([frontend/src/services/api.ts:952](../../frontend/src/services/api.ts#L952), documented at [frontend/src/views/UploadView.vue:12](../../frontend/src/views/UploadView.vue#L12)).

### Related Tables
None written directly. The returned `gcs_uri` is consumed by `/upload-complete`, which writes `sources`.

---

## `POST /v1/gcs/upload-complete`

- **Endpoint:** `/v1/gcs/upload-complete`
- **Method:** `POST`
- **Decorator:** `@router.post("/upload-complete", response_model=UploadCompleteResponse)` — [app/api/gcs_upload.py:110](../../app/api/gcs_upload.py#L110)
- **Handler:** `async def upload_complete(payload, db, _user)` — [app/api/gcs_upload.py:111](../../app/api/gcs_upload.py#L111)

### Purpose
Confirms one or more uploads for a session. Enforces the **R7 scope invariant** (every `gcs_uri` must start with the session's scoped prefix), inserts `sources` rows, logs an `audit_events` row, parses manifest (`role='manifest'`) and chat (`role='chat'`) sidecar files, and enqueues the Celery ingest pipeline.

### Authentication
JWT required (`_user: CurrentUser`) — [app/api/gcs_upload.py:114](../../app/api/gcs_upload.py#L114).

### Authorization
JWT-only — no admin gate. `_user.email` is used only for the rate-limit slot reservation ([app/api/gcs_upload.py:148](../../app/api/gcs_upload.py#L148)) and the `audit_events.actor_email` value ([app/api/gcs_upload.py:180](../../app/api/gcs_upload.py#L180)), not for any permission check.

### Request Schema
Body model `UploadCompleteRequest` — [app/api/gcs_upload.py:99](../../app/api/gcs_upload.py#L99):

| Field | Type | Required | Constraints |
|---|---|---|---|
| `session_id` | `str` | yes | `min_length=1` |
| `files` | `list[UploadCompleteFile]` | yes | `min_length=1` (Pydantic enforces non-empty) |

`UploadCompleteFile` — [app/api/gcs_upload.py:90](../../app/api/gcs_upload.py#L90):

| Field | Type | Required | Notes |
|---|---|---|---|
| `gcs_uri` | `str` | yes | `min_length=1` |
| `role` | `str \| null` | no | defaults to `"other"` at insert if null ([:163](../../app/api/gcs_upload.py#L163)) |
| `filename` | `str \| null` | no | defaults to last path segment of `gcs_uri` if null ([:163](../../app/api/gcs_upload.py#L163)) |
| `content_type` | `str \| null` | no | |
| `size_bytes` | `int \| null` | no | |
| `duration_sec` | `int \| null` | no | |

### Response Schema
Model `UploadCompleteResponse` — [app/api/gcs_upload.py:104](../../app/api/gcs_upload.py#L104) (envelope `data`):

| Field | Type | Notes |
|---|---|---|
| `session_id` | `str` | echoes request |
| `accepted` | `list[str]` | the `gcs_uri`s inserted (one per file) |
| `manifest` | `dict \| null` | manifest/chat parse summary, or `null` if neither present |

The `manifest` summary, when a `role='manifest'` file is parsed successfully ([:371](../../app/api/gcs_upload.py#L371)), contains: `parsed` (bool), `code`, `title_long`, `title_short`, `speakers` (list of `{role, name, credentials}`), `slide_resource_count`, `slide_count_with_resources`, `publishing_links` (list of keys), `polls_parsed_count`. A `role='chat'` file adds `chat_messages` (count) ([:448](../../app/api/gcs_upload.py#L448)). On manifest parse failure the summary is `{"parsed": False}` ([:405](../../app/api/gcs_upload.py#L405)). Parse field shapes derive from `ParsedManifest` in [app/services/extras2_parser.py:40](../../app/services/extras2_parser.py#L40).

### Validation Rules
1. **`validate_files(payload.files, session_id)`** ([:125](../../app/api/gcs_upload.py#L125)) — rejects `audio_enhance` files below the minimum byte threshold (likely silent) and `video`/`audio` files exceeding `MAX_VIDEO_DURATION_MINUTES`; both raise HTTP 400 `VALIDATION_FAILED` ([app/middleware/rate_limit.py:98](../../app/middleware/rate_limit.py#L98)).
2. **R7 scope check** — `find_out_of_scope_uri` returns the first `gcs_uri` not starting with `gs://<bucket>/sessions/<id>/` ([app/services/gcs.py:57](../../app/services/gcs.py#L57)); if any, raises `ValidationFailedError` ([:130](../../app/api/gcs_upload.py#L130)).
3. **Session existence** — `SELECT 1 FROM sessions WHERE id = :sid` must return a row, else `NotFoundError` ([:146](../../app/api/gcs_upload.py#L146)). This runs **before** `reserve_slot` so a 404 does not leak a rate-limit slot ([:140](../../app/api/gcs_upload.py#L140)).

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| `files` empty / body invalid | FastAPI 422 | model at [:99](../../app/api/gcs_upload.py#L99) |
| Silent enhance audio / over-duration media | HTTP 400 `VALIDATION_FAILED` | [app/middleware/rate_limit.py:109](../../app/middleware/rate_limit.py#L109) |
| `gcs_uri` outside session scope | `VALIDATION_FAILED` / 400; details include `expected_prefix`, `gcs_uri`, `offending_uri` | [app/api/gcs_upload.py:130](../../app/api/gcs_upload.py#L130) |
| Session does not exist | `NOT_FOUND` / 404 | [app/api/gcs_upload.py:146](../../app/api/gcs_upload.py#L146) |

Note: manifest/chat parse failures and ingest-enqueue failures are **non-fatal** — they are caught and logged, and the endpoint still returns 200 (`manifest: {"parsed": false}` or omitted chat count). See [:403](../../app/api/gcs_upload.py#L403), [:469](../../app/api/gcs_upload.py#L469), [:203](../../app/api/gcs_upload.py#L203).

### Example
```http
POST /v1/gcs/upload-complete
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "session_id": "3f...uuid",
  "files": [
    { "gcs_uri": "gs://video-pipeline-uploads-mic/sessions/3f...uuid/lecture.mp4", "role": "video", "filename": "lecture.mp4", "content_type": "video/mp4", "size_bytes": 524288000, "duration_sec": 3600 }
  ]
}
```
Response `data`:
```json
{ "session_id": "3f...uuid", "accepted": ["gs://video-pipeline-uploads-mic/sessions/3f...uuid/lecture.mp4"], "manifest": null }
```

### Related Screens
- `UploadView.vue` — calls `/v1/gcs/upload-complete` ([frontend/src/services/api.ts:957](../../frontend/src/services/api.ts#L957), documented at [frontend/src/views/UploadView.vue:14](../../frontend/src/views/UploadView.vue#L14)).
- `SectionDiagnostics.vue` references `/upload-complete` as the ingest trigger boundary ([frontend/src/components/settings/SectionDiagnostics.vue:86](../../frontend/src/components/settings/SectionDiagnostics.vue#L86)).

### Related Tables
Written / read by this endpoint and its helpers:
- `sessions` — existence check ([:142](../../app/api/gcs_upload.py#L142)); manifest parse updates `code`, `title_long`, `title_short`, `ce_broker_id`, `class_id`, `tags`, `publishing_links`, `polls_raw`, `polls_parsed` ([:264](../../app/api/gcs_upload.py#L264)).
- `sources` — INSERT one row per file, `ON CONFLICT (gcs_uri) DO NOTHING` ([:152](../../app/api/gcs_upload.py#L152)).
- `audit_events` — INSERT (`upload.complete.sources`, `upload.complete.manifest`, `upload.complete.chat`) ([:176](../../app/api/gcs_upload.py#L176), [:385](../../app/api/gcs_upload.py#L385), [:452](../../app/api/gcs_upload.py#L452)).
- `session_speakers` and `speakers` — INSERT from parsed manifest speakers ([:276](../../app/api/gcs_upload.py#L276), [:292](../../app/api/gcs_upload.py#L292)).
- `polls`, `poll_options` — INSERT from parsed `polls_parsed` ([:314](../../app/api/gcs_upload.py#L314), [:343](../../app/api/gcs_upload.py#L343)).
- `session_slide_resources` — INSERT from parsed slide resources ([:356](../../app/api/gcs_upload.py#L356)).
- `chat_messages` — INSERT from parsed chat file ([:429](../../app/api/gcs_upload.py#L429)).

---

## Source Verification
- **Files Used:** [app/api/gcs_upload.py](../../app/api/gcs_upload.py), [app/auth.py](../../app/auth.py), [app/middleware/envelope.py](../../app/middleware/envelope.py), [app/middleware/rate_limit.py](../../app/middleware/rate_limit.py), [app/services/gcs.py](../../app/services/gcs.py), [app/services/extras2_parser.py](../../app/services/extras2_parser.py), [app/main.py](../../app/main.py), frontend/src/services/api.ts, frontend/src/views/UploadView.vue
- **Components Used:** UploadView.vue, SectionDiagnostics.vue
- **APIs Used:** `POST /v1/gcs/upload-url`, `POST /v1/gcs/upload-complete`
- **Database Tables Used:** sessions, sources, audit_events, session_speakers, speakers, polls, poll_options, session_slide_resources, chat_messages
- **Permission Logic Used:** JWT presence only (`CurrentUser` → `get_current_user`); plus a per-user rate-limit quota on `/upload-url`. No admin/role gate present.
- **Confidence Score:** High — both decorators, all Pydantic models, validation paths, and error classes were read directly from source; router mount confirmed in main.py.
- **Evidence Links:** [decorator /upload-url app/api/gcs_upload.py:69](../../app/api/gcs_upload.py#L69), [decorator /upload-complete app/api/gcs_upload.py:110](../../app/api/gcs_upload.py#L110), [R7 check app/services/gcs.py:57](../../app/services/gcs.py#L57), [auth dep app/auth.py:208](../../app/auth.py#L208), [mount app/main.py:213](../../app/main.py#L213)
