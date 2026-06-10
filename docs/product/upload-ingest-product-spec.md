# Upload & Ingest — Product Spec

> Module key: `upload-ingest`. Code-verified against the rounds.vin repository on 2026-06-08.
> Every claim below is traceable to a source file. Unproven behavior is tagged
> `NOT VERIFIED IN CODE`, `IMPLEMENTATION NOT FOUND`, or `PARTIALLY IMPLEMENTED`.

## Overview

Upload & Ingest is the entry point of rounds.vin. An operator selects one or more
recording artifacts (video/audio plus optional slide deck, chat log, and session
manifest), the browser uploads the bytes directly to Google Cloud Storage (GCS) via
short-lived signed PUT URLs, and the server confirms the upload, persists `sources`
rows, parses any manifest/chat files, and enqueues a background Celery pipeline that
drives the session from status `uploading` toward `ready`.

There are two surfaces in this module:

1. **The Upload page** (`/upload`) — creates a brand-new session and uploads its
   primary artifacts. Implemented in [frontend/src/views/UploadView.vue](../../frontend/src/views/UploadView.vue).
2. **Add-file-to-existing-session** — attaches a slide deck, chat log, or manifest
   to a session that already exists, from the Session Detail page. Implemented in
   [frontend/src/components/session/AddFileModal.vue](../../frontend/src/components/session/AddFileModal.vue),
   backed by [app/api/add_to_session.py](../../app/api/add_to_session.py).

## Purpose

Get a recorded session out of an operator's local machine and into a state where the
AI processing pipeline can produce a first-pass transcript. The module's
responsibilities are: collect files, validate scope and basic constraints, write
durable source records, parse structured side-channel inputs (manifest, chat), and
hand off to ingest.

## User Value

