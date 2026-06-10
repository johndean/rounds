# Upload & Ingest — Demo Questions

> Module key: `upload-ingest`. Every answer below is code-true as of 2026-06-08 and
> traceable to the cited source. Questions with no code-true answer were omitted.

---

## User

### Q1. How do I upload a recording?
**Verified Answer:** Go to `/upload`, drag-drop or click to pick one or more files,
adjust the processing options if needed, and click **Process**. The browser uploads the
bytes straight to cloud storage, then navigates you to the Processing page (`/p/<id>`).
**Supporting Evidence:** Drop zone + Process button + `router.push('/p/...')`.
**Source Files:** frontend/src/views/UploadView.vue ([L330-374](../../frontend/src/views/UploadView.vue#L330), [L580-595](../../frontend/src/views/UploadView.vue#L580), [L248](../../frontend/src/views/UploadView.vue#L248))
**API References:** POST /v1/sessions, POST /v1/gcs/upload-url, POST /v1/gcs/upload-complete
**Database References:** sessions, sources

### Q2. Can I upload several files at once (video + slides + chat)?
**Verified Answer:** Yes. The picker is `multiple` and each file's role is auto-detected
from its filename extension (video, audio, slide, manifest, chat, other).
**Supporting Evidence:** `<input type="file" multiple>` and `inferRole()`.
**Source Files:** frontend/src/views/UploadView.vue ([L86-97](../../frontend/src/views/UploadView.vue#L86), [L330-337](../../frontend/src/views/UploadView.vue#L330))
**API References:** POST /v1/gcs/upload-complete
**Database References:** sources

### Q3. What file types are accepted?
**Verified Answer:** On the main Upload page roles are inferred from extension: video
(mp4/mov/mkv/webm/avi/m4v), audio (mp3/m4a/wav/ogg/flac/aac), slides (pdf/pptx/ppt),
manifest or chat (.txt), else "other". On the add-to-session path, slides must be PDF or
PPTX, and primary audio/video is rejected with a message to use the main Upload page.
**Supporting Evidence:** `inferRole()`; add-path MIME maps + `_reject_primary_av`.
**Source Files:** frontend/src/views/UploadView.vue ([L86-97](../../frontend/src/views/UploadView.vue#L86)); app/api/add_to_session.py ([L61-67](../../app/api/add_to_session.py#L61), [L179-189](../../app/api/add_to_session.py#L179))
**API References:** POST /v1/sessions/{id}/add/slides
**Database References:** sources

### Q4. Can I attach a slide deck to a session I already uploaded?
**Verified Answer:** Yes, from the Session Detail page via the Add-file modal. If the
session already has slides you get a Replace ALL / Append / Replace-selected choice with
thumbnail previews.
**Supporting Evidence:** AddFileModal slide conflict pane; `add/slides` modes.
**Source Files:** frontend/src/components/session/AddFileModal.vue ([L431-472](../../frontend/src/components/session/AddFileModal.vue#L431)); app/api/add_to_session.py ([L450-553](../../app/api/add_to_session.py#L450))
**API References:** POST /v1/sessions/{id}/add/slides
**Database References:** sources, slides

### Q5. What happens after the upload finishes?
**Verified Answer:** The session is created at status `uploading`, source rows are
written, any manifest/chat is parsed, and a background ingest job is queued; you're sent
to the Processing page to watch it advance.
**Supporting Evidence:** upload-complete enqueues `ingest_task`; UI navigates to `/p/<id>`.
**Source Files:** app/api/gcs_upload.py ([L198-219](../../app/api/gcs_upload.py#L198)); frontend/src/views/UploadView.vue ([L248](../../frontend/src/views/UploadView.vue#L248))
**API References:** POST /v1/gcs/upload-complete
**Database References:** sessions, session_audit

### Q6. Can I close the tab while a big video uploads?
**Verified Answer:** The UI explicitly warns "Streaming bytes to GCS — do not close this
tab" while uploading. There is no pause/resume; the signed URL lasts 60 minutes and a
failed PUT surfaces an error toast rather than auto-resuming.
**Supporting Evidence:** progress copy; throw-on-non-OK PUT; 60-min TTL.
**Source Files:** frontend/src/views/UploadView.vue ([L593-595](../../frontend/src/views/UploadView.vue#L593), [L227-232](../../frontend/src/views/UploadView.vue#L227)); app/api/gcs_upload.py ([L50](../../app/api/gcs_upload.py#L50))
**API References:** POST /v1/gcs/upload-url
**Database References:** none

---

## Operations

### Q1. What status does a brand-new session start in, and what advances it?
**Verified Answer:** New sessions are created at `uploading`. `ingest_task` only proceeds
while status is `uploading`; the `enhanced` route then transitions it to `transcribing`,
while the `direct` route lets `ai_process_task` mark it `ready`.
**Supporting Evidence:** create inserts `'uploading'`; ingest guard + route branches.
**Source Files:** app/api/sessions.py ([L205](../../app/api/sessions.py#L205)); app/tasks/ingest.py ([L61-63](../../app/tasks/ingest.py#L61), [L141-193](../../app/tasks/ingest.py#L141))
**API References:** POST /v1/sessions
**Database References:** sessions, session_templates

### Q2. A session is stuck on "uploading" — how is it recovered?
**Verified Answer:** A Celery Beat watchdog (`upload_watchdog_task`) finds sessions stuck
on `uploading` longer than 300s that have at least one source row and re-queues ingest.
It is OFF by default (`UPLOAD_WATCHDOG_ENABLED=False`); operators can also manually fire
`/v1/diag/reingest/<id>`. There is no end-user resume button.
**Supporting Evidence:** watchdog task; config default; diag reingest reference.
**Source Files:** app/tasks/upload_watchdog.py ([L51-112](../../app/tasks/upload_watchdog.py#L51)); app/config.py ([L100-111](../../app/config.py#L100)); app/tasks/ingest.py ([L96-106](../../app/tasks/ingest.py#L96))
**API References:** POST /v1/diag/reingest/{id}
**Database References:** sessions, sources

### Q3. Why does re-running ingest on a session refuse to do anything?
**Verified Answer:** `ingest_task` has a pre-flight guard: if the session already has
`segments`, it refuses to re-run to avoid silent cross-pipeline overwrites, and tells the
operator to call `/v1/diag/reingest/<id>` (which DELETEs segments first).
**Supporting Evidence:** segments-exist guard.
**Source Files:** app/tasks/ingest.py ([L96-113](../../app/tasks/ingest.py#L96))
**API References:** POST /v1/diag/reingest/{id}
**Database References:** segments, sessions

### Q4. What ties together direct vs enhanced processing at ingest time?
**Verified Answer:** `ingest_task` reads `session_templates.ai_pipeline`. `direct` →
`ai_process_task` (Gemini multimodal, marks ready itself); anything else (`enhanced`) →
transition to `transcribing`, fan out `frame_task` + `slide_extract_task`, then chain
`transcribe_task → finalize_task`.
**Supporting Evidence:** pipeline read + branch.
**Source Files:** app/tasks/ingest.py ([L67-88](../../app/tasks/ingest.py#L67), [L141-193](../../app/tasks/ingest.py#L141))
**API References:** none
**Database References:** session_templates, sources

### Q5. How many concurrent uploads can a single operator have in flight?
**Verified Answer:** `MAX_CONCURRENT_SESSIONS` = 3 per user, with a global
`MAX_QUEUE_LENGTH` = 10. Exceeding either returns 429 (`RATE_LIMIT_USER` /
`RATE_LIMIT_QUEUE`). If Redis is down the check is skipped (uploads not blocked).
**Supporting Evidence:** `check_user_quota`; config values.
**Source Files:** app/middleware/rate_limit.py ([L33-67](../../app/middleware/rate_limit.py#L33)); app/config.py ([L46-47](../../app/config.py#L46))
**API References:** POST /v1/gcs/upload-url
**Database References:** none (Redis)

---

## Compliance

### Q1. How does the system stop a client uploading to another session's storage area?
**Verified Answer:** The R7 invariant. `/v1/gcs/upload-complete` rejects any `gcs_uri`
that does not begin with `gs://<bucket>/sessions/<session_id>/` (400 `VALIDATION_FAILED`),
enforced by `find_out_of_scope_uri`. Missing/non-string URIs are treated as out-of-scope.
**Supporting Evidence:** scope check + rejection.
**Source Files:** app/services/gcs.py ([L57-70](../../app/services/gcs.py#L57)); app/api/gcs_upload.py ([L128-137](../../app/api/gcs_upload.py#L128))
**API References:** POST /v1/gcs/upload-complete
**Database References:** none

### Q2. Is there an audit trail of what files were uploaded?
**Verified Answer:** Yes, on the main upload path. `audit_events` rows are written for the
source set (`upload.complete.sources`, with actor email), and for manifest and chat parse
outcomes (`upload.complete.manifest`, `upload.complete.chat`, actor `NULL`). The
add-to-session endpoints do not write audit_events in the reviewed code.
**Supporting Evidence:** audit inserts in upload-complete; none in add path.
**Source Files:** app/api/gcs_upload.py ([L174-189](../../app/api/gcs_upload.py#L174), [L384-422](../../app/api/gcs_upload.py#L384), [L449-487](../../app/api/gcs_upload.py#L449))
**API References:** POST /v1/gcs/upload-complete
**Database References:** audit_events

### Q3. Are signed upload URLs time-limited?
**Verified Answer:** Yes — 60 minutes (3600s), v4 signed, method-scoped to PUT, on both
the main and add-to-session upload paths.
**Supporting Evidence:** TTL constants + v4 PUT signing.
**Source Files:** app/services/gcs.py ([L73-90](../../app/services/gcs.py#L73)); app/api/gcs_upload.py ([L50](../../app/api/gcs_upload.py#L50)); app/api/add_to_session.py ([L69](../../app/api/add_to_session.py#L69), [L146-153](../../app/api/add_to_session.py#L146))
**API References:** POST /v1/gcs/upload-url, POST /v1/sessions/{id}/add/signed-url
**Database References:** none

### Q4. Who is allowed to upload — are there role restrictions?
**Verified Answer:** Any authenticated (JWT-bearing) user can upload. There is no
role-based restriction on this module. Role auth is scaffold-only repo-wide; the only real
admin gate anywhere is a hardcoded `johndean@vin.com` check used by other modules plus one
client-side `adminOnly` route guard — neither applies to upload/ingest. The only access
constraint at upload time is rate limiting.
**Supporting Evidence:** CurrentUser-only deps; LEGACY_ADMIN_EMAIL gate lives elsewhere.
**Source Files:** app/api/gcs_upload.py ([L70](../../app/api/gcs_upload.py#L70), [L114](../../app/api/gcs_upload.py#L114)); app/api/add_to_session.py ([L229](../../app/api/add_to_session.py#L229), [L451-457](../../app/api/add_to_session.py#L451)); frontend/src/router/index.ts ([L51](../../frontend/src/router/index.ts#L51), [L63](../../frontend/src/router/index.ts#L63))
**API References:** POST /v1/gcs/upload-complete, POST /v1/sessions/{id}/add/*
**Database References:** none

### Q5. What stops a silent/corrupt audio file from poisoning transcription?
**Verified Answer:** A supplementary `audio_enhance` file smaller than 100 KB is rejected
at upload-complete as likely silent/empty, since it would poison STT.
**Supporting Evidence:** `validate_files` minimum-size check.
**Source Files:** app/middleware/rate_limit.py ([L24](../../app/middleware/rate_limit.py#L24), [L109-118](../../app/middleware/rate_limit.py#L109))
**API References:** POST /v1/gcs/upload-complete
**Database References:** none

---

## Administrator

### Q1. Where is the choice between direct-to-GCS and through-the-server upload made?
**Verified Answer:** The org-level `upload_backend` setting (`gcs` or `railway`). Migration
027 sets the production default to `gcs`. The add-file modal reads it on mount; if it
can't read the setting it falls back to `railway`. The main Upload page always uses the
GCS-direct flow.
**Supporting Evidence:** settings flip; modal mount read + fallback.
**Source Files:** migrations/027_default_gcs_upload_backend.sql ([L27-29](../../migrations/027_default_gcs_upload_backend.sql#L27)); frontend/src/components/session/AddFileModal.vue ([L88](../../frontend/src/components/session/AddFileModal.vue#L88), [L90-97](../../frontend/src/components/session/AddFileModal.vue#L90))
**API References:** GET org settings (settingsApi.list)
**Database References:** org_settings

### Q2. What configuration does each session carry from upload, and where is it stored?
**Verified Answer:** A `session_templates` row created in the same transaction as the
session: `ai_pipeline`, `ai_mode`, `ai_model`, `prompt_mode`, `custom_prompt`,
`stt_backend`, `template_id`, and `iil_config`. Defaults: `enhanced` / `transcript` /
`gemini-2.5-pro` / `google_latest_long` / `lecture_v1`.
**Supporting Evidence:** create writes session_templates; column defaults.
**Source Files:** app/api/sessions.py ([L232-254](../../app/api/sessions.py#L232)); migrations/009_session_templates.sql ([L32-45](../../migrations/009_session_templates.sql#L32))
**API References:** POST /v1/sessions
**Database References:** session_templates, templates

### Q3. Why is the default AI model `gemini-2.5-pro` and not flash?
**Verified Answer:** Migration 027 flipped the default because a 200MB+ video plus a
100+-slide PDF plus the transcript prompt routinely exceeds flash's 1M-token context
(causing `400 INVALID_ARGUMENT`); pro's 2M-token context handles these payloads.
**Supporting Evidence:** migration rationale.
**Source Files:** migrations/027_default_gcs_upload_backend.sql ([L19-25](../../migrations/027_default_gcs_upload_backend.sql#L19))
**API References:** none
**Database References:** org_settings, session_templates

### Q4. Is the upload watchdog safe to turn on in production?
**Verified Answer:** It's a default-OFF kill-switch (`UPLOAD_WATCHDOG_ENABLED`) flipped in
Railway worker env. It only re-calls the same `enqueue_ingest` that `/v1/diag/reingest`
uses, acts on sessions stuck on `uploading` past 300s with ≥1 source, and has a 600s
cooldown between retries on the same session.
**Supporting Evidence:** config flags + task body.
**Source Files:** app/config.py ([L92-111](../../app/config.py#L92)); app/tasks/upload_watchdog.py ([L51-112](../../app/tasks/upload_watchdog.py#L51))
**API References:** none
**Database References:** sessions, sources

### Q5. How are upload defaults presented on the Upload form?
**Verified Answer:** On mount the form calls `settingsApi.list()` and overrides its local
defaults with `default_ai_model`, `default_pipeline`, and `default_style` when present;
otherwise it keeps local fallbacks (pipeline `direct`, model `gemini-2.5-pro`, style
`lecture`).
**Supporting Evidence:** `onMounted` prefill.
**Source Files:** frontend/src/views/UploadView.vue ([L37-53](../../frontend/src/views/UploadView.vue#L37), [L56-67](../../frontend/src/views/UploadView.vue#L56))
**API References:** GET org settings (settingsApi.list)
**Database References:** org_settings

---

## Power User

### Q1. Exactly what sequence does the Upload page run when I click Process?
**Verified Answer:** (1) generate a code `MMDDYY_<stem>_<4-char-random>`; (2) `POST
/v1/sessions` with the pipeline config; (3) for each file `POST /v1/gcs/upload-url` then a
browser `PUT` to the signed URL; (4) `POST /v1/gcs/upload-complete` with all files; (5)
`router.push('/p/<id>')`.
**Supporting Evidence:** `processBatch()` + `genCode()`.
**Source Files:** frontend/src/views/UploadView.vue ([L153-165](../../frontend/src/views/UploadView.vue#L153), [L199-255](../../frontend/src/views/UploadView.vue#L199))
**API References:** POST /v1/sessions, POST /v1/gcs/upload-url, POST /v1/gcs/upload-complete
**Database References:** sessions, sources

### Q2. How do I replace only specific slides in an existing deck?
**Verified Answer:** Upload the new deck via the Add-file modal; on the 409 conflict pane,
check the slides to swap and choose "Replace selected". The backend mode
`replace_selected` requires a `{slide_numbers:[...]}` body of ≥1 positive integer and
rejects numbers exceeding the new deck's page count.
**Supporting Evidence:** modal selected-slide flow; backend validation.
**Source Files:** frontend/src/components/session/AddFileModal.vue ([L250-255](../../frontend/src/components/session/AddFileModal.vue#L250), [L466-471](../../frontend/src/components/session/AddFileModal.vue#L466)); app/api/add_to_session.py ([L488-522](../../app/api/add_to_session.py#L488))
**API References:** POST /v1/sessions/{id}/add/slides?mode=replace_selected
**Database References:** slides, sources

### Q3. What does an uploaded extras2 manifest actually populate?
**Verified Answer:** Session columns (`code`, `title_long`, `title_short`, `ce_broker_id`,
`class_id`, `tags`, `publishing_links`, `polls_raw`, `polls_parsed`), plus rows in
`session_speakers`, bridged into `speakers`, plus `polls`+`poll_options` from parsed
polls, plus `session_slide_resources` for @N anchored links.
**Supporting Evidence:** manifest parse block.
**Source Files:** app/api/gcs_upload.py ([L243-365](../../app/api/gcs_upload.py#L243)); migrations/011_manifest.sql ([L10-45](../../migrations/011_manifest.sql#L10))
**API References:** POST /v1/gcs/upload-complete
**Database References:** sessions, session_speakers, speakers, polls, poll_options, session_slide_resources

### Q4. What's the GCS object layout for a session's files?
**Verified Answer:** `gs://<bucket>/sessions/<id>/<file>` for video (root),
`.../slides/` for slides, `.../manifest/` for manifest, `.../uploads/` for
audio_enhance/audio/other, `.../chat/` for chat. Add-file staging lands under
`.../staging/phase6/<uuid>/<file>`.
**Supporting Evidence:** `_ROLE_PREFIXES`; `_staging_blob_name`.
**Source Files:** app/services/gcs.py ([L24-49](../../app/services/gcs.py#L24)); app/api/add_to_session.py ([L92-94](../../app/api/add_to_session.py#L92))
**API References:** POST /v1/gcs/upload-url
**Database References:** sources

### Q5. If I upload the same file twice, do I get duplicate source rows?
**Verified Answer:** No. `sources.gcs_uri` has a unique index, and the insert uses
`ON CONFLICT (gcs_uri) DO NOTHING`, so a repeated `gcs_uri` is silently de-duped. The
front-end also de-dupes the attached list by name+size before upload.
**Supporting Evidence:** unique index + ON CONFLICT; UI dedupe.
**Source Files:** migrations/001_init.sql ([L51](../../migrations/001_init.sql#L51)); app/api/gcs_upload.py ([L154-157](../../app/api/gcs_upload.py#L154)); frontend/src/views/UploadView.vue ([L135-144](../../frontend/src/views/UploadView.vue#L135))
**API References:** POST /v1/gcs/upload-complete
**Database References:** sources

### Q6. Is there a max video length or file size enforced?
**Verified Answer:** A 180-minute duration cap exists server-side for video/audio, but it
only fires when the client sends `duration_sec` — the Upload form does not compute or send
it, so from that surface the cap is effectively unenforced (PARTIALLY IMPLEMENTED).
`MAX_UPLOAD_SIZE_MB` (2048) is defined in config but no byte-size gate enforcing it was
found (IMPLEMENTATION NOT FOUND).
**Supporting Evidence:** duration check requires duration_sec; UI omits it; size constant unused on upload path.
**Source Files:** app/middleware/rate_limit.py ([L119-129](../../app/middleware/rate_limit.py#L119)); frontend/src/views/UploadView.vue ([L215](../../frontend/src/views/UploadView.vue#L215), [L233-239](../../frontend/src/views/UploadView.vue#L233)); app/config.py ([L48-49](../../app/config.py#L48))
**API References:** POST /v1/gcs/upload-complete
**Database References:** none

---

## Executive

### Q1. Why is the upload designed to go straight to cloud storage?
**Verified Answer:** Speed and reliability for large CE session videos. Routing 200MB+
bytes through the API container is slower and less reliable; a browser→bucket v4 signed
PUT bypasses the server entirely. This was the explicit rationale for defaulting the
upload backend to GCS.
**Supporting Evidence:** migration 027 rationale.
**Source Files:** migrations/027_default_gcs_upload_backend.sql ([L13-17](../../migrations/027_default_gcs_upload_backend.sql#L13)); frontend/src/views/UploadView.vue ([L226-241](../../frontend/src/views/UploadView.vue#L226))
**API References:** POST /v1/gcs/upload-url
**Database References:** org_settings

### Q2. What's the throughput ceiling — how many sessions can be in flight?
**Verified Answer:** 3 active sessions per user and 10 in the global ingest queue, enforced
by rate-limit guards backed by Redis.
**Supporting Evidence:** config + guard.
**Source Files:** app/config.py ([L46-47](../../app/config.py#L46)); app/middleware/rate_limit.py ([L33-67](../../app/middleware/rate_limit.py#L33))
**API References:** POST /v1/gcs/upload-url
**Database References:** none (Redis)

---

## Finance

### Q1. Where is the cost-sensitive AI model choice controlled per session?
**Verified Answer:** Each session stores `ai_model` in `session_templates` (default
`gemini-2.5-pro`); operators pick it on the Upload form's AI Model select, and the org
default is set in `org_settings`. Pipeline `direct` sends media to Gemini multimodal;
`enhanced` runs STT first then Gemini.
**Supporting Evidence:** session_templates model column; upload form select; ingest routing.
**Source Files:** migrations/009_session_templates.sql ([L36](../../migrations/009_session_templates.sql#L36)); frontend/src/views/UploadView.vue ([L429-436](../../frontend/src/views/UploadView.vue#L429)); app/tasks/ingest.py ([L141-193](../../app/tasks/ingest.py#L141))
**API References:** POST /v1/sessions
**Database References:** session_templates, org_settings

### Q2. What guards against runaway transcription cost from oversized media?
**Verified Answer:** A configured 180-minute duration cap (`MAX_VIDEO_DURATION_MINUTES`)
exists, but it only triggers when the client supplies `duration_sec`, which the Upload form
does not send — so it is not an effective cost guard from that surface today (PARTIALLY
IMPLEMENTED). The per-user/queue concurrency caps bound parallel load. No byte-size cap is
enforced (IMPLEMENTATION NOT FOUND).
**Supporting Evidence:** duration check + missing client value; concurrency caps.
**Source Files:** app/middleware/rate_limit.py ([L119-129](../../app/middleware/rate_limit.py#L119), [L33-59](../../app/middleware/rate_limit.py#L33)); frontend/src/views/UploadView.vue ([L233-239](../../frontend/src/views/UploadView.vue#L233)); app/config.py ([L46-49](../../app/config.py#L46))
**API References:** POST /v1/gcs/upload-complete
**Database References:** none

---

## Source Verification
- **Files Used:** app/api/gcs_upload.py, app/api/add_to_session.py, app/services/gcs.py, app/tasks/ingest.py, app/tasks/upload_watchdog.py, app/middleware/rate_limit.py, app/config.py, app/api/sessions.py, frontend/src/views/UploadView.vue, frontend/src/components/session/AddFileModal.vue, frontend/src/router/index.ts, migrations/001_init.sql, migrations/009_session_templates.sql, migrations/011_manifest.sql, migrations/027_default_gcs_upload_backend.sql, migrations/035_drop_sessions_code_unique.sql
- **Components Used:** UploadView.vue, AddFileModal.vue, SessionDetailView.vue
- **APIs Used:** POST /v1/sessions, POST /v1/gcs/upload-url, POST /v1/gcs/upload-complete, GET /v1/sessions/{id}/missing, POST /v1/sessions/{id}/add/signed-url, POST /v1/sessions/{id}/add/slides, POST /v1/sessions/{id}/add/chat, POST /v1/sessions/{id}/add/manifest, POST /v1/diag/reingest/{id}
- **Database Tables Used:** sessions, sources, session_templates, templates, session_speakers, speakers, session_slide_resources, polls, poll_options, chat_messages, slides, segments, audit_events, session_audit, org_settings
- **Permission Logic Used:** JWT presence only (CurrentUser); no role gate on this module. Repo-wide admin gate (LEGACY_ADMIN_EMAIL + client-side adminOnly guard) does not apply here.
- **Confidence Score:** High — every answer cites a verified source line; unenforced/uncertain behaviors are tagged PARTIALLY IMPLEMENTED / IMPLEMENTATION NOT FOUND.
- **Evidence Links:** [gcs_upload.py:110-219](../../app/api/gcs_upload.py#L110), [gcs.py:57-90](../../app/services/gcs.py#L57), [ingest.py:32-206](../../app/tasks/ingest.py#L32), [rate_limit.py:33-129](../../app/middleware/rate_limit.py#L33), [UploadView.vue:199-255](../../frontend/src/views/UploadView.vue#L199), [add_to_session.py:450-553](../../app/api/add_to_session.py#L450)
