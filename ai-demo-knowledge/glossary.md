# rounds.vin — Glossary (general terms)

> General/industry terms as they are used in the rounds.vin codebase. For terms
> unique to rounds.vin's AI pipeline (segment, anchor, fusion, drift, IIL, SOP
> stage, etc.) see [terminology.md](./terminology.md). Definitions are grounded
> in how each term actually appears in this repo, with evidence. Links relative
> to `ai-demo-knowledge/`. Unproven claims tagged `NOT VERIFIED IN CODE`.

## VIN
Veterinary Information Network — the organization rounds.vin serves. rounds.vin
is "transcript software for VIN"
([docs/product/README.md:3-4](../docs/product/README.md#L3)).

## Transcript
The text rendering of a recorded session's spoken content, broken into segments
with timestamps, speaker labels, and slide alignment. The product's core output.

## STT (Speech-to-Text)
Automatic speech recognition. rounds.vin uses **Google Speech-to-Text**
(`long_running_recognize`, LINEAR16 / 16kHz / en-US, word offsets + auto
punctuation) as the raw transcription backend and as a reference for discrepancy
detection ([docs/technical/processing-pipeline-technical-spec.md:292-294](../docs/technical/processing-pipeline-technical-spec.md#L292)).

## Gemini
Google's multimodal LLM. Used for the direct/enhanced AI transcript pass
(`call_gemini_multimodal` / `call_gemini_text`), for discrepancy classification
(`GEMINI_CLASSIFY_MODEL` = `gemini-2.5-flash-lite`), and for the Help Center "Ask
AI" answers ([docs/technical/processing-pipeline-technical-spec.md:295-299](../docs/technical/processing-pipeline-technical-spec.md#L295),
[app/config.py:85](../app/config.py#L85)).

## LLM (Large Language Model)
The general category for the Gemini models above. The `llm_client` engine wraps
Gemini calls and categorizes failures (e.g. `gemini_context_overflow`)
([app/engines/llm_client.py](../app/engines/llm_client.py)).

## Vertex AI
Google's managed ML platform. rounds.vin has a `VERTEX_AI_CLASSIFY_ENABLED` flag
(default false) and `VERTEX_AI_LOCATION` config to optionally route
classification through Vertex instead of the Gemini dev API; the active route is
reported by `GET /v1/diag/classify-route`
([app/config.py:86-87](../app/config.py#L86),
[app/api/diagnostics.py:66](../app/api/diagnostics.py#L66)).

## GCS (Google Cloud Storage)
The object store for uploaded media, extracted thumbnails, and generated
artifacts. Uploads use 60-minute v4 signed PUT URLs and are scope-restricted to
`gs://<bucket>/sessions/<id>/` (the R7 invariant)
([app/api/gcs_upload.py:69](../app/api/gcs_upload.py#L69),
[docs/technical/processing-pipeline-technical-spec.md:288-290](../docs/technical/processing-pipeline-technical-spec.md#L288)).

## Signed URL
A time-limited, pre-authorized URL that lets the browser upload directly to GCS
without proxying through the API. rounds.vin issues v4 PUT signed URLs valid 60
minutes ([app/api/gcs_upload.py:69-86](../app/api/gcs_upload.py#L69)).

## FastAPI
The Python async web framework the backend is built on. App object + routers in
[app/main.py](../app/main.py).

## SQLAlchemy
The Python ORM / SQL toolkit. Request-path code uses the async engine (asyncpg);
Celery tasks open their own synchronous engine per invocation
([docs/technical/processing-pipeline-technical-spec.md:43-45](../docs/technical/processing-pipeline-technical-spec.md#L43)).

## Postgres / PostgreSQL
The relational database. rounds.vin runs its own isolated Postgres (Railway
plugin); the `DATABASE_URL` is normalized to `postgresql+asyncpg://`
([app/config.py:137-149](../app/config.py#L137)).

## Celery
The distributed task queue running all heavy processing (transcription, slide
extraction, fusion, alignment, classification, SOP deadline checks). Single
queue, one worker replica, Beat embedded for scheduled jobs
([docs/technical/processing-pipeline-technical-spec.md:41-42](../docs/technical/processing-pipeline-technical-spec.md#L41)).

## Celery Beat
Celery's periodic-task scheduler. rounds.vin schedules `upload-watchdog` (every
60s, default-off) and `sop-check-deadlines` (every 3600s)
([docs/technical/processing-pipeline-technical-spec.md:316-320](../docs/technical/processing-pipeline-technical-spec.md#L316)).

## Redis
In-memory store used as the Celery broker/backend, the inter-task signal hand-off
(frame/anchor outputs with 24h TTL), the WebSocket pub/sub bridge, and the
rate-limit slot sets ([app/main.py:93-97](../app/main.py#L93),
[docs/technical/processing-pipeline-technical-spec.md:219-227](../docs/technical/processing-pipeline-technical-spec.md#L219)).

## JWT (JSON Web Token)
The bearer token format used for auth. rounds.vin issues HS256 JWTs signed with
`API_SECRET_KEY`, with `sub` = the user email and an 8-hour expiry
([app/auth.py:153-158](../app/auth.py#L153)).

## bcrypt
The password-hashing function. `auth_users` stores bcrypt password hashes; login
verification is ~50ms by design
([app/auth.py:113-127](../app/auth.py#L113)).

## OAuth2 password flow
The login mechanism: `POST /v1/auth/login` consumes an
`OAuth2PasswordRequestForm` (username + password) and the API uses
`OAuth2PasswordBearer` to extract the token on protected routes
([app/api/auth.py:16](../app/api/auth.py#L16),
[app/auth.py:161](../app/auth.py#L161)).

## SPA (Single-Page Application)
The Vue 3 frontend, served as static files by the same FastAPI process in
production with an SPA fallback to `index.html`
([app/main.py:249-262](../app/main.py#L249)).

## Hash routing
Client-side routing where the route lives after `#` in the URL
(`createWebHashHistory`). All rounds.vin frontend routes are hash routes
([frontend/src/router/index.ts:22-25](../frontend/src/router/index.ts#L22)).

## WebSocket
A persistent bidirectional connection used to push live processing updates to the
browser. Endpoint `/v1/ws/sessions/{session_id}` streams events like
`processing_update` and `session_failed`
([app/main.py:192-208](../app/main.py#L192)).

## Idempotency key
A client-supplied `Idempotency-Key` header that lets the middleware replay a
cached response instead of re-executing a request (TTL 86400s default)
([app/main.py:127-131](../app/main.py#L127),
[app/config.py:77](../app/config.py#L77)).

## Rate limiting / quota
Per-user concurrency limits: a user may have at most `MAX_CONCURRENT_SESSIONS`
(3) sessions in flight, and the global queue is capped at `MAX_QUEUE_LENGTH`
(10). Slots are reserved on upload-complete and released on completion/failure
([app/config.py:46-47](../app/config.py#L46)).

## SLA (Service-Level Agreement)
A per-stage deadline (in hours) for the SOP workflow; a session past it is
"overdue." Defaults range from 8h (prep, qa) to 48h (medical)
([app/api/sop.py:29-38](../app/api/sop.py#L29)).

## CMS (Content Management System)
The downstream system that finished transcripts are exported to (e.g. a
macro-compatible Word doc, or a publish-ready HTML body). `cms` is also one of
the 8 SOP stages ([docs/product/README.md:4](../docs/product/README.md#L4),
[app/api/sop.py:24](../app/api/sop.py#L24)).

## SRT / WebVTT (.srt / .vtt)
Caption/subtitle file formats. rounds.vin exports SubRip (`srt`) and WebVTT
(`vtt`) captions; the in-app player consumes a cache-friendly `captions.vtt`
track ([app/api/exports.py:41-120](../app/api/exports.py#L41)).

## DOCX / HTML / TXT / ZIP
Export artifact formats produced on demand from a session's stored data by the
artifact transformer engine
([app/api/exports.py:41](../app/api/exports.py#L41),
[app/engines/artifact_transformer.py](../app/engines/artifact_transformer.py)).

## FFmpeg / ffprobe
Command-line media tools used for audio chunking, frame sampling, stream/duration
probing, and caption burn-in
([docs/technical/processing-pipeline-technical-spec.md:300-302](../docs/technical/processing-pipeline-technical-spec.md#L300)).

## OpenCV / NumPy
Computer-vision/array libraries used by `frame_task` to detect visual change
between sampled frames (grayscale absdiff + histogram distance)
([docs/technical/processing-pipeline-technical-spec.md:303-304](../docs/technical/processing-pipeline-technical-spec.md#L303)).

## PyMuPDF (fitz) / python-pptx
Document libraries used to extract slides, bullets, and thumbnails from PDF and
PPTX slide decks
([docs/technical/processing-pipeline-technical-spec.md:305-306](../docs/technical/processing-pipeline-technical-spec.md#L305)).

## LCS (Longest Common Subsequence)
The diff algorithm used to detect discrepancies between AI-normalized text and
raw STT text
([docs/technical/processing-pipeline-technical-spec.md:85](../docs/technical/processing-pipeline-technical-spec.md#L85)).

## SMTP
The email-sending protocol. Used for SOP deadline notification emails and the
admin email-debug surface; configured via `SMTP_*` env vars (currently shared
with the predecessor MIC project)
([app/api/email_debug.py:82](../app/api/email_debug.py#L82)).

## Soft delete
Marking a session deleted via `deleted_at` (hidden from the default list) rather
than removing the row; admins can restore or permanently delete
([app/api/sessions.py:621-707](../app/api/sessions.py#L621)).

## Migration
A versioned SQL schema change in `migrations/` (e.g. migration 045 added
`auth_users.role`, 053 added `help_articles`). Applied via `scripts/migrate.py`
(referenced) ([app/security/roles.py:11-12](../app/security/roles.py#L11)).

## Railway
The PaaS host for the api + worker services and the isolated Postgres/Redis
plugins; production deploys auto-trigger on push to the production remote
(CLAUDE.md repo guidance). **NOT VERIFIED IN CODE** beyond config references.

## Response envelope
The standard JSON wrapper around every API response —
`{success, data, error, meta}` — applied by the EnvelopeMiddleware
([app/main.py:133-143](../app/main.py#L133)).

## Feature flag
A backend kill-switch read from config and surfaced via `GET /v1/version`.
Examples: `HELP_ASK_AI_ENABLED`, `SPLIT_MERGE_ENABLED`, `UPLOAD_WATCHDOG_ENABLED`,
`SOP_DEADLINE_EMAIL_ENABLED` — all default-off
([app/main.py:183-189](../app/main.py#L183),
[app/config.py:100-134](../app/config.py#L100)).

## Source Verification
- **Files Used:** docs/product/README.md, app/main.py, app/config.py, app/auth.py, app/api/auth.py, app/api/gcs_upload.py, app/api/exports.py, app/api/sop.py, app/api/sessions.py, app/api/email_debug.py, app/api/diagnostics.py, app/engines/llm_client.py, app/engines/artifact_transformer.py, app/security/roles.py, frontend/src/router/index.ts, docs/technical/processing-pipeline-technical-spec.md
- **Components Used:** Vue 3 SPA (referenced)
- **APIs Used:** POST /v1/auth/login, GET /v1/version, WS /v1/ws/sessions/{id}, GET /v1/diag/classify-route, /v1/sessions/{id}/exports/{format}, /v1/sessions/{id}/captions.vtt
- **Database Tables Used:** auth_users, sessions, help_articles (referenced)
- **Permission Logic Used:** JWT (defined as a term); LEGACY_ADMIN_EMAIL referenced
- **Confidence Score:** High — each general term tied to its concrete usage in the repo; Railway deploy mechanics flagged NOT VERIFIED IN CODE.
- **Evidence Links:** [app/config.py:80-134](../app/config.py#L80), [app/main.py:127-208](../app/main.py#L127), [docs/technical/processing-pipeline-technical-spec.md:288-306](../docs/technical/processing-pipeline-technical-spec.md#L288), [app/api/sop.py:24-38](../app/api/sop.py#L24)
