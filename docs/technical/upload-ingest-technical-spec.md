# Upload & Ingest — Technical Spec

> Module key: `upload-ingest`. Code-verified against the rounds.vin repository on 2026-06-08.
> Paths are relative to this file (`docs/technical/`). Uncertain items are tagged
> `NOT VERIFIED IN CODE`, `IMPLEMENTATION NOT FOUND`, or `PARTIALLY IMPLEMENTED`.

## Architecture

Two-stage, direct-to-cloud design:

1. **Browser → GCS (bytes).** The API never proxies the recording bytes on the primary
   upload path. The client requests a v4 signed PUT URL and PUTs the file straight to
   the bucket ([../../frontend/src/views/UploadView.vue#L224-L241](../../frontend/src/views/UploadView.vue#L224); [../../app/api/gcs_upload.py#L69-L86](../../app/api/gcs_upload.py#L69)).
2. **Browser → API (confirm + enqueue).** `POST /v1/gcs/upload-complete` validates
   scope (R7), writes `sources` rows, parses manifest/chat, and enqueues a Celery
   `ingest_task` that fans out into the processing pipeline
   ([../../app/api/gcs_upload.py#L110-L219](../../app/api/gcs_upload.py#L110); [../../app/tasks/ingest.py#L38-L202](../../app/tasks/ingest.py#L38)).

The add-to-session surface supports both a GCS-direct transport and a Railway
multipart transport (bytes through the API), selected by an org setting
([../../app/api/add_to_session.py#L13-L23](../../app/api/add_to_session.py#L13); [../../frontend/src/components/session/AddFileModal.vue#L90-L97](../../frontend/src/components/session/AddFileModal.vue#L90)).

```
UploadView.vue
  POST /v1/sessions ───────────► sessions (status=uploading) + session_templates
  ┌─ per file ─┐
  │ POST /v1/gcs/upload-url ───► signed PUT URL + gcs_uri
  │ PUT <signed_url> ─────────► GCS bucket (browser → GCS)
  └────────────┘
  POST /v1/gcs/upload-complete ► R7 check → INSERT sources → parse manifest/chat
                               └► enqueue_ingest() → ingest_task
ingest_task ──► (direct)   ai_process_task  [+ slide_extract_task]
            └─► (enhanced) transition→transcribing; frame_task ‖ slide_extract_task;
                           chain(transcribe_task → finalize_task)
```

## Frontend Components

### `UploadView.vue` ([../../frontend/src/views/UploadView.vue](../../frontend/src/views/UploadView.vue))
- Reactive form state: `pipeline`, `aiMode`, `model`, `style`, `stt`, IIL toggles
  (`iilEnabled`, `tier1`/`tier2`/`tier3`) ([#L56-L67](../../frontend/src/views/UploadView.vue#L56)).
- File state: `attached: Attached[]`, where role is inferred from extension by
  `inferRole()` ([#L70-L97](../../frontend/src/views/UploadView.vue#L70)).
- On mount, prefills defaults from `settingsApi.list()` (`default_ai_model`,
  `default_pipeline`, `default_style`) ([#L37-L53](../../frontend/src/views/UploadView.vue#L37)).
- `buildPipelineConfig()` maps form refs → backend `PipelineConfig`, including the
  `style → template_id` map (`lecture` → `lecture_v1`, etc.) ([#L167-L197](../../frontend/src/views/UploadView.vue#L167)).
- `processBatch()` runs the create → per-file signed-URL+PUT → upload-complete →
  navigate sequence ([#L199-L255](../../frontend/src/views/UploadView.vue#L199)).

### `AddFileModal.vue` ([../../frontend/src/components/session/AddFileModal.vue](../../frontend/src/components/session/AddFileModal.vue))
- Props: `open`, `sessionId`, `type` (`slides|chat|manifest|bios`), `hasExisting` ([#L24-L29](../../frontend/src/components/session/AddFileModal.vue#L24)).
- Phase machine `idle|uploading|committing|conflict|done|error` ([#L78-L79](../../frontend/src/components/session/AddFileModal.vue#L78)).
- `uploadBackend` read from `settingsApi.list().upload_backend`, default `railway` ([#L88](../../frontend/src/components/session/AddFileModal.vue#L88), [#L90-L97](../../frontend/src/components/session/AddFileModal.vue#L90)).
- GCS transport uses `XMLHttpRequest` with `upload.onprogress` for a real progress bar ([#L161-L171](../../frontend/src/components/session/AddFileModal.vue#L161)).
- Conflict resolvers: `chooseSlideMode`, `chooseChatMode`, `chooseManifestMode` ([#L250-L279](../../frontend/src/components/session/AddFileModal.vue#L250)).

### `SessionDetailView.vue` (host of the modal)
- Imports `AddFileModal`, opens it via `fileAction()`, maps file role → modal type via
  `ROLE_TO_MODAL_TYPE` ([../../frontend/src/views/SessionDetailView.vue#L21](../../frontend/src/views/SessionDetailView.vue#L21), [#L308-L322](../../frontend/src/views/SessionDetailView.vue#L308), [#L752-L759](../../frontend/src/views/SessionDetailView.vue#L752)).

### API client ([../../frontend/src/services/api.ts](../../frontend/src/services/api.ts))
- `gcs.signedUrl(sessionId, filename, role)` → `POST /v1/gcs/upload-url` ([#L949-L954](../../frontend/src/services/api.ts#L949)).
- `gcs.uploadComplete(sessionId, files[])` → `POST /v1/gcs/upload-complete` ([#L955-L958](../../frontend/src/services/api.ts#L955)).

## Backend Services

### `app/services/gcs.py` ([../../app/services/gcs.py](../../app/services/gcs.py))
- `_ROLE_PREFIXES` maps role → bucket subdir: video → root, slide → `slides/`,
  manifest → `manifest/`, audio_enhance/audio → `uploads/`, chat → `chat/`, other →
  `uploads/` ([#L24-L32](../../app/services/gcs.py#L24)).
- `session_prefix(id)` → `gs://<bucket>/sessions/<id>/` ([#L35-L37](../../app/services/gcs.py#L35)).
- `blob_name_for_role()` / `gcs_uri()` compose canonical object names ([#L40-L54](../../app/services/gcs.py#L40)).
- **`find_out_of_scope_uri(files, session_id)`** — the R7 enforcement primitive: returns
  the first `gcs_uri` not starting with `session_prefix`, treating missing/non-string
  URIs as out-of-scope ([#L57-L70](../../app/services/gcs.py#L57)).
- `make_signed_put_url()` — v4 PUT URL, default `ttl_minutes=60` ([#L73-L90](../../app/services/gcs.py#L73)).

### `app/api/gcs_upload.py` ([../../app/api/gcs_upload.py](../../app/api/gcs_upload.py))
- `/upload-url` — calls `check_user_quota`, mints the URL, echoes `mime_type` and
  `expires_in_seconds` (3600) ([#L69-L86](../../app/api/gcs_upload.py#L69)).
- `/upload-complete` — `validate_files` → R7 `find_out_of_scope_uri` → session-exists
  check → `reserve_slot` → `INSERT INTO sources … ON CONFLICT (gcs_uri) DO NOTHING` →
  `audit_events` → `_parse_manifest_and_chat_sources` → `enqueue_ingest` ([#L110-L219](../../app/api/gcs_upload.py#L110)).
- `_parse_manifest_and_chat_sources()` — downloads manifest/chat objects via
  `asyncio.to_thread(_read_gcs_text)` and persists parsed structures ([#L222-L502](../../app/api/gcs_upload.py#L222)).

### `app/api/add_to_session.py` ([../../app/api/add_to_session.py](../../app/api/add_to_session.py))
- GCS helpers: client/bucket builders, `_staging_blob_name` (`sessions/{id}/staging/phase6/{uuid}/{file}`), upload/download/delete, signed PUT/GET minting ([#L74-L162](../../app/api/add_to_session.py#L74)).
- `_intake_upload()` — unifies the multipart and `{gcs_uri}` JSON paths, enforcing
  Phase-6 staging scope on the JSON path ([#L279-L332](../../app/api/add_to_session.py#L279)).
- `_compute_missing()` — per-type presence booleans from authoritative tables ([#L194-L223](../../app/api/add_to_session.py#L194)).
- Slide thumbnail rendering via PyMuPDF for the conflict UI ([#L341-L418](../../app/api/add_to_session.py#L341)).

## APIs

| Method & Path | Auth | Purpose | Source |
|---|---|---|---|
| `POST /v1/sessions` | CurrentUser | Create session (status `uploading`) + `session_templates` row | [sessions.py:178-256](../../app/api/sessions.py#L178) |
| `POST /v1/gcs/upload-url` | CurrentUser | Mint 60-min v4 PUT URL + canonical `gcs_uri` | [gcs_upload.py:69-86](../../app/api/gcs_upload.py#L69) |
| `POST /v1/gcs/upload-complete` | CurrentUser | R7-validate, write `sources`, parse manifest/chat, enqueue ingest | [gcs_upload.py:110-219](../../app/api/gcs_upload.py#L110) |
| `GET /v1/sessions/{id}/missing` | CurrentUser | Per-type presence booleans (`has_slides`/`has_chat`/`has_manifest`/`has_bios`) | [add_to_session.py:228-232](../../app/api/add_to_session.py#L228) |
| `POST /v1/sessions/{id}/add/signed-url` | CurrentUser | Mint staging PUT URL (add path) | [add_to_session.py:237-274](../../app/api/add_to_session.py#L237) |
| `POST /v1/sessions/{id}/add/slides` | CurrentUser | Add/replace/append slide deck; `mode=replace\|append\|replace_selected` | [add_to_session.py:450-553](../../app/api/add_to_session.py#L450) |
| `POST /v1/sessions/{id}/add/chat` | CurrentUser | Add/replace chat; `?confirm=true`, `?start_time=` | [add_to_session.py:597-678](../../app/api/add_to_session.py#L597) |
| `POST /v1/sessions/{id}/add/manifest` | CurrentUser | Add/replace manifest; `mode=use_new\|keep_current` | [add_to_session.py:711-824](../../app/api/add_to_session.py#L711) |

### Request/response contracts (upload path)
- `UploadUrlRequest{session_id, filename, role?, mime_type?}` → `UploadUrlResponse{signed_url, gcs_uri, blob_name, mime_type?, expires_in_seconds=3600}` ([gcs_upload.py:54-86](../../app/api/gcs_upload.py#L54)).
- `UploadCompleteRequest{session_id, files: UploadCompleteFile[min_length=1]}`,
  `UploadCompleteFile{gcs_uri, role?, filename?, content_type?, size_bytes?, duration_sec?}`
  → `UploadCompleteResponse{session_id, accepted[], manifest?}` ([gcs_upload.py:90-107](../../app/api/gcs_upload.py#L90)).

## Data Models

### `sources` ([../../migrations/001_init.sql#L36-L51](../../migrations/001_init.sql#L36))
`id UUID PK`, `session_id UUID FK→sessions ON DELETE CASCADE`, `role TEXT NOT NULL`,
`filename TEXT NOT NULL`, `gcs_uri TEXT NOT NULL`, `content_type TEXT`, `size_bytes BIGINT`,
`duration_sec INTEGER`, `metadata JSONB`, `created_at TIMESTAMPTZ`. Indexes on
`session_id`, `(session_id, role)`, and **unique index `sources_gcs_uri_uq` on `gcs_uri`**.

### `session_templates` ([../../migrations/009_session_templates.sql#L32-L45](../../migrations/009_session_templates.sql#L32))
PK `session_id UUID FK→sessions ON DELETE CASCADE`; `ai_pipeline` (default `enhanced`),
`ai_mode` (`transcript`), `ai_model` (`gemini-2.5-pro`), `prompt_mode`, `custom_prompt`,
`stt_backend` (`google_latest_long`), `template_id FK→templates` (`lecture_v1`),
`iil_config JSONB`, `auto_detected_template_id`, `auto_detected_confidence REAL`. Backfilled
for legacy sessions ([#L52-L55](../../migrations/009_session_templates.sql#L52)). The
`gemini-2.5-pro` default was set by migration 028; org default model flipped to
`gemini-2.5-pro` by [migration 027](../../migrations/027_default_gcs_upload_backend.sql).

### `templates` ([../../migrations/009_session_templates.sql#L8-L28](../../migrations/009_session_templates.sql#L8))
Seeded with `lecture_v1`, `training_v1`, `technical_v1`, `podcast_v1`, `sales_v1`.

### Manifest-derived models ([../../migrations/011_manifest.sql](../../migrations/011_manifest.sql))
- `sessions` columns added: `title_long`, `title_short`, `ce_broker_id`, `class_id`,
  `tags JSONB`, `publishing_links JSONB`, `polls_raw TEXT`, `polls_parsed JSONB` ([#L10-L17](../../migrations/011_manifest.sql#L10)).
- `session_speakers{id, session_id, role, name, credentials, bio, sort_order}` ([#L22-L31](../../migrations/011_manifest.sql#L22)).
- `session_slide_resources{id, session_id, slide_number, label, url, sort_order}` ([#L36-L45](../../migrations/011_manifest.sql#L36)).

### `sessions.status` enum ([../../migrations/010_state_machine.sql#L21-L26](../../migrations/010_state_machine.sql#L21))
CHECK over `uploading|transcribing|normalizing|fusing|aligning|ready|complete|failed`.
Legacy `ingesting` normalized to `uploading` ([#L17-L19](../../migrations/010_state_machine.sql#L17)).

## Events

- **`audit_events`** rows: `upload.complete.sources`, `upload.complete.manifest`,
  `upload.complete.chat` ([gcs_upload.py:176](../../app/api/gcs_upload.py#L176), [:386](../../app/api/gcs_upload.py#L386), [:453](../../app/api/gcs_upload.py#L453)).
- **`session_audit.processing_log`** JSONB-appended on every status transition
  ([state_machine.py:52-95](../../app/engines/state_machine.py#L52)).
- **WebSocket `processing_update`** events emitted on transition via `ws_bridge`
  ([state_machine.py:98-111](../../app/engines/state_machine.py#L98)).
- **Celery task dispatch** is the inter-service event mechanism (`enqueue_ingest` →
  `ingest_task` → `transcribe`/`finalize`/`ai_process`/`frame`/`slide_extract`)
  ([ingest.py:141-206](../../app/tasks/ingest.py#L141)).

## State Management

- **Frontend:** local `ref` state in each component; no Vuex/Pinia store dedicated to
  upload state. Defaults pulled from `settingsApi.list()` on mount.
- **Backend session state:** the only legal path to mutate `sessions.status` is the FSM
  in `state_machine.py` (`transition_session` async / `transition_session_sync` for
  Celery). It locks the row `FOR UPDATE`, validates against `ALLOWED_TRANSITIONS`,
  rejects moves out of terminal states, and appends an audit entry, all atomically
  ([state_machine.py:114-247](../../app/engines/state_machine.py#L114)).
- **Rate-limit slots:** Redis sets `sessions:active:{user}` + list `sessions:queue`,
  reserved on upload-complete and released by finalize / failure handlers
  ([rate_limit.py:22-95](../../app/middleware/rate_limit.py#L22)).

## Validation

- **Pydantic:** `filename` 1–512 chars; `role`/`mime_type` length-capped; `files`
  `min_length=1`; each file `gcs_uri` `min_length=1` ([gcs_upload.py:54-101](../../app/api/gcs_upload.py#L54)).
- **R7 scope:** `find_out_of_scope_uri` → 400 `VALIDATION_FAILED` ([gcs_upload.py:128-137](../../app/api/gcs_upload.py#L128)).
- **`validate_files`:** `audio_enhance` < 100 KB → 400; `video`/`audio` `duration_sec`
  over 180 min → 400 ([rate_limit.py:98-129](../../app/middleware/rate_limit.py#L98)).
- **Add path MIME:** `_reject_primary_av` and `_reject_bad_type_mime` enforce type maps;
  primary A/V rejected on the add path entirely ([add_to_session.py:179-189](../../app/api/add_to_session.py#L179)).
- **Add path staging scope:** `_is_phase6_staging_uri` ([add_to_session.py:97-99](../../app/api/add_to_session.py#L97)).
- `MAX_UPLOAD_SIZE_MB` is defined ([config.py:48](../../app/config.py#L48)) but no byte-size
  gate enforcing it was found in the upload paths — `IMPLEMENTATION NOT FOUND`.

## Security

- **R7 is the core boundary** — a client cannot register a `gcs_uri` pointing outside its
  own session's prefix, limiting blast radius of a crafted/leaked URI ([gcs.py:57-70](../../app/services/gcs.py#L57); test `tests/test_gcs_scope.py` referenced in [gcs.py:12-14](../../app/services/gcs.py#L12)).
- **Signed URLs are short-lived (60 min) and method-scoped** (`PUT`) ([gcs.py:85-89](../../app/services/gcs.py#L85)).
- **Add-path signed URLs are staging-scoped** to `sessions/{id}/staging/phase6/`, a
  session-bounded prefix the bucket lifecycle reaps at 48h ([add_to_session.py:14-22](../../app/api/add_to_session.py#L14), [:92-99](../../app/api/add_to_session.py#L92)).
- **GCS credentials** use `GCP_PROJECT_ID`; the bucket is `GCS_BUCKET` ([gcs.py:81-82](../../app/services/gcs.py#L81); config [config.py:35-36](../../app/config.py#L35)).
- **Auth** is JWT-only via the `CurrentUser` dependency on every endpoint.

## Permissions

JWT presence only. None of the upload/ingest endpoints apply a role check — each takes
`CurrentUser` and nothing more ([gcs_upload.py:70](../../app/api/gcs_upload.py#L70), [:114](../../app/api/gcs_upload.py#L114); [add_to_session.py:229](../../app/api/add_to_session.py#L229), [:451-457](../../app/api/add_to_session.py#L451); [sessions.py:179](../../app/api/sessions.py#L179)).

Role-based authorization is **scaffold-only** repo-wide: `app/security/roles.py`
(`is_admin`/`require_admin`) is not wired into these endpoints, and `auth_users.role`
(migration 045) is not read by `get_current_user`. The only real admin gate anywhere is
the hardcoded `user.email == "johndean@vin.com"` (`LEGACY_ADMIN_EMAIL`) check used by a
few other modules, plus one client-side `adminOnly` route guard
([../../frontend/src/router/index.ts#L51](../../frontend/src/router/index.ts#L51), [#L63](../../frontend/src/router/index.ts#L63)). Neither applies to Upload & Ingest.

The only access constraint at upload time is rate limiting: `MAX_CONCURRENT_SESSIONS`
(3) per user and `MAX_QUEUE_LENGTH` (10) global → 429 ([rate_limit.py:33-67](../../app/middleware/rate_limit.py#L33)).

## Integrations

- **Google Cloud Storage** (`google.cloud.storage`) — signed URLs + object I/O ([gcs.py:79](../../app/services/gcs.py#L79); [add_to_session.py:74-76](../../app/api/add_to_session.py#L74); [gcs_upload.py:494-502](../../app/api/gcs_upload.py#L494)).
- **Redis** — rate-limit accounting ([rate_limit.py:27-30](../../app/middleware/rate_limit.py#L27)).
- **Celery** — `ingest_task` and downstream tasks ([ingest.py](../../app/tasks/ingest.py)).
- **PyMuPDF (`fitz`)** — slide page count + thumbnails ([add_to_session.py:347-378](../../app/api/add_to_session.py#L347)).
- **extras2 parser / chat parser** — `parse_extras2`, `parse_chat_file` ([gcs_upload.py:230-233](../../app/api/gcs_upload.py#L230)).
- The downstream Gemini/STT integrations are owned by the processing pipeline, not this
  module; upload-ingest only selects the route via `session_templates.ai_pipeline`.

## Background Jobs

- **`ingest_task`** ([../../app/tasks/ingest.py#L32-L202](../../app/tasks/ingest.py#L32)):
  - Skips unless status is `uploading` ([#L61-L63](../../app/tasks/ingest.py#L61)).
  - Reads `session_templates.ai_pipeline` and the slide-source count ([#L67-L88](../../app/tasks/ingest.py#L67)).
  - **Re-ingest guard:** refuses to run if `segments` already exist (requires explicit
    `/v1/diag/reingest`) ([#L96-L113](../../app/tasks/ingest.py#L96)).
  - **`direct`:** enqueues `ai_process_task` (+ `slide_extract_task` if slides) ([#L141-L158](../../app/tasks/ingest.py#L141)).
  - **`enhanced`:** transitions to `transcribing`, fans out `frame_task` and
    `slide_extract_task`, then `chain(transcribe_task → finalize_task)` ([#L160-L193](../../app/tasks/ingest.py#L160)).
  - `max_retries=2` with backoff on exception ([#L36](../../app/tasks/ingest.py#L36), [#L195-L199](../../app/tasks/ingest.py#L195)).
- **`enqueue_ingest(session_id)`** — `apply_async(queue="celery")` ([#L204-L206](../../app/tasks/ingest.py#L204)).
- **`upload_watchdog_task`** ([../../app/tasks/upload_watchdog.py#L51-L112](../../app/tasks/upload_watchdog.py#L51)) — Celery Beat task; finds sessions stuck on `uploading` past `UPLOAD_STUCK_THRESHOLD_SEC` (300s) with ≥1 source and re-calls `enqueue_ingest`. Disabled by default (`UPLOAD_WATCHDOG_ENABLED=False`, [config.py:100](../../app/config.py#L100)); cooldown 600s ([config.py:111](../../app/config.py#L111)).
- **`slide_extract_task`** — dispatched directly from `add/slides` ([add_to_session.py:537-544](../../app/api/add_to_session.py#L537)).

## Error Handling

- `/upload-url` GCS sign failure → 500 `InternalError` ([gcs_upload.py:77-78](../../app/api/gcs_upload.py#L77)).
- `/upload-complete`: out-of-scope → 400; session-missing → 404 (before slot reservation
  to avoid leaking a slot) ([gcs_upload.py:128-146](../../app/api/gcs_upload.py#L128)).
- Manifest/chat parse and ingest enqueue are wrapped so failures are logged and do not
  fail the HTTP request; manifest/chat outcomes are written to `audit_events` ([gcs_upload.py:194-219](../../app/api/gcs_upload.py#L194), [:403-422](../../app/api/gcs_upload.py#L403)).
- Add path: GCS upload/sign failure → 500; staging blob not found → 404; bad type →
  400 `VALIDATION_FAILED`; existing-content collisions → 409 with a comparison `details`
  payload ([add_to_session.py:264-331](../../app/api/add_to_session.py#L264), [:468-486](../../app/api/add_to_session.py#L468), [:619-632](../../app/api/add_to_session.py#L619), [:740-749](../../app/api/add_to_session.py#L740)).
- FSM rejects illegal transitions with `ConflictError` (→ 409) ([state_machine.py:145-154](../../app/engines/state_machine.py#L145)).
- **Discrepancy:** `create_session` still catches `sessions_code_key` and returns 409
  ([sessions.py:219-228](../../app/api/sessions.py#L219)), but migration 035 dropped that
  unique constraint ([migrations/035_drop_sessions_code_unique.sql#L21](../../migrations/035_drop_sessions_code_unique.sql#L21)) — the handler is now effectively dead. Flagged.

## Performance Considerations

- **Direct-to-GCS bypass** keeps large recordings off the API container's bandwidth and
  memory — the explicit rationale for defaulting `upload_backend=gcs` ([migrations/027_default_gcs_upload_backend.sql#L13-L25](../../migrations/027_default_gcs_upload_backend.sql#L13)).
- **GCS object reads are run in threads** (`asyncio.to_thread`) so the async event loop
  isn't blocked during manifest/chat download ([gcs_upload.py:240](../../app/api/gcs_upload.py#L240), [:426](../../app/api/gcs_upload.py#L426)).
- **Thumbnail uploads are concurrency-bounded** by an `asyncio.Semaphore(10)` ([add_to_session.py:387-401](../../app/api/add_to_session.py#L387)).
- **Concurrency caps** (3 active per user, 10 global queue) bound simultaneous ingest
  load ([rate_limit.py:33-67](../../app/middleware/rate_limit.py#L33)).
- **`gemini-2.5-pro` default** chosen for its 2M-token context to avoid token-overflow
  failures on large video + slide + prompt payloads ([migrations/027_default_gcs_upload_backend.sql#L19-L25](../../migrations/027_default_gcs_upload_backend.sql#L19)).
- **No client-side chunking/resumable uploads** — a single PUT per file; an expired
  60-min URL forces a re-request (`NOT VERIFIED IN CODE` for any retry-on-401/403 in the
  current `UploadView.vue`; the file header comment mentions it but `processBatch` throws
  on a non-OK PUT without re-requesting, [UploadView.vue:227-232](../../frontend/src/views/UploadView.vue#L227)).

## Source Verification
- **Files Used:** app/api/gcs_upload.py, app/api/add_to_session.py, app/services/gcs.py, app/tasks/ingest.py, app/tasks/upload_watchdog.py, app/middleware/rate_limit.py, app/engines/state_machine.py, app/config.py, app/api/sessions.py, frontend/src/views/UploadView.vue, frontend/src/views/SessionDetailView.vue, frontend/src/components/session/AddFileModal.vue, frontend/src/services/api.ts, frontend/src/router/index.ts, migrations/001_init.sql, migrations/009_session_templates.sql, migrations/010_state_machine.sql, migrations/011_manifest.sql, migrations/027_default_gcs_upload_backend.sql, migrations/035_drop_sessions_code_unique.sql
- **Components Used:** UploadView.vue, AddFileModal.vue, SessionDetailView.vue
- **APIs Used:** POST /v1/sessions, POST /v1/gcs/upload-url, POST /v1/gcs/upload-complete, GET /v1/sessions/{id}/missing, POST /v1/sessions/{id}/add/signed-url, POST /v1/sessions/{id}/add/slides, POST /v1/sessions/{id}/add/chat, POST /v1/sessions/{id}/add/manifest
- **Database Tables Used:** sessions, sources, session_templates, templates, session_speakers, speakers, session_slide_resources, polls, poll_options, chat_messages, slides, audit_events, session_audit
- **Permission Logic Used:** JWT presence only (CurrentUser); no role gate on this module. Repo-wide admin gate is the LEGACY_ADMIN_EMAIL string check + one client-side adminOnly guard, neither applicable here.
- **Confidence Score:** High — claims are sourced to specific lines; unenforced/uncertain behaviors are tagged.
- **Evidence Links:** [gcs.py:57-90](../../app/services/gcs.py#L57), [gcs_upload.py:110-219](../../app/api/gcs_upload.py#L110), [ingest.py:32-206](../../app/tasks/ingest.py#L32), [state_machine.py:40-170](../../app/engines/state_machine.py#L40), [add_to_session.py:279-332](../../app/api/add_to_session.py#L279), [rate_limit.py:33-129](../../app/middleware/rate_limit.py#L33)