- **Direct-to-cloud upload.** Bytes go browser → GCS bucket through a v4 signed PUT,
  bypassing the API container ([UploadView.vue:226-241](../../frontend/src/views/UploadView.vue#L226), rationale in [migrations/027_default_gcs_upload_backend.sql:13-17](../../migrations/027_default_gcs_upload_backend.sql#L13)).
- **Multiple files per session, roles auto-detected from filename.** A single batch can
  carry video, audio, slides, manifest, and chat ([UploadView.vue:86-110](../../frontend/src/views/UploadView.vue#L86)).
- **Manifest enrichment.** An uploaded extras2 manifest populates the session's title,
  CE Broker ID, speaker roster, per-slide resource links, and polls automatically
  ([gcs_upload.py:222-422](../../app/api/gcs_upload.py#L222)).
- **Conflict-aware re-uploads.** Adding files to a session that already has slides,
  chat, or a manifest surfaces a side-by-side comparison instead of silently
  overwriting ([add_to_session.py:468-486](../../app/api/add_to_session.py#L468), [add_to_session.py:619-632](../../app/api/add_to_session.py#L619), [add_to_session.py:740-749](../../app/api/add_to_session.py#L740)).

## Navigation

- **Upload page:** route `/upload` → `UploadView.vue` (route registered in [frontend/src/router/index.ts](../../frontend/src/router/index.ts)). On successful upload the page calls `router.push('/p/<session_id>')` to the Processing page ([UploadView.vue:248](../../frontend/src/views/UploadView.vue#L248)).
- **Add-file modal:** opened from the Session Detail page (`/s/<id>` family). `SessionDetailView.vue` imports `AddFileModal` and opens it via `fileAction()` ([SessionDetailView.vue:21](../../frontend/src/views/SessionDetailView.vue#L21), [:319-322](../../frontend/src/views/SessionDetailView.vue#L319), [:752-759](../../frontend/src/views/SessionDetailView.vue#L752)).

## Screens

### Upload page (`UploadView.vue`)

A single scrolling form:

- **Drop zone** — drag-and-drop or click-to-browse via a hidden `<input type="file" multiple>` ([:330-374](../../frontend/src/views/UploadView.vue#L330)).
- **Attached-files list** — per file shows kind label, filename, human size, a colored
  chip, and a remove button; manifest files get an "(extras2)" note ([:376-399](../../frontend/src/views/UploadView.vue#L376)).
- **Processing Pipeline** select — `direct` (Direct to AI) vs `enhanced` (AI-Enhanced) ([:404-415](../../frontend/src/views/UploadView.vue#L404)).
- **AI Processing Mode** select — transcript / summary / key-moments / structured-notes / custom-prompt ([:258-264](../../frontend/src/views/UploadView.vue#L258), [:417-426](../../frontend/src/views/UploadView.vue#L417)).
- **AI Model** select — driven by `AI_MODELS` fixture ([:429-436](../../frontend/src/views/UploadView.vue#L429)).
- **Custom Prompt** block — shown only when AI mode is `custom-prompt` ([:438-468](../../frontend/src/views/UploadView.vue#L438)).
- **Speech-to-Text (STT)** select — `google_latest_long` / `google_phone`; disabled unless pipeline is `enhanced` ([:470-482](../../frontend/src/views/UploadView.vue#L470)).
- **Processing Style** card — collapsible style picker (Lecture, Training, Technical, Podcast, Sales, Custom) ([:484-530](../../frontend/src/views/UploadView.vue#L484)).
- **Instructor Intelligence Layer (IIL)** card — master toggle + three filler tiers ([:532-578](../../frontend/src/views/UploadView.vue#L532)).
- **Process button** — shows `Uploading {done}/{total}…` progress while running ([:580-595](../../frontend/src/views/UploadView.vue#L580)).

> The heading copy still reads "Media Intelligence Compiler" ([:341](../../frontend/src/views/UploadView.vue#L341)) — a carryover label from the MIC predecessor, present in the current code.

### Add-file modal (`AddFileModal.vue`)

A dialog with a five-phase state machine: `idle` → `uploading` → `committing` →
`done`, with `conflict` and `error` branches ([AddFileModal.vue:78](../../frontend/src/components/session/AddFileModal.vue#L78)). Four `type` variants:

- **slides** — PDF or PPTX; conflict pane shows current vs new deck thumbnails with per-slide checkboxes ([:431-472](../../frontend/src/components/session/AddFileModal.vue#L431)).
- **chat** — `.txt`/`.csv`; conflict pane shows current vs new message previews ([:474-493](../../frontend/src/components/session/AddFileModal.vue#L474)).
- **manifest** — `.txt`; conflict pane shows current vs new field summaries ([:495-514](../../frontend/src/components/session/AddFileModal.vue#L495)).
- **bios** — informational only; directs the user to edit bios inline on the Speakers panel, no upload ([:66-72](../../frontend/src/components/session/AddFileModal.vue#L66), [:352-357](../../frontend/src/components/session/AddFileModal.vue#L352)).

## User Flows

### Flow A — Upload a new session (`UploadView.vue` → backend)

1. User picks/drops files; each is assigned a role by filename extension
   (`inferRole`) ([:86-97](../../frontend/src/views/UploadView.vue#L86)).
2. User adjusts pipeline/mode/model/style/IIL and clicks **Process**.
3. Frontend generates a session code: `MMDDYY_<filestem>_<4-char-random>` ([:153-165](../../frontend/src/views/UploadView.vue#L153)).
4. `POST /v1/sessions` creates the session (status `uploading`) plus its
   `session_templates` config row ([UploadView.vue:211-219](../../frontend/src/views/UploadView.vue#L211); [sessions.py:178-256](../../app/api/sessions.py#L178)).
5. For each file: `POST /v1/gcs/upload-url` returns a signed PUT URL + canonical
   `gcs_uri`; the browser PUTs the bytes straight to GCS ([UploadView.vue:224-241](../../frontend/src/views/UploadView.vue#L224); [gcs_upload.py:69-86](../../app/api/gcs_upload.py#L69)).
6. `POST /v1/gcs/upload-complete` validates R7 scope, inserts `sources` rows, parses
   manifest/chat, and enqueues `ingest_task` ([gcs_upload.py:110-219](../../app/api/gcs_upload.py#L110)).
7. Frontend navigates to `/p/<session_id>` (Processing page) ([:248](../../frontend/src/views/UploadView.vue#L248)).

### Flow B — Add a file to an existing session (`AddFileModal.vue`)

The transport depends on the org-level `upload_backend` setting, read on modal mount
([AddFileModal.vue:90-97](../../frontend/src/components/session/AddFileModal.vue#L90)):

- **`gcs` transport:** `POST /v1/sessions/{id}/add/signed-url` → browser PUT → `POST /v1/sessions/{id}/add/{type}` with `{gcs_uri}` ([:151-178](../../frontend/src/components/session/AddFileModal.vue#L151)).
- **`railway` transport (default in code):** multipart `POST /v1/sessions/{id}/add/{type}` with the file bytes streamed through the API ([:179-206](../../frontend/src/components/session/AddFileModal.vue#L179)). The org default is `gcs` per [migrations/027_default_gcs_upload_backend.sql:27-29](../../migrations/027_default_gcs_upload_backend.sql#L27); the component's hardcoded fallback when the setting cannot be read is `railway` ([:88](../../frontend/src/components/session/AddFileModal.vue#L88)).

On a 409 the modal renders the conflict pane and the user chooses Replace / Append /
Replace-selected (slides), Use-new / Keep-current (chat, manifest) ([:250-279](../../frontend/src/components/session/AddFileModal.vue#L250)).

### Flow C — Stuck-upload recovery (background, opt-in)

A Celery Beat task `upload_watchdog_task` finds sessions stuck on status `uploading`
past `UPLOAD_STUCK_THRESHOLD_SEC` (300s) that have at least one source row and
re-calls `enqueue_ingest()` ([app/tasks/upload_watchdog.py:51-112](../../app/tasks/upload_watchdog.py#L51)). It is **off by default** (`UPLOAD_WATCHDOG_ENABLED=False`, [config.py:100](../../app/config.py#L100)). There is no manual "resume" button in the UI. `IMPLEMENTATION NOT FOUND` for any user-facing resume control.

## Business Rules

- **BR-013 (signed-URL TTL = 3600s / 60 min).** Both upload-url endpoints mint v4 PUT
  URLs with a 1-hour expiry ([gcs_upload.py:50](../../app/api/gcs_upload.py#L50), [gcs.py:73-90](../../app/services/gcs.py#L73), [add_to_session.py:69](../../app/api/add_to_session.py#L69), [:146-153](../../app/api/add_to_session.py#L146)).
- **R7 scope invariant.** `/v1/gcs/upload-complete` rejects any `gcs_uri` not starting
  with `gs://<bucket>/sessions/<session_id>/` ([gcs.py:57-70](../../app/services/gcs.py#L57); enforced at [gcs_upload.py:128-137](../../app/api/gcs_upload.py#L128)).
- **Add-file staging scope.** `add/*` JSON-mode uploads must reference a URI under
  `gs://<bucket>/sessions/<id>/staging/phase6/` ([add_to_session.py:97-99](../../app/api/add_to_session.py#L97), [:310-311](../../app/api/add_to_session.py#L310)).
- **Primary A/V cannot be added via the add-file path.** Any audio/video MIME submitted
  to `add/*` is rejected with guidance to use the main `/upload` page ([add_to_session.py:179-183](../../app/api/add_to_session.py#L179)).
- **Slide deck must be PDF or PPTX** on the add path ([add_to_session.py:186-189](../../app/api/add_to_session.py#L186)).
- **Pipeline default.** Session create defaults `ai_pipeline` to `direct` when no
  `pipeline_config` is supplied ([sessions.py:61](../../app/api/sessions.py#L61)); the
  `session_templates` table column default is `enhanced` ([migrations/009_session_templates.sql:34](../../migrations/009_session_templates.sql#L34)). The Upload form defaults the select to `direct` ([UploadView.vue:56](../../frontend/src/views/UploadView.vue#L56)).
- **Ingest routing.** `ingest_task` reads `session_templates.ai_pipeline`: `direct`
  routes to `ai_process_task` (Gemini multimodal); anything else routes to the STT
  `enhanced` chain ([ingest.py:88](../../app/tasks/ingest.py#L88), [:141-193](../../app/tasks/ingest.py#L141)).

## Validation Rules

- **At least one file required (request body).** `UploadCompleteRequest.files` has `min_length=1` ([gcs_upload.py:101](../../app/api/gcs_upload.py#L101)). The Upload form also blocks Process with no files attached ([UploadView.vue:200-203](../../frontend/src/views/UploadView.vue#L200)).
- **R7 out-of-scope URI → 400 `VALIDATION_FAILED`** with `expected_prefix`, `gcs_uri`, and (legacy) `offending_uri` in details ([gcs_upload.py:129-137](../../app/api/gcs_upload.py#L129)).
- **`audio_enhance` minimum size = 100 KB.** Smaller files are rejected as likely
  silent/corrupt ([rate_limit.py:24](../../app/middleware/rate_limit.py#L24), [:109-118](../../app/middleware/rate_limit.py#L109)).
- **Media duration cap.** For `video`/`audio` roles, a client-supplied `duration_sec`
  over `MAX_VIDEO_DURATION_MINUTES` (180 min) is rejected ([rate_limit.py:119-129](../../app/middleware/rate_limit.py#L119); config [config.py:49](../../app/config.py#L49)).
  This relies on the client sending `duration_sec`; the Upload form does not compute
  duration and sends `duration_sec: null` at session create ([UploadView.vue:215](../../frontend/src/views/UploadView.vue#L215)), and the per-file `completeFiles` objects it builds omit `duration_sec` entirely ([:233-239](../../frontend/src/views/UploadView.vue#L233)). `PARTIALLY IMPLEMENTED` — the server-side check exists but the primary UI does not feed it duration data.
- **`MAX_UPLOAD_SIZE_MB` (2048).** Defined in config ([config.py:48](../../app/config.py#L48)) but **no enforcement of a per-file byte cap was found** in the upload-complete or add-to-session paths. `IMPLEMENTATION NOT FOUND` for an active size-limit gate.
- **Role-allowed MIME maps** for the add path: slides {PDF, PPTX}, chat {text/plain, text/csv, application/octet-stream}, manifest {text/plain, application/octet-stream} ([add_to_session.py:61-67](../../app/api/add_to_session.py#L61)).

> Note on the documented "MAX_UPLOAD_SIZE_MB 48 / MAX_VIDEO_DURATION_MINUTES 49" from
> the task brief: the actual code values are **2048** and **180** respectively
> ([config.py:48-49](../../app/config.py#L48)). The brief figures do not match code.

## States

Session status values (CHECK-constrained): `uploading`, `transcribing`,
`normalizing`, `fusing`, `aligning`, `ready`, `complete`, `failed`
([migrations/010_state_machine.sql:21-26](../../migrations/010_state_machine.sql#L21)).

- New sessions are created at `uploading` ([sessions.py:205](../../app/api/sessions.py#L205)).
- `ingest_task` only proceeds if status is still `uploading`; otherwise it skips ([ingest.py:61-63](../../app/tasks/ingest.py#L61)).
- Allowed transitions out of `uploading`: `transcribing`, `ready`, `failed` ([state_machine.py:40-47](../../app/engines/state_machine.py#L40)). The `enhanced` path moves to `transcribing`; the `direct` path lets `ai_process_task` mark the session `ready` itself.

Add-file modal phases: `idle` / `uploading` / `committing` / `conflict` / `done` /
`error` ([AddFileModal.vue:78-79](../../frontend/src/components/session/AddFileModal.vue#L78)).

## Dependencies

- **Google Cloud Storage** — signed URLs + direct object I/O ([gcs.py](../../app/services/gcs.py), [add_to_session.py:74-162](../../app/api/add_to_session.py#L74)).
- **Redis** — concurrency/queue rate-limit slots ([rate_limit.py:27-30](../../app/middleware/rate_limit.py#L27)). Redis being unavailable does not block uploads (warns and proceeds) ([rate_limit.py:64-66](../../app/middleware/rate_limit.py#L64)).
- **Celery + Postgres** — ingest orchestration ([ingest.py](../../app/tasks/ingest.py)).
- **extras2 manifest parser** (`parse_extras2`) and **chat parser** (`parse_chat_file`) ([gcs_upload.py:230-233](../../app/api/gcs_upload.py#L230)).
- **PyMuPDF (`fitz`)** — PDF page counting + thumbnail rendering for the slide-conflict UI ([add_to_session.py:341-401](../../app/api/add_to_session.py#L341)).

## Error Handling

- **GCS sign failure** on `/upload-url` → 500 `InternalError("GCS sign failed: ...")` ([gcs_upload.py:77-78](../../app/api/gcs_upload.py#L77)).
- **Session not found** on upload-complete → 404 (checked before reserving a rate-limit slot so a 404 doesn't leak a slot) ([gcs_upload.py:139-146](../../app/api/gcs_upload.py#L139)).
- **Out-of-scope URI** → 400 `VALIDATION_FAILED` ([gcs_upload.py:129-137](../../app/api/gcs_upload.py#L129)).
- **Duplicate `gcs_uri`** → `ON CONFLICT (gcs_uri) DO NOTHING`, silently de-duped ([gcs_upload.py:157](../../app/api/gcs_upload.py#L157); unique index [migrations/001_init.sql:51](../../migrations/001_init.sql#L51)).
- **Manifest/chat parse failure is non-fatal** — ingest still runs; the failure is logged and an `audit_events` row is written ([gcs_upload.py:403-422](../../app/api/gcs_upload.py#L403), [:469-487](../../app/api/gcs_upload.py#L469)).
- **Ingest enqueue failure is non-fatal** to the HTTP response — logged as a warning ([gcs_upload.py:203-206](../../app/api/gcs_upload.py#L203)); the watchdog (if enabled) can later recover the stuck session.
- **Add-file 409 conflict** carries a `details` payload the modal renders ([add_to_session.py:472-486](../../app/api/add_to_session.py#L472); [AddFileModal.vue:192-200](../../frontend/src/components/session/AddFileModal.vue#L192)).
- **Front-end upload errors** (signed-URL failure, GCS PUT non-2xx) surface as a toast ([UploadView.vue:232](../../frontend/src/views/UploadView.vue#L232), [:249-251](../../frontend/src/views/UploadView.vue#L249)).

## Permissions

Authorization across this module is **JWT-presence only**. Every endpoint takes a
`CurrentUser` dependency (a logged-in user), and none of the upload/ingest endpoints
apply role checks:

- `/v1/gcs/upload-url`, `/v1/gcs/upload-complete` — `_user: CurrentUser`, no role gate ([gcs_upload.py:70](../../app/api/gcs_upload.py#L70), [:114](../../app/api/gcs_upload.py#L114)).
- `/v1/sessions/{id}/missing`, `/add/*` — `_u: CurrentUser`, no role gate ([add_to_session.py:229](../../app/api/add_to_session.py#L229), [:238-240](../../app/api/add_to_session.py#L238), [:451-457](../../app/api/add_to_session.py#L451)).
- `POST /v1/sessions` (session create) — `user: CurrentUser`, no role gate ([sessions.py:179](../../app/api/sessions.py#L179)).

Role-based authorization is **scaffold-only** repo-wide: `app/security/roles.py`
(`is_admin`/`require_admin`) is not wired into these endpoints, and the
`auth_users.role` column (migration 045) is not read by `get_current_user`. The only
real admin gate anywhere is a hardcoded `user.email == "johndean@vin.com"`
(`LEGACY_ADMIN_EMAIL`) check used in a handful of other modules, plus one client-side
`adminOnly` route guard ([frontend/src/router/index.ts:51](../../frontend/src/router/index.ts#L51), [:63](../../frontend/src/router/index.ts#L63)). **None of those apply to Upload & Ingest** — there is no role tier on this module.

Rate limits (not roles) are the only access constraint at upload time: per-user
`MAX_CONCURRENT_SESSIONS` (3) and global `MAX_QUEUE_LENGTH` (10) → 429
`RATE_LIMIT_USER` / `RATE_LIMIT_QUEUE` ([rate_limit.py:33-67](../../app/middleware/rate_limit.py#L33); config [config.py:46-47](../../app/config.py#L46)).

## Reporting Impacts

- **`audit_events`** rows are written at upload-complete for the source set, manifest
  parse outcome, and chat parse outcome ([gcs_upload.py:174-189](../../app/api/gcs_upload.py#L174), [:384-422](../../app/api/gcs_upload.py#L384), [:449-487](../../app/api/gcs_upload.py#L449)). These provide durable, queryable evidence of what landed and whether enrichment succeeded.
- **`session_audit.processing_log`** accumulates a JSONB entry on every status
  transition driven by ingest ([state_machine.py:52-95](../../app/engines/state_machine.py#L52)).
- No dedicated reporting/dashboard surface for upload metrics was found in this module.
  `IMPLEMENTATION NOT FOUND`.

## Audit Requirements

The module emits structured `audit_events` (kinds `upload.complete.sources`,
`upload.complete.manifest`, `upload.complete.chat`) with actor email where known and
a JSONB `details` blob ([gcs_upload.py:176-189](../../app/api/gcs_upload.py#L176)). Manifest/chat audit rows are written with `actor_email = NULL` ([gcs_upload.py:386](../../app/api/gcs_upload.py#L386), [:453](../../app/api/gcs_upload.py#L453)). The add-file endpoints do **not** write `audit_events` rows in the code reviewed — `NOT VERIFIED IN CODE` that add-file actions are audited.

## Data Relationships

- **`sessions`** (1) → **`sources`** (many) via `session_id`; `sources.gcs_uri` is
  globally unique ([migrations/001_init.sql:36-51](../../migrations/001_init.sql#L36)).
- **`sessions`** (1) → **`session_templates`** (1) via PK `session_id` — created in the
  same transaction as the session ([migrations/009_session_templates.sql:32-45](../../migrations/009_session_templates.sql#L32); [sessions.py:232-254](../../app/api/sessions.py#L232)).
- **Manifest parse** populates `sessions` columns (`code`, `title_long`, `title_short`,
  `ce_broker_id`, `class_id`, `tags`, `publishing_links`, `polls_raw`, `polls_parsed`),
  and inserts into `session_speakers`, `speakers`, `polls`, `poll_options`, and
  `session_slide_resources` ([gcs_upload.py:243-365](../../app/api/gcs_upload.py#L243); columns/tables in [migrations/011_manifest.sql](../../migrations/011_manifest.sql)).
- **Chat parse** inserts into `chat_messages` ([gcs_upload.py:428-444](../../app/api/gcs_upload.py#L428)).
- **Add-slides** inserts a `sources` row (role `slide`) and dispatches `slide_extract_task` ([add_to_session.py:524-544](../../app/api/add_to_session.py#L524)).

## Known Constraints

- **No pause/resume** for in-flight uploads; a leaked/expired signed URL must be
  re-requested (1-hour TTL) ([gcs_upload.py:50](../../app/api/gcs_upload.py#L50)).
- **Duration cap depends on the client sending `duration_sec`** — the Upload form does
  not, so the 180-minute cap is effectively unenforced from that surface (`PARTIALLY IMPLEMENTED`).
- **`MAX_UPLOAD_SIZE_MB` is defined but not enforced** (`IMPLEMENTATION NOT FOUND`).
- **No automatic template detection at upload** — the operator picks a style/template
  manually; `auto_detected_template_id`/`auto_detected_confidence` columns exist but the
  upload path leaves them unset ([migrations/009_session_templates.sql:42-43](../../migrations/009_session_templates.sql#L42)).
- **Code-collision 409 handler is likely dead code.** `create_session` still catches the
  `sessions_code_key` unique violation and returns a 409 ([sessions.py:219-228](../../app/api/sessions.py#L219)), but migration 035 dropped that unique constraint ([migrations/035_drop_sessions_code_unique.sql:21](../../migrations/035_drop_sessions_code_unique.sql#L21)), so the violation can no longer fire. Flagged as a discrepancy.
- **Stuck-upload recovery is automatic-only and disabled by default** — no manual resume
  UI ([config.py:100](../../app/config.py#L100); [upload_watchdog.py](../../app/tasks/upload_watchdog.py)).
- **Re-ingest guard.** If a session already has `segments`, `ingest_task` refuses to
  re-run without an explicit `/v1/diag/reingest/<id>` reset ([ingest.py:96-113](../../app/tasks/ingest.py#L96)).

## Source Verification
- **Files Used:** app/api/gcs_upload.py, app/api/add_to_session.py, app/services/gcs.py, app/tasks/ingest.py, app/tasks/upload_watchdog.py, app/middleware/rate_limit.py, app/engines/state_machine.py, app/config.py, app/api/sessions.py, frontend/src/views/UploadView.vue, frontend/src/views/SessionDetailView.vue, frontend/src/components/session/AddFileModal.vue, frontend/src/services/api.ts, frontend/src/router/index.ts, migrations/001_init.sql, migrations/009_session_templates.sql, migrations/010_state_machine.sql, migrations/011_manifest.sql, migrations/027_default_gcs_upload_backend.sql, migrations/035_drop_sessions_code_unique.sql, docs/product/upload-processing.md (seed)
- **Components Used:** UploadView.vue, AddFileModal.vue, SessionDetailView.vue
- **APIs Used:** POST /v1/sessions, POST /v1/gcs/upload-url, POST /v1/gcs/upload-complete, GET /v1/sessions/{id}/missing, POST /v1/sessions/{id}/add/signed-url, POST /v1/sessions/{id}/add/slides, POST /v1/sessions/{id}/add/chat, POST /v1/sessions/{id}/add/manifest
- **Database Tables Used:** sessions, sources, session_templates, session_speakers, speakers, session_slide_resources, polls, poll_options, chat_messages, slides, audit_events, session_audit
- **Permission Logic Used:** JWT presence only (CurrentUser dependency); no role gate on this module. Repo-wide admin gate is the LEGACY_ADMIN_EMAIL string check + one client-side adminOnly guard, neither of which applies here.
- **Confidence Score:** High — every claim is backed by a read of the cited source; uncertain/unenforced items are explicitly tagged.
- **Evidence Links:** [gcs_upload.py:110-219](../../app/api/gcs_upload.py#L110), [gcs.py:57-70](../../app/services/gcs.py#L57), [ingest.py:38-202](../../app/tasks/ingest.py#L38), [config.py:46-49](../../app/config.py#L46), [UploadView.vue:199-255](../../frontend/src/views/UploadView.vue#L199), [add_to_session.py:450-553](../../app/api/add_to_session.py#L450)
