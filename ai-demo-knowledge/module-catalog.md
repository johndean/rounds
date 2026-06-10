# rounds.vin — Module Catalog

> The 18 modules of rounds.vin, each with a one-paragraph summary and its routes.
> Module boundaries match the per-area spec files in `docs/product/` and
> `docs/technical/`. Backend route paths are verified against `app/api/*.py`
> (router prefixes + decorators); frontend routes against
> [frontend/src/router/index.ts](../frontend/src/router/index.ts). Links relative
> to `ai-demo-knowledge/`. Unproven claims tagged `NOT VERIFIED IN CODE`.

A "route" below means either a backend API path (`/v1/...`) or a frontend hash
route (`#/...`). Unless noted, every backend route requires a JWT
(`CurrentUser`); admin-gated routes are called out explicitly. The admin gate is
the hardcoded `LEGACY_ADMIN_EMAIL` (`johndean@vin.com`) check — not a role
([app/security/roles.py:54-92](../app/security/roles.py#L54)).

---

## 1. Authentication
Username (email) + password login that issues an 8-hour HS256 JWT bearer token.
Credentials verify against the bcrypt-hashed `auth_users` table with a
constant-time env-CSV fallback; `get_current_user` validates the token and that
the user is still active on every protected request. No role is loaded.
- **Backend:** `POST /v1/auth/login`, `GET /v1/auth/me`
  ([app/api/auth.py:15-34](../app/api/auth.py#L15)).
- **Frontend:** `#/login` (public) ([frontend/src/router/index.ts:29](../frontend/src/router/index.ts#L29)).
- **Spec:** [docs/product/authentication-product-spec.md](../docs/product/authentication-product-spec.md), [docs/technical/authentication-technical-spec.md](../docs/technical/authentication-technical-spec.md).

## 2. Dashboard
The default landing screen: a KPI strip, a "Your Queue" shortlist (three most
recent sessions globally), a two-row pipeline visualization (7-step AI pipeline +
8-stage SOP), and lower operations widgets. It loads `GET /v1/sessions` and
`GET /v1/sop/dashboard-summary` on mount; several widgets render zero/empty
chrome because their aggregate endpoints do not exist yet. Pipeline rows act as
deep-link filters into the sessions list.
- **Backend:** consumes `GET /v1/sessions`, `GET /v1/sop/dashboard-summary`
  ([app/api/sop.py:279](../app/api/sop.py#L279)).
- **Frontend:** `#/dashboard` (and `/` redirects here) ([frontend/src/router/index.ts:28-30](../frontend/src/router/index.ts#L28)).
- **Spec:** [docs/product/dashboard-product-spec.md](../docs/product/dashboard-product-spec.md).

## 3. Sessions
The session list + per-session detail. Lists non-deleted sessions with optional
filters by SOP stage (`?stage=`), AI status (`?ai=`), and free text (`?f=`);
creating a session also writes the matching `session_templates` row carrying the
pipeline routing chosen at upload. Includes soft-delete, restore, permanent
delete, deleted-list, stage-assignee management, pipeline-config, audit-log, and
failure-reason. Soft-delete/restore/permanent-delete and the deleted list are
admin-gated (`require_admin`); permanent delete is the strictest.
- **Backend (prefix `/v1/sessions`):** `GET ""`, `POST ""`, `GET /deleted` (admin),
  `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/restore` (admin),
  `DELETE /{id}/permanent` (admin), `GET /{id}/audit-log`,
  `GET /{id}/pipeline-config`, `GET /{id}/stage-assignees`,
  `PUT /{id}/stage-assignees/{stage}`, `GET /{id}/failure-reason`
  ([app/api/sessions.py:138-753](../app/api/sessions.py#L138)).
- **Frontend:** `#/sessions`, `#/s/:id` ([frontend/src/router/index.ts:31-32](../frontend/src/router/index.ts#L31)).
- **Spec:** [docs/product/sessions-product-spec.md](../docs/product/sessions-product-spec.md).

## 4. Upload & Ingest
Two-step upload: request a 60-minute v4 signed PUT URL, upload media to GCS,
then call upload-complete, which validates files, enforces the R7 scope
invariant, inserts `sources`, reserves the rate-limit slot, parses manifest/chat
text, and enqueues ingest. "Add to session" lets you attach more media (slides,
chat, manifest) to an existing session after ingest.
- **Backend:** `POST /v1/gcs/upload-url`, `POST /v1/gcs/upload-complete`
  ([app/api/gcs_upload.py:69-110](../app/api/gcs_upload.py#L69));
  `GET /v1/sessions/{id}/missing`, `POST /v1/sessions/{id}/add/signed-url`,
  `/add/slides`, `/add/chat`, `/add/manifest`
  ([app/api/add_to_session.py:228-711](../app/api/add_to_session.py#L228)).
- **Frontend:** `#/upload` ([frontend/src/router/index.ts:33](../frontend/src/router/index.ts#L33)).
- **Spec:** [docs/product/upload-ingest-product-spec.md](../docs/product/upload-ingest-product-spec.md).

## 5. Processing Pipeline
The Celery DAG that drives a session from `uploading` to `ready`: ingest routes
the pipeline (`direct` vs `standard`/`enhanced`), fans out frame/slide
extraction, and chains transcribe → anchor → normalize → fusion → align →
finalize (or Gemini multimodal for direct). The only frontend surface is the
ProcessingView, which shows live progress over WebSocket and redirects to the
editor when `ready`.
- **Backend:** driven by `enqueue_ingest` from upload-complete; recovery via
  `/v1/diag/reingest|realign|abort-session/{id}`
  ([docs/technical/processing-pipeline-technical-spec.md:116-120](../docs/technical/processing-pipeline-technical-spec.md#L116)).
- **Frontend:** `#/p/:id` ([frontend/src/router/index.ts:38](../frontend/src/router/index.ts#L38)).
- **Spec:** [docs/product/processing-pipeline-product-spec.md](../docs/product/processing-pipeline-product-spec.md), [docs/technical/processing-pipeline-technical-spec.md](../docs/technical/processing-pipeline-technical-spec.md).

## 6. Editor
The single-session correction workspace at `#/e/:id`: a five-column grid (video +
slide list / transcript-STT-discrepancies-audit center / Active Slide + Admin/
Chat/Polls right rail). On mount it fetches eleven data sources in parallel. It
supports inline segment editing with autosave, slide reassignment, speaker
reassignment, side-by-side STT comparison, and export — all writes flow through
the append-only correction ledger.
- **Backend:** segments, corrections, discrepancies, word_alignment, locks,
  session_resources, exports (see those modules).
- **Frontend:** `#/e/:id` (+ `/e/:id/sop`, `/e/:id/audit`)
  ([frontend/src/router/index.ts:34-36](../frontend/src/router/index.ts#L34)).
- **Spec:** [docs/product/editor-product-spec.md](../docs/product/editor-product-spec.md), [docs/technical/editor-technical-spec.md](../docs/technical/editor-technical-spec.md).

## 7. Corrections & Audit
The append-only correction ledger behind the editor. Every text/slide/speaker
edit appends a correction row; undo/redo move a `sequence_number` pointer rather
than mutating rows. Includes find-replace, a review queue, and (behind the
`SPLIT_MERGE_ENABLED` flag) structural segment split/merge. The audit module
exposes the org-wide and per-session correction history.
- **Backend (prefix `/v1/sessions`):** `POST /{id}/corrections`,
  `POST /{id}/find-replace`, `GET /{id}/corrections`,
  `POST /{id}/corrections/undo`, `POST /{id}/corrections/redo`,
  `GET /{id}/review-queue` ([app/api/corrections.py:332-978](../app/api/corrections.py#L332));
  `GET /v1/audit`, `GET /v1/audit/sessions/{id}/corrections`
  ([app/api/audit.py:18-45](../app/api/audit.py#L18)).
- **Frontend:** `#/audit`, `#/e/:id/audit` ([frontend/src/router/index.ts:36-41](../frontend/src/router/index.ts#L36)).
- **Spec:** [docs/product/corrections-audit-product-spec.md](../docs/product/corrections-audit-product-spec.md).

## 8. Speakers
Per-session speaker roster (name, role, avatar color), seeded by the AI pipeline
and editable in the editor. Supports listing, creating, patching, and deleting
speakers, plus reassigning a segment's speaker (which can create a new speaker).
- **Backend (prefix `/v1/sessions/{id}`):** `GET /speakers`, `POST /speakers`,
  `PATCH /speakers/{speaker_id}`, `DELETE /speakers/{speaker_id}`,
  `POST /segments/{segment_id}/speaker-reassign`
  ([app/api/session_resources.py:206-318](../app/api/session_resources.py#L206)).
- **Frontend:** inside the Editor right rail (`#/e/:id`).
- **Spec:** [docs/product/speakers-product-spec.md](../docs/product/speakers-product-spec.md).

## 9. Slides & Video Sync
Slide extraction (PDF/PPTX → slides + bullets + thumbnails) and the timeline that
aligns transcript segments to slides via the fusion + alignment engines.
Surfaces slides, segment→slide reassignment, media signed-URL playback, and
re-extraction of selected pages. The editor uses a captioned/karaoke playhead
synced to the video.
- **Backend (prefix `/v1/sessions/{id}`):** `GET /slides`,
  `POST /slides/re-extract`, `GET /media-url`, `GET /sources`,
  `GET /words` ([app/api/session_resources.py:39-461](../app/api/session_resources.py#L39));
  segment reassignment `POST /v1/sessions/{id}/segments/{segment_id}/reassign`
  ([app/api/segments.py:224](../app/api/segments.py#L224)).
- **Frontend:** Editor (`#/e/:id`); viewer `#/v/:id`
  ([frontend/src/router/index.ts:37](../frontend/src/router/index.ts#L37)).
- **Spec:** [docs/product/slides-video-sync-product-spec.md](../docs/product/slides-video-sync-product-spec.md).

## 10. Chat & Polls
Imported webinar chat messages and polls, which can be re-ordered and anchored
onto transcript segments. Polls can be auto-placed by the pipeline; both chat and
polls render as cards in the editor right rail. Includes chat participant
listing and per-message edits.
- **Backend (prefix `/v1/sessions/{id}`):** `GET /chat`, `PATCH /chat/order`,
  `PATCH /chat/{message_id}`, `GET /chat-participants`, `GET /polls`,
  `PATCH /polls/order`, `PATCH /polls/{poll_id}/anchor`
  ([app/api/session_resources.py:499-795](../app/api/session_resources.py#L499)).
- **Frontend:** Editor right rail (`#/e/:id`).
- **Spec:** [docs/product/chat-polls-product-spec.md](../docs/product/chat-polls-product-spec.md).

## 11. Quality & Discrepancies
The AI-accuracy surface: LCS-detected diffs between the AI-normalized text and
the raw Google STT reference, classified by a Gemini classify task as meaningful
vs. noise. The editor shows a side-by-side AI ↔ STT comparison and word-level
alignment. The discrepancy list reports a classification status
(complete/partial/pending).
- **Backend:** `GET /v1/sessions/{id}/discrepancies`
  ([app/api/discrepancies.py:49](../app/api/discrepancies.py#L49));
  `GET /v1/sessions/{id}/word-alignment`
  ([app/api/word_alignment.py:54](../app/api/word_alignment.py#L54)).
- **Frontend:** Editor center pane (`#/e/:id`).
- **Spec:** [docs/product/quality-discrepancies-product-spec.md](../docs/product/quality-discrepancies-product-spec.md).

## 12. SOP Workflow
The 8-stage editorial/medical "Standard Operating Procedure" control layer that
runs after a transcript is `ready`:
`prep → copy_draft → medical → copy_final → cms → captions → qa → complete`,
forward-only (one stage at a time). Each stage has a default SLA in hours,
assignees (person or group), blockers, and stage-scoped annotations
(note/override/blocker). A global dashboard-summary aggregates per-stage counts.
- **Backend (prefix `/v1/sessions/{id}/sop`):** `GET ""`, `POST /advance`,
  `POST /assign`, `PATCH /annotations`, `POST /checks/resolve`
  ([app/api/sop.py:93-250](../app/api/sop.py#L93)); global
  `GET /v1/sop/dashboard-summary` ([app/api/sop.py:279](../app/api/sop.py#L279)).
- **Frontend:** `#/e/:id/sop` ([frontend/src/router/index.ts:35](../frontend/src/router/index.ts#L35)).
- **Spec:** [docs/product/sop-workflow-product-spec.md](../docs/product/sop-workflow-product-spec.md).

## 13. Improvements
A master/detail backlog for product enhancements, bug reports, and operator
suggestions about the Rounds app itself. Each record has a title, description,
type/area, priority, risk, status, and four optional markdown "wizard" payloads
(requirements/implementation/testing/review). One shared `improvements` table —
no per-tenant scoping. Any authenticated user can file one.
- **Backend (prefix `/v1/improvements`):** `GET ""`, `POST ""`, `GET /{id}`,
  `PUT /{id}/wizard/{step}`, `PATCH /{id}`, `DELETE /{id}`
  ([app/api/improvements.py:76-179](../app/api/improvements.py#L76)).
- **Frontend:** `#/improvements` ([frontend/src/router/index.ts:39](../frontend/src/router/index.ts#L39)).
- **Spec:** [docs/product/improvements-product-spec.md](../docs/product/improvements-product-spec.md).

## 14. Exports & Artifacts
On-demand generation of downloadable transcript artifacts (`txt`, `srt`, `vtt`,
`docx`, `html`, `zip`) streamed back as file downloads, plus a cache-friendly
WebVTT caption track for the in-app player. A third backend surface — caption
burn-in to MP4 via ffmpeg — exists but has no wired UI.
- **Backend:** `GET /v1/sessions/{id}/exports/{format}`,
  `GET /v1/sessions/{id}/captions.vtt`
  ([app/api/exports.py:41-120](../app/api/exports.py#L41)); burn-in
  `POST /v1/sessions/{id}/captions/burn`, `GET /v1/sessions/{id}/captioned-video`
  ([app/api/session_resources.py:92-130](../app/api/session_resources.py#L92)).
- **Frontend:** Editor download menu (`#/e/:id`).
- **Spec:** [docs/product/exports-artifacts-product-spec.md](../docs/product/exports-artifacts-product-spec.md).

## 15. Settings
Operator-configurable app data: org settings key/value, people, groups (+
membership), session types (+ type→stage assignee defaults), templates, the
macro export, and an `auth-users` admin surface (create/update/reset-password/
delete). Most mutating routes are admin-gated (`require_admin`).
- **Backend (prefix `/v1/settings`):** `GET ""`, `PUT /{key}`, people CRUD,
  groups CRUD + members, types CRUD (admin), `GET/PUT /types/{id}/assignees`
  (admin), `auth-users` CRUD, `GET /export/macro`, templates CRUD
  ([app/api/settings.py:67-1011](../app/api/settings.py#L67)).
- **Frontend:** `#/settings/:section?` ([frontend/src/router/index.ts:40](../frontend/src/router/index.ts#L40)).
- **Spec:** [docs/product/settings-product-spec.md](../docs/product/settings-product-spec.md).

## 16. Diagnostics & Operator Tools
13 operator-only diagnostic + manual-rescue endpoints under `/v1/diag/*` with no
UI surface (curl/Postman tools): read-only probes (gcs, classify-route,
gcs-checks), per-session rescue (reingest, realign, init-session-stages,
autoplace-polls, abort-session), queue/task surgery (flush-celery-queue,
revoke-task, sop-check), and auth recovery (clear-rate-limit-slots,
reseed-auth-users). All require a JWT; only reseed and gcs-checks add the inline
hardcoded-email check.
- **Backend (prefix `/v1/diag`):** see [app/api/diagnostics.py:35-624](../app/api/diagnostics.py#L35).
- **Frontend:** none for `/v1/diag/*`. The `#/gcs` view is a related read surface
  ([frontend/src/router/index.ts:42](../frontend/src/router/index.ts#L42)).
- **Spec:** [docs/product/diagnostics-operator-tools-product-spec.md](../docs/product/diagnostics-operator-tools-product-spec.md).

## 17. Help Center
The in-app help drawer (This page / FAQ / Ask AI tabs, any signed-in user) plus
an admin-only help-article CMS at `#/admin/help` (author/edit/publish/archive,
version history, CC-Rounds compliance meter, coverage report, AI bulk ops). Ask
AI grounds questions against an in-process help corpus and answers with Gemini;
it is gated by the backend `HELP_ASK_AI_ENABLED` flag.
- **Backend (prefix `/v1/help`):** `POST /ask`, `GET /articles`,
  `GET/POST/PATCH /articles...` (admin writes), `GET /coverage`, `GET /search`,
  `POST /admin/bulk-publish` and other admin AI ops
  ([app/api/help.py:164-947](../app/api/help.py#L164)).
- **Frontend:** drawer on any route; `#/admin/help` (`meta.adminOnly`)
  ([frontend/src/router/index.ts:44](../frontend/src/router/index.ts#L44)).
- **Spec:** [docs/product/help-center-product-spec.md](../docs/product/help-center-product-spec.md).

## 18. Notifications & Email
SMTP email plumbing: email templates CRUD with resolution, an admin email-debug
surface (config, connectivity test, send, attempts log), and SOP deadline
notification emails sent by the hourly `sop_check_deadlines_task` when
`SOP_DEADLINE_EMAIL_ENABLED` is on. Template and email-debug routes are
admin-gated.
- **Backend:** `/v1/email-templates` CRUD + `POST /resolve`
  ([app/api/email_templates.py:165-316](../app/api/email_templates.py#L165));
  `/v1/admin/email-debug/config|connectivity|send|attempts`
  ([app/api/email_debug.py:64-307](../app/api/email_debug.py#L64)).
- **Frontend:** within Settings (`#/settings/:section?`). **NOT VERIFIED IN
  CODE** which settings section renders the email-debug UI.
- **Spec:** [docs/product/notifications-email-product-spec.md](../docs/product/notifications-email-product-spec.md).

---

## Additional frontend routes (not standalone modules)
- `#/queue` — per-user work queue: sessions where the logged-in user is the
  assignee of the current SOP stage, longest-waiting first
  (`GET /v1/queue/mine`, [app/api/queue.py:45](../app/api/queue.py#L45)). Part of
  the Dashboard module's spec.
- `#/gcs` — GCS diagnostics read view (Diagnostics module).
- `#/v/:id` — read-only viewer (Slides & Video Sync / Editor surface).
- Session locks (`/v1/sessions/{id}/lock/*`,
  [app/api/locks.py:99-218](../app/api/locks.py#L99)) back the editor's
  one-editor-at-a-time TTL lock (Editor module).

## Source Verification
- **Files Used:** app/main.py, app/api/auth.py, app/api/sessions.py, app/api/gcs_upload.py, app/api/add_to_session.py, app/api/corrections.py, app/api/audit.py, app/api/session_resources.py, app/api/segments.py, app/api/discrepancies.py, app/api/word_alignment.py, app/api/sop.py, app/api/improvements.py, app/api/exports.py, app/api/settings.py, app/api/diagnostics.py, app/api/help.py, app/api/email_templates.py, app/api/email_debug.py, app/api/queue.py, app/api/locks.py, app/security/roles.py, frontend/src/router/index.ts, docs/product/*, docs/technical/*
- **Components Used:** ProcessingView, EditorView, HelpEditor, ImprovementsView, DashboardView, QueueView (referenced via specs)
- **APIs Used:** all `/v1/*` routes enumerated above (verified from router prefixes + decorators)
- **Database Tables Used:** sessions, session_templates, sources, segments, words, slides, bullets, speakers, alignments, slide_time_ranges, transcription_discrepancies, word_alignment, corrections, sop_state, session_stage_assignees, improvements, help_articles, email_templates, auth_users, audit_events, chat_messages, polls (see processing-pipeline-technical-spec.md + per-module specs)
- **Permission Logic Used:** JWT presence on all routes; LEGACY_ADMIN_EMAIL hardcoded gate via require_admin on sessions delete/restore/permanent/deleted, settings mutations, help writes, email-templates, email-debug; client-side adminOnly guard on #/admin/help
- **Confidence Score:** High — every route enumerated from router decorators; module boundaries match shipped spec files.
- **Evidence Links:** [app/main.py:212-233](../app/main.py#L212), [frontend/src/router/index.ts:27-45](../frontend/src/router/index.ts#L27), [app/api/sop.py:24](../app/api/sop.py#L24), [app/api/diagnostics.py:35-624](../app/api/diagnostics.py#L35)
