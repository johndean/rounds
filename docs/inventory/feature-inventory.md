# rounds.vin — Master Feature Inventory

Transcript software for VIN (Veterinary Information Network). Operators upload recorded sessions; an AI pipeline produces a first-pass transcript with speaker labels + slide alignment; a workflow (Copy Edit → Medical Review → Publish) finishes it before CMS export.

This document is the master, code-verified inventory of every feature across the 18 functional modules in **this repository**. Every claim below is verified against source files in `app/` and `frontend/src/`. Modules from the originating "CE.VIN" brief (Organizations / Sites / Vendors / Projects) **do not exist here** and are intentionally absent.

## How to read this document

- **Routes** = frontend hash routes from [frontend/src/router/index.ts](../../frontend/src/router/index.ts).
- **API Endpoints** = FastAPI routes registered in [app/main.py](../../app/main.py).
- **Database Tables** = SQL tables defined in [migrations/](../../migrations/) (raw `.sql`, no ORM models in this repo).
- **Permissions** — verified reality: the only live authorization is **JWT presence** plus a hardcoded **`LEGACY_ADMIN_EMAIL` gate** (`johndean@vin.com`, [app/security/roles.py:54](../../app/security/roles.py#L54)) plus one **client-side `adminOnly` route guard** ([frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)). Role tiers are **NOT** active — see the Permission Model Reality section.
- **Status** — one of: SHIPPED / PARTIALLY IMPLEMENTED / IMPLEMENTATION NOT FOUND.

---

## Permission Model Reality (read this first)

Role-based authorization in this repo is **scaffold-only**. Verified:

1. `app/security/roles.py` exposes `is_admin()` / `require_admin()`. The helper resolves admin in two ways: if a `role=` kwarg is passed it matches `role == "admin"`; **otherwise** it falls back to `user.email == LEGACY_ADMIN_EMAIL` ([app/security/roles.py:88-92](../../app/security/roles.py#L88)).
2. `get_current_user` constructs `User(email=...)` only — the `User` dataclass has a single `email` field ([app/auth.py:36-39](../../app/auth.py#L36)) and `get_current_user` **never reads `auth_users.role`** ([app/auth.py:172-205](../../app/auth.py#L172)).
3. Because no caller passes `role=`, every `require_admin(user, ...)` call collapses to the `LEGACY_ADMIN_EMAIL` email comparison. So although `require_admin` **is** now wired into endpoints (email_templates, email_debug, help, settings, sessions), the **effective** check is still the single hardcoded email.
4. `auth_users.role` exists (migration 045) but is **not consulted** by `get_current_user`.
5. Two diagnostics endpoints hardcode the email check inline rather than via the helper: [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534) and [app/api/diagnostics.py:632](../../app/api/diagnostics.py#L632). The other 11 `/v1/diag/*` routes require only `CurrentUser` (JWT presence).
6. `SESSION_TRASH_ALLOWED = {LEGACY_ADMIN_EMAIL, "carlab@vin.com"}` ([app/api/sessions.py:52](../../app/api/sessions.py#L52)) is a wider allowlist for soft-delete (NOT an admin tier).
7. Client-side: the only `meta.adminOnly` guard is on `/admin/help`, comparing `auth.email !== LEGACY_ADMIN_EMAIL` ([frontend/src/router/index.ts:44,63](../../frontend/src/router/index.ts#L44)). This is UI-only; the server is authoritative on `/v1/help/articles*`.

**Permission shorthand used below:**
- **JWT** = requires a valid bearer token (`CurrentUser` dependency), no further gate.
- **JWT + ADMIN gate** = `require_admin(user)` → effectively `email == johndean@vin.com`.
- **JWT + TRASH allowlist** = `SESSION_TRASH_ALLOWED` membership.
- **JWT + inline-email gate** = hardcoded `user.email == "johndean@vin.com"` at the callsite.
- **client adminOnly** = the router guard (UI-only).

---

## Feature Flags (defaults from [app/config.py](../../app/config.py))

| Flag | Default | Read by | Effect when OFF (default) |
|---|---|---|---|
| `UPLOAD_WATCHDOG_ENABLED` | `False` | [app/tasks/upload_watchdog.py:67](../../app/tasks/upload_watchdog.py#L67) | Watchdog beat task returns early; no stuck-upload recovery. ([app/config.py:100](../../app/config.py#L100)) |
| `SOP_DEADLINE_EMAIL_ENABLED` | `False` | [app/tasks/sop_tasks.py:542](../../app/tasks/sop_tasks.py#L542) | `sop_check_deadlines_task` computes overdue but sends no SMTP email. ([app/config.py:110](../../app/config.py#L110)) |
| `HELP_ASK_AI_ENABLED` | `False` | [app/api/help.py:174](../../app/api/help.py#L174), [app/main.py:183](../../app/main.py#L183) | `POST /v1/help/ask` returns 404; `/v1/version` reports `help_ask_ai_enabled:false` and the frontend hides the Ask tab. ([app/config.py:121](../../app/config.py#L121)) |
| `SPLIT_MERGE_ENABLED` | `False` | [app/api/corrections.py:362](../../app/api/corrections.py#L362), [app/main.py:188](../../app/main.py#L188) | Split/merge correction op returns 503 `SPLIT_MERGE_DISABLED`; `/v1/version` reports `split_merge_enabled:false` and the frontend hides Split/merge UI. ([app/config.py:134](../../app/config.py#L134)) |
| `VERTEX_AI_CLASSIFY_ENABLED` | `False` | [app/engines/llm_client.py:275](../../app/engines/llm_client.py#L275), [app/api/diagnostics.py:69](../../app/api/diagnostics.py#L69) | Classification routes to `gemini_dev` (Gemini Developer API) instead of Vertex AI. ([app/config.py:86](../../app/config.py#L86)) |

Secondary tuning knobs (not boolean kill-switches): `HELP_ASK_AI_RATE_LIMIT_PER_HOUR=30` ([app/config.py:123](../../app/config.py#L123)), `UPLOAD_STUCK_THRESHOLD_SEC=300`, `UPLOAD_WATCHDOG_INTERVAL_SEC=60`, `UPLOAD_WATCHDOG_COOLDOWN_SEC=600` ([app/config.py:101-111](../../app/config.py#L101)).

> Note on `VITE_HELP_ASK_AI_ENABLED`: a Phase-0 build-time placeholder flag. It is **NOT plumbed through the Dockerfile** and is intentionally not consulted by the runtime frontend ([app/config.py:118-120](../../app/config.py#L118)). Do not treat it as live.

---

## Module 1 — Authentication

- **Purpose:** JWT bearer-token login backed by the `auth_users` table (bcrypt), with an AUTH_USERS env-CSV fallback for DR/cutover.
- **Routes:** `#/login` (public).
- **Screens:** Login.
- **Components:** [LoginView.vue](../../frontend/src/views/LoginView.vue).
- **Database Tables:** `auth_users` (migration 045).
- **API Endpoints:** `POST /v1/auth/login` ([app/api/auth.py:15](../../app/api/auth.py#L15)), `GET /v1/auth/me` ([app/api/auth.py:31](../../app/api/auth.py#L31)).
- **Permissions:** login is public; `/v1/auth/me` requires JWT. Tokens: HS256, signed with `API_SECRET_KEY`, expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 480 = 8h).
- **Dependencies:** `auth_users` table seeded on boot from `AUTH_USERS` env CSV ([app/main.py:73-91](../../app/main.py#L73)); bcrypt via `app/services/auth_users.py`.
- **Status:** SHIPPED.
- **Feature Flags:** none.
- **Known Constraints:** `auth_users.role` is stored but never read by `get_current_user`; admin gating is the hardcoded `LEGACY_ADMIN_EMAIL`. `AUTH_USERS` remains plaintext in env (known debt; hashed-at-rest is the table, env CSV is fallback).

## Module 2 — Dashboard

- **Purpose:** Operator landing view; pipeline/stage summary entry point.
- **Routes:** `#/dashboard` (and `/` redirect).
- **Screens:** Dashboard.
- **Components:** [DashboardView.vue](../../frontend/src/views/DashboardView.vue); [Sparkline.vue](../../frontend/src/components/dashboard/Sparkline.vue).
- **Database Tables:** reads `sessions`, `sop_state` (via the SOP dashboard-summary endpoint).
- **API Endpoints:** no dashboard-specific router. Consumes `GET /v1/sessions` ([app/api/sessions.py:138](../../app/api/sessions.py#L138)) and `GET /v1/sop/dashboard-summary` ([app/api/sop.py:279](../../app/api/sop.py#L279)). **A dedicated dashboard API is IMPLEMENTATION NOT FOUND** (no `app/api/dashboard.py`).
- **Permissions:** JWT.
- **Dependencies:** sessions list + SOP stage-summary.
- **Status:** PARTIALLY IMPLEMENTED — view exists and aggregates other modules' endpoints; no dedicated backend.
- **Feature Flags:** none.
- **Known Constraints:** Dashboard analytics depth not verifiable beyond the two endpoints above.

## Module 3 — Session Management

- **Purpose:** List / get / create / soft-delete / restore / purge sessions; stage assignees; pipeline config; audit log; failure reason.
- **Routes:** `#/sessions`, `#/s/:id`.
- **Screens:** Sessions list, Session detail.
- **Components:** [SessionsView.vue](../../frontend/src/views/SessionsView.vue), [SessionDetailView.vue](../../frontend/src/views/SessionDetailView.vue); [StageBadge.vue](../../frontend/src/components/shared/StageBadge.vue), [SessionTextEdit.vue](../../frontend/src/components/session/SessionTextEdit.vue).
- **Database Tables:** `sessions` (001), `session_audit` (010), `session_templates` (009), `session_types` (006), `stage_assignees` (006), `session_stage_assignees` (042).
- **API Endpoints (prefix `/v1/sessions`, [app/api/sessions.py](../../app/api/sessions.py)):** `GET ""` (list), `POST ""` (create), `GET /deleted`, `GET /{id}/audit-log`, `GET /{id}/pipeline-config`, `GET /{id}/stage-assignees`, `PUT /{id}/stage-assignees/{stage}`, `POST /{id}/stage-assignees/apply-type-defaults`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/restore`, `DELETE /{id}/permanent`, `GET /{id}/failure-reason`.
- **Permissions:** JWT for read/create/patch. `GET /deleted`, `POST /{id}/restore`, `DELETE /{id}/permanent` are **JWT + ADMIN gate** via `require_admin` ([sessions.py:276,674,707](../../app/api/sessions.py#L276)). Soft-delete `DELETE /{id}` is gated by `SESSION_TRASH_ALLOWED` (JWT + TRASH allowlist).
- **Dependencies:** state machine ([app/engines/state_machine.py]) for all status mutations (ADR-003); rate limits (`MAX_CONCURRENT_SESSIONS=3`, `MAX_QUEUE_LENGTH=10`).
- **Status:** SHIPPED.
- **Feature Flags:** none.
- **Known Constraints:** No DB-level status CHECK constraint — FSM is Python-only. Soft-delete carve-out for `carlab@vin.com` is explicit and intentional.

## Module 4 — Upload & Ingest (GCS)

- **Purpose:** Signed-URL direct-to-GCS upload, upload-complete handshake that enqueues ingest, R7 scope enforcement.
- **Routes:** `#/upload`.
- **Screens:** Upload.
- **Components:** [UploadView.vue](../../frontend/src/views/UploadView.vue); [GcsView.vue](../../frontend/src/views/GcsView.vue) (debug); [GCSDebug.vue](../../frontend/src/components/settings/GCSDebug.vue).
- **Database Tables:** `sessions`, `sources` (001).
- **API Endpoints:** `POST /v1/gcs/upload-url` ([app/api/gcs_upload.py:69](../../app/api/gcs_upload.py#L69)), `POST /v1/gcs/upload-complete` ([gcs_upload.py:110](../../app/api/gcs_upload.py#L110)).
- **Permissions:** JWT.
- **Dependencies:** GCS service; Celery ingest enqueue; **R7 invariant** — `upload-complete` rejects any `gcs_uri` outside `gs://<bucket>/sessions/<id>/` (`app/services/gcs.py::find_out_of_scope_uri`).
- **Status:** SHIPPED.
- **Feature Flags:** `UPLOAD_WATCHDOG_ENABLED` (default OFF) recovers sessions stuck on `status='uploading'` when the silent enqueue-failure path fires.
- **Known Constraints:** Upload limits: `MAX_UPLOAD_SIZE_MB=2048`, `MAX_VIDEO_DURATION_MINUTES=180`.

## Module 5 — Add-to-Session (supplementary uploads)

- **Purpose:** Add slides / chat / manifest / extra media to an existing session after initial ingest.
- **Routes:** surfaced inside session detail (no dedicated route).
- **Screens:** Add-file modal.
- **Components:** [AddFileModal.vue](../../frontend/src/components/session/AddFileModal.vue).
- **Database Tables:** `sources`, `slides`, `chat_messages`, `session_slide_resources` (011), session manifest tables.
- **API Endpoints (prefix `/v1/sessions`, [app/api/add_to_session.py](../../app/api/add_to_session.py)):** `GET /{id}/missing`, `POST /{id}/add/signed-url`, `POST /{id}/add/slides`, `POST /{id}/add/chat`, `POST /{id}/add/manifest`.
- **Permissions:** JWT.
- **Dependencies:** GCS signed URLs; ingest/slide-extract tasks.
- **Status:** SHIPPED.
- **Feature Flags:** none.
- **Known Constraints:** Same R7 GCS-scope rules apply to add-uploads.

## Module 6 — Processing Pipeline

- **Purpose:** Live processing status view for an in-flight session; AI transcript + slide-alignment pipeline.
- **Routes:** `#/p/:id`.
- **Screens:** Processing.
- **Components:** [ProcessingView.vue](../../frontend/src/views/ProcessingView.vue).
- **Database Tables:** `sessions`, `slide_time_ranges` (013), `alignments` (014), `validation_results` (014), `normalization_results` (012), `replay_log` (013), `artifacts` (018), `instructor_profiles`/`session_patterns`/`key_points_annotations` (019, IIL).
- **API Endpoints:** no dedicated processing router. Live updates flow over the WebSocket `GET /v1/ws/sessions/{session_id}` ([app/main.py:192](../../app/main.py#L192)); status is read via `GET /v1/sessions/{id}`. Operator re-runs via `/v1/diag/*` (reingest/realign).
- **Permissions:** JWT (WS connect requires a live session; auth model for the WS channel is **NOT VERIFIED IN CODE** beyond connect/keep-alive).
- **Dependencies:** Celery workers; STT (`TRANSCRIPTION_BACKEND=google_stt_chunked`, `TRANSCRIPTION_CHUNK_MINUTES=5`); Gemini/Vertex classify; **LOCKED scoring weights** (`FUSION_*`, `ALIGN_*`, `IIL_*` in [app/config.py:51-77](../../app/config.py#L51), pinned by `tests/test_health.py::test_locked_weights_match_audit`).
- **Status:** SHIPPED (pipeline + WS); progress UI present.
- **Feature Flags:** `VERTEX_AI_CLASSIFY_ENABLED` (default OFF → Gemini Developer API).
- **Known Constraints:** Locked weights must not change without coordinated config+test+plan update. WS publishers before the bridge starts have no listeners ([app/main.py:14](../../app/main.py#L14)).

## Module 7 — Editor (Transcript)

- **Purpose:** Core transcript editing surface — segments, slide rail, video strip, speaker editing, polls/chat tabs, discrepancies pane, find/replace, admin tab.
- **Routes:** `#/e/:id`.
- **Screens:** Editor (multi-pane).
- **Components:** [EditorView.vue](../../frontend/src/views/EditorView.vue); [TranscriptPane.vue], [SegmentText.vue], [SlideRail.vue], [VideoStrip.vue], [ActiveSlideCard.vue], [STTPane.vue], [STTSidePanel.vue], [AnchorBlock.vue], [DecisionCard.vue], [DiscrepanciesPane.vue], [DownloadMenu.vue], [FlagLegend.vue], [SpeakerEditPanel.vue], [AdminTab.vue], [AuditTabInline.vue], [ChatTab.vue], [PollsTab.vue] (all under [frontend/src/components/editor/](../../frontend/src/components/editor/)); [FindReplaceModal.vue], [SegmentEditModal.vue] (overlays); [EditorSkeleton.vue].
- **Database Tables:** `segments` (001), `words` (015), `bullets` (016), `speakers` (001), `session_speakers` (011), `correction_ledger` (029), `ledger_pointers` (029).
- **API Endpoints:** Segments (prefix `/v1/sessions/{id}/segments`): `GET ""`, `PATCH /{seg}`, `POST /{seg}/reassign` ([app/api/segments.py](../../app/api/segments.py)). Corrections (prefix `/v1/sessions`): `POST /{id}/corrections`, `POST /{id}/find-replace`, `GET /{id}/corrections`, `POST /{id}/corrections/undo`, `POST /{id}/corrections/redo`, `GET /{id}/review-queue` ([app/api/corrections.py](../../app/api/corrections.py)). Session resources (words/sources/media-url) under [app/api/session_resources.py](../../app/api/session_resources.py).
- **Permissions:** JWT. Edit-conflict prevention via session-lock endpoints (see Module 18).
- **Dependencies:** correction ledger (undo/redo); session locks; WebSocket for live state.
- **Status:** SHIPPED (core); **split/merge structural edit is PARTIALLY IMPLEMENTED behind a flag** (returns 503 when off).
- **Feature Flags:** `SPLIT_MERGE_ENABLED` (default OFF → split/merge correction returns 503 `SPLIT_MERGE_DISABLED` and UI hides the Split/merge affordances).
- **Known Constraints:** Per CLAUDE.md the frontend is an in-progress React→Vue port; pixel parity for Editor is ongoing.

## Module 8 — Speaker Management

- **Purpose:** Manage session speakers; reassign segment speakers; speaker edit panel.
- **Routes:** within `#/e/:id`.
- **Screens:** Speaker edit panel (editor).
- **Components:** [SpeakerEditPanel.vue](../../frontend/src/components/editor/SpeakerEditPanel.vue); [Avatar.vue](../../frontend/src/components/shared/Avatar.vue).
- **Database Tables:** `speakers` (001), `session_speakers` (011).
- **API Endpoints (prefix `/v1/sessions/{id}`, [app/api/session_resources.py](../../app/api/session_resources.py)):** `GET /speakers`, `POST /speakers`, `PATCH /speakers/{speaker_id}`, `DELETE /speakers/{speaker_id}`, `POST /segments/{segment_id}/speaker-reassign`.
- **Permissions:** JWT.
- **Dependencies:** segments module (reassignment writes to segment rows).
- **Status:** SHIPPED.
- **Feature Flags:** none.
- **Known Constraints:** none verified.

## Module 9 — Slides & Video Sync

- **Purpose:** Slide extraction/re-extraction, slide-to-transcript alignment, media URL signing, caption burn-in, captioned-video artifact.
- **Routes:** within `#/e/:id` (slide rail, video strip) and `#/v/:id` (viewer).
- **Screens:** Slide rail, Video strip, Viewer.
- **Components:** [SlideRail.vue], [VideoStrip.vue], [ActiveSlideCard.vue] (editor); [ViewerView.vue](../../frontend/src/views/ViewerView.vue).
- **Database Tables:** `slides` (001), `slide_time_ranges` (013), `session_slide_resources` (011), `alignments` (014), `artifacts` (018), `artifact_versions` (023).
- **API Endpoints (prefix `/v1/sessions/{id}`, [app/api/session_resources.py](../../app/api/session_resources.py)):** `POST /slides/re-extract`, `GET /slides`, `POST /captions/burn`, `GET /captioned-video`, `GET /sources`, `GET /media-url`.
- **Permissions:** JWT.
- **Dependencies:** GCS media; Celery slide-extract / caption-burn tasks; fusion/alignment weights (Module 6).
- **Status:** SHIPPED.
- **Feature Flags:** none.
- **Known Constraints:** Alignment quality governed by LOCKED `ALIGN_*` weights.

## Module 10 — Chat, Polls & Resources

- **Purpose:** Display/edit session chat messages, polls (with anchors and ordering), chat participants.
- **Routes:** within `#/e/:id` (Chat tab, Polls tab).
- **Screens:** Chat tab, Polls tab.
- **Components:** [ChatTab.vue](../../frontend/src/components/editor/ChatTab.vue), [PollsTab.vue](../../frontend/src/components/editor/PollsTab.vue).
- **Database Tables:** `chat_messages` (008, order_index added in 052), `polls` (008), `poll_options` (008).
- **API Endpoints (prefix `/v1/sessions/{id}`, [app/api/session_resources.py](../../app/api/session_resources.py)):** `GET /chat`, `PATCH /chat/order`, `PATCH /chat/{message_id}`, `GET /chat-participants`, `GET /polls`, `PATCH /polls/order`, `PATCH /polls/{poll_id}/anchor`.
- **Permissions:** JWT.
- **Dependencies:** poll auto-placement (backfillable via `/v1/diag/autoplace-polls/{id}`); poll anchors backfilled by migration 037.
- **Status:** SHIPPED.
- **Feature Flags:** none.
- **Known Constraints:** Group expansion for assignees is deferred; no poll create/delete endpoint found (read + reorder + anchor + edit only).

## Module 11 — Quality & Discrepancies

- **Purpose:** Surface transcription discrepancies and word-level alignment for QA.
- **Routes:** within `#/e/:id` (Discrepancies pane).
- **Screens:** Discrepancies pane.
- **Components:** [DiscrepanciesPane.vue](../../frontend/src/components/editor/DiscrepanciesPane.vue).
- **Database Tables:** `discrepancies` (002), `transcription_discrepancies` (017), `word_alignment` (036), `words` (015).
- **API Endpoints:** `GET /v1/sessions/{id}/discrepancies` ([app/api/discrepancies.py:49](../../app/api/discrepancies.py#L49)); `GET /v1/sessions/{id}/word-alignment` ([app/api/word_alignment.py:54](../../app/api/word_alignment.py#L54)); `GET /v1/sessions/{id}/words` ([app/api/session_resources.py:461](../../app/api/session_resources.py#L461)).
- **Permissions:** JWT.
- **Dependencies:** `lcs_discrepancies_task` (rebuildable via `/v1/diag/realign/{id}`).
- **Status:** SHIPPED (read surfaces).
- **Feature Flags:** none.
- **Known Constraints:** Word alignment is populated by the realign task; legacy sessions may need the diag backfill.

## Module 12 — Corrections & Audit Ledger

- **Purpose:** Persistent correction ledger with undo/redo, find/replace, and a per-session correction audit trail.
- **Routes:** `#/e/:id/audit`, `#/audit`.
- **Screens:** Editor audit tab, global Audit.
- **Components:** [EditorAuditView.vue](../../frontend/src/views/EditorAuditView.vue), [AuditView.vue](../../frontend/src/views/AuditView.vue); [AuditLedger.vue](../../frontend/src/components/audit/AuditLedger.vue), [AuditTabInline.vue](../../frontend/src/components/editor/AuditTabInline.vue).
- **Database Tables:** `correction_ledger` (029), `ledger_pointers` (029), `corrections` (002), `audit_events` (004), `session_audit` (010).
- **API Endpoints:** Corrections (prefix `/v1/sessions`): `POST /{id}/corrections`, `POST /{id}/find-replace`, `GET /{id}/corrections`, `POST /{id}/corrections/undo`, `POST /{id}/corrections/redo`, `GET /{id}/review-queue` ([app/api/corrections.py](../../app/api/corrections.py)). Audit (prefix `/v1/audit`): `GET ""`, `GET /sessions/{id}/corrections` ([app/api/audit.py](../../app/api/audit.py)).
- **Permissions:** JWT.
- **Dependencies:** state machine; segments/words for split/merge.
- **Status:** SHIPPED. The split/merge correction sub-feature is PARTIALLY IMPLEMENTED behind `SPLIT_MERGE_ENABLED`.
- **Feature Flags:** `SPLIT_MERGE_ENABLED` gates the split/merge executor inside `POST /{id}/corrections` ([corrections.py:362](../../app/api/corrections.py#L362)).
- **Known Constraints:** Split/merge serialized on `(session_id, "split_merge")` lock; returns 503 when flag is off so stale UI cannot silently no-op.

## Module 13 — SOP Workflow

- **Purpose:** Stage workflow (Copy Edit → Medical Review → Publish), transitions, assignments, checks, annotations, deadline tracking, dashboard summary.
- **Routes:** `#/e/:id/sop`.
- **Screens:** SOP view.
- **Components:** [SopView.vue](../../frontend/src/views/SopView.vue).
- **Database Tables:** `sop_state` (003), `sop_transitions` (003), `sop_checks` (003), `sop_approvals` (003), `session_stage_assignees` (042), `audit_events` (004, for email dedupe).
- **API Endpoints:** Per-session (prefix `/v1/sessions/{id}/sop`): `GET ""`, `POST /advance`, `POST /assign`, `PATCH /annotations`, `POST /checks/resolve`. Global (prefix `/v1/sop`): `GET /dashboard-summary` ([app/api/sop.py](../../app/api/sop.py)).
- **Permissions:** JWT.
- **Dependencies:** `sop_check_deadlines_task` (Celery Beat, also runnable via `/v1/diag/sop-check`); SMTP for overdue notifications; SLA hours map shared with queue.
- **Status:** SHIPPED.
- **Feature Flags:** `SOP_DEADLINE_EMAIL_ENABLED` (default OFF → overdue computed, no email sent).
- **Known Constraints:** Email dedupe per session+stage on a 23h window via `audit_events`.

## Module 14 — Queue ("My Queue")

- **Purpose:** Per-user work queue — sessions where the current user is the assignee for the session's current SOP stage.
- **Routes:** `#/queue`.
- **Screens:** Queue.
- **Components:** [QueueView.vue](../../frontend/src/views/QueueView.vue).
- **Database Tables:** `session_stage_assignees` (042), `sop_state` (003), `sessions` (001).
- **API Endpoints:** `GET /v1/queue/mine` ([app/api/queue.py:45](../../app/api/queue.py#L45)).
- **Permissions:** JWT (scoped to the calling user's email).
- **Dependencies:** SOP stage state; SLA map mirrors `app/tasks/sop_tasks.py` for `overdue_hours`.
- **Status:** SHIPPED.
- **Feature Flags:** none.
- **Known Constraints:** Excludes soft-deleted sessions, terminal `complete` stage, and group assignments (`group:NAME`) — group expansion deferred to v1.

## Module 15 — Improvements

- **Purpose:** Capture and triage product/process improvements via a wizard flow.
- **Routes:** `#/improvements`.
- **Screens:** Improvements list + detail.
- **Components:** [ImprovementsView.vue](../../frontend/src/views/ImprovementsView.vue); [ImprovDetail.vue](../../frontend/src/components/improvements/ImprovDetail.vue), [SuggestImprovementModal.vue](../../frontend/src/components/overlays/SuggestImprovementModal.vue).
- **Database Tables:** `improvements` (005).
- **API Endpoints (prefix `/v1/improvements`, [app/api/improvements.py](../../app/api/improvements.py)):** `GET ""`, `POST ""`, `GET /{id}`, `PUT /{id}/wizard/{step}`, `PATCH /{id}`, `DELETE /{id}`.
- **Permissions:** JWT.
- **Dependencies:** none beyond the `improvements` table.
- **Status:** SHIPPED.
- **Feature Flags:** none.
- **Known Constraints:** none verified.

## Module 16 — Exports & Artifacts

- **Purpose:** Export the finished transcript in multiple formats; serve VTT captions; manage versioned artifacts.
- **Routes:** download menu within `#/e/:id`.
- **Screens:** Download menu.
- **Components:** [DownloadMenu.vue](../../frontend/src/components/editor/DownloadMenu.vue).
- **Database Tables:** `artifacts` (018), `artifact_versions` (023).
- **API Endpoints:** `GET /v1/sessions/{id}/exports/{format}` ([app/api/exports.py:41](../../app/api/exports.py#L41)); `GET /v1/sessions/{id}/captions.vtt` ([exports.py:120](../../app/api/exports.py#L120), via `captions_router`).
- **Permissions:** JWT.
- **Dependencies:** transcript/segments; artifact generation tasks; GCS for captioned video.
- **Status:** SHIPPED.
- **Feature Flags:** none.
- **Known Constraints:** Supported export formats determined by the `{format}` path param handler (set in exports.py); CMS export is the downstream consumer (handoff format not separately verified here).

## Module 17 — Settings (Team / Types / AI / Email / Prompts / Templates / Auth Users)

- **Purpose:** Org configuration: key/value settings, people, groups + members, session types + per-type stage assignees, auth-user admin, prompt templates, session templates, macro export, email templates + debug.
- **Routes:** `#/settings/:section?`.
- **Screens:** Settings (sectioned).
- **Components:** [SettingsView.vue](../../frontend/src/views/SettingsView.vue); section components under [frontend/src/components/settings/](../../frontend/src/components/settings/): SectionGeneral, SectionTeam, SectionTypes, SectionAIModels, SectionUpload, SectionExport, SectionEmail, SectionDiscrepancy, SectionManifest, SectionDeleted, SectionDiagnostics, SectionAuthUsers, SectionPromptTemplates, EmailBuilder, EmailDebug, GCSDebug, plus FormRow / TogglePill / SettingsHeader; [TweaksPanel.vue](../../frontend/src/components/TweaksPanel.vue).
- **Database Tables:** `org_settings` (006), `people` (006), `groups` (006), `group_members` (006), `session_types` (006), `stage_assignees` (006) / `session_stage_assignees` (042), `prompt_templates` (006/047), `templates` (009), `session_templates` (009), `auth_users` (045), `email_templates` (006/048).
- **API Endpoints:** Settings (prefix `/v1/settings`, [app/api/settings.py](../../app/api/settings.py)): key/value `GET ""`, `PUT /{key}`; people CRUD; groups CRUD + members; types CRUD + `/types/{id}/assignees`; auth-users `GET/POST/PUT/DELETE` + `POST /auth-users/{id}/reset-password`; `GET /export/macro`; templates CRUD. Email templates (prefix `/v1/email-templates`, [app/api/email_templates.py](../../app/api/email_templates.py)): `GET`, `GET /{id}`, `POST`, `PUT /{id}`, `DELETE /{id}`, `POST /resolve`. Email debug (prefix `/v1/admin/email-debug`, [app/api/email_debug.py](../../app/api/email_debug.py)): `GET /config`, `POST /connectivity`, `POST /send`, `GET /attempts`.
- **Permissions:** Mixed. Reads (`GET ""`, people/groups/types reads, `GET /templates`) are JWT-only. **JWT + ADMIN gate** (`require_admin`) on: `POST/DELETE /types`, `PUT /types/{id}/assignees`, all `auth-users` write ops + reset-password, `GET /export/macro`, template create/update/delete ([settings.py:322,337,431,531,538,571,617,647,872,938,1016](../../app/api/settings.py#L322)). All `/v1/email-templates` writes ([email_templates.py:223,266,298](../../app/api/email_templates.py#L223)) and all `/v1/admin/email-debug` ([email_debug.py:53](../../app/api/email_debug.py#L53)) are ADMIN-gated.
- **Dependencies:** SMTP (`SMTP_*` env) for email debug/send; email_attempts table (030).
- **Status:** SHIPPED.
- **Feature Flags:** none directly; the AI-models section surfaces `VERTEX_AI_CLASSIFY_ENABLED` routing indirectly.
- **Known Constraints:** Admin gate is the single `LEGACY_ADMIN_EMAIL` (see Permission Model Reality). `auth_users.role` is editable via this UI but not enforced anywhere.

## Module 18 — Session Locks (edit-conflict prevention)

- **Purpose:** Cooperative editor lock per session — acquire / heartbeat / release / holder / force-take.
- **Routes:** consumed inside `#/e/:id` (no dedicated route).
- **Screens:** lock state surfaced in the editor.
- **Components:** consumed by [EditorView.vue](../../frontend/src/views/EditorView.vue) (no dedicated lock component verified).
- **Database Tables:** `session_locks` (057).
- **API Endpoints (prefix `/v1/sessions`, [app/api/locks.py](../../app/api/locks.py)):** `POST /{id}/lock/acquire`, `POST /{id}/lock/heartbeat`, `POST /{id}/lock/release` (204), `GET /{id}/lock/holder`, `POST /{id}/lock/force-take`.
- **Permissions:** JWT.
- **Dependencies:** editor; correction ledger (locks protect concurrent corrections).
- **Status:** SHIPPED.
- **Feature Flags:** none.
- **Known Constraints:** Force-take semantics (who may steal a lock) are JWT-only — no admin gate on force-take.

---

## Cross-cutting: Help Center

Not one of the 18 numbered functional modules above but a substantial shipped surface; included for completeness.

- **Purpose:** Help articles (CRUD + versioning + archive + reorder), search, coverage report, Ask AI (Gemini), and admin bulk-AI tasks.
- **Routes:** `#/admin/help` (`adminOnly` guard). End-user help is surfaced via the [HelpPanel.vue](../../frontend/src/components/help/HelpPanel.vue) overlay (not a top-level route).
- **Screens:** Help panel (end-user), Help editor (admin).
- **Components:** [HelpEditor.vue](../../frontend/src/views/admin/HelpEditor.vue); [frontend/src/components/help/](../../frontend/src/components/help/): HelpPanel, HelpItem, HelpAskComposer, HelpStepList, HelpRelatedLinks, HelpCoverageReport, HelpVersionHistoryDialog, HelpComplianceMeter, HelpArticleEditorDialog, HelpFaqAccordion, HelpAdminToolbar.
- **Database Tables:** `help_articles` (053), `help_article_versions` (054).
- **API Endpoints (prefix `/v1/help`, [app/api/help.py](../../app/api/help.py)):** `POST /ask`; `GET /articles`, `GET /articles/{id}`, `POST /articles`, `PATCH /articles/{id}`, `PATCH /articles/{id}/archive`, `PATCH /articles/reorder`, `GET /articles/{id}/versions`, `GET /articles/{id}/versions/{version}`, `GET /coverage`, `GET /search`; admin bulk tasks `POST /admin/bulk-publish`, `/admin/fix-summaries`, `/admin/expand-steps`, `/admin/expand-faqs`, `/admin/generate-faq-corpus`.
- **Permissions:** Article reads/search/coverage are JWT-only. `POST /ask` is JWT + the `HELP_ASK_AI_ENABLED` gate (404 when off). All article writes, version reads, reorder, archive, and all `/admin/*` tasks are **JWT + ADMIN gate** (`require_admin`, [help.py:461,529,632,683,713,733,756,834,921,927,933,947](../../app/api/help.py#L461)).
- **Dependencies:** Gemini (Ask AI + bulk tasks); Celery for bulk-AI tasks ([app/tasks/help_tasks.py]).
- **Status:** SHIPPED (articles + admin); Ask AI is PARTIALLY IMPLEMENTED in the sense that it is **disabled by default** behind `HELP_ASK_AI_ENABLED`.
- **Feature Flags:** `HELP_ASK_AI_ENABLED` (default OFF), `HELP_ASK_AI_RATE_LIMIT_PER_HOUR` (default 30, soft cap).
- **Known Constraints:** Client `adminOnly` guard on `#/admin/help` is UI-only; the server is authoritative on every write route.

## Cross-cutting: Diagnostics / Operator Tools

- **Purpose:** Operator-only curl/Postman rescue + read-only probes; no general UI surface (Settings exposes a Diagnostics section that consumes a subset).
- **Routes:** `#/gcs` (GCS debug view); Settings → Diagnostics section.
- **Screens:** GcsView, SectionDiagnostics.
- **Components:** [GcsView.vue](../../frontend/src/views/GcsView.vue); [SectionDiagnostics.vue](../../frontend/src/components/settings/SectionDiagnostics.vue), [GCSDebug.vue](../../frontend/src/components/settings/GCSDebug.vue).
- **Database Tables:** reads across `sessions`, `word_alignment`, `auth_users`, etc. (no dedicated table).
- **API Endpoints (prefix `/v1/diag`, [app/api/diagnostics.py](../../app/api/diagnostics.py)):** read probes `GET /gcs`, `GET /classify-route`, `GET /gcs-checks`; per-session rescue `POST /reingest/{id}`, `/realign/{id}`, `/init-session-stages/{id}`, `/autoplace-polls/{id}`, `/abort-session/{id}`; queue/task surgery `POST /flush-celery-queue`, `/revoke-task/{task_id}`, `/sop-check`; rate-limit/auth recovery `POST /clear-rate-limit-slots`, `/reseed-auth-users`.
- **Permissions:** Most routes are **JWT only** (`CurrentUser`). Two routes hardcode an inline `email == johndean@vin.com` check: `POST /reseed-auth-users` ([diagnostics.py:534](../../app/api/diagnostics.py#L534)) and `GET /gcs-checks` ([diagnostics.py:632](../../app/api/diagnostics.py#L632)).
- **Dependencies:** GCS, Celery, Redis, STT/classify routing, `auth_users` seed.
- **Status:** SHIPPED (operator tooling).
- **Feature Flags:** `VERTEX_AI_CLASSIFY_ENABLED` is reported by `GET /classify-route`.
- **Known Constraints:** Most diag routes are reachable by any authenticated user despite being "operator-only" — only 2 of 13 enforce the email gate. Non-destructive today; CLAUDE.md notes a confirmation-token requirement should precede any future destructive route.

## Cross-cutting: Notifications / Email

- **Purpose:** SMTP delivery for SOP overdue notifications + email template management/debug.
- **Routes:** Settings → Email section.
- **Screens:** EmailBuilder, EmailDebug.
- **Components:** [SectionEmail.vue](../../frontend/src/components/settings/SectionEmail.vue), [EmailBuilder.vue](../../frontend/src/components/settings/EmailBuilder.vue), [EmailDebug.vue](../../frontend/src/components/settings/EmailDebug.vue).
- **Database Tables:** `email_templates` (006/048), `email_attempts` (030).
- **API Endpoints:** `/v1/email-templates/*` and `/v1/admin/email-debug/*` (see Module 17).
- **Permissions:** all writes/debug **JWT + ADMIN gate**.
- **Dependencies:** `SMTP_*` env (sends as `mic@design.veterinary.support` per CLAUDE.md, shared with MIC).
- **Status:** SHIPPED.
- **Feature Flags:** `SOP_DEADLINE_EMAIL_ENABLED` controls whether the SOP deadline task actually sends.
- **Known Constraints:** Email send path only fires from the SOP deadline task when the flag is on, plus manual debug `/send`.

---

## Source Verification
- **Files Used:** [app/config.py](../../app/config.py), [app/main.py](../../app/main.py), [app/auth.py](../../app/auth.py), [app/security/roles.py](../../app/security/roles.py), [frontend/src/router/index.ts](../../frontend/src/router/index.ts), [app/api/auth.py](../../app/api/auth.py), [app/api/sessions.py](../../app/api/sessions.py), [app/api/gcs_upload.py](../../app/api/gcs_upload.py), [app/api/add_to_session.py](../../app/api/add_to_session.py), [app/api/segments.py](../../app/api/segments.py), [app/api/corrections.py](../../app/api/corrections.py), [app/api/session_resources.py](../../app/api/session_resources.py), [app/api/discrepancies.py](../../app/api/discrepancies.py), [app/api/word_alignment.py](../../app/api/word_alignment.py), [app/api/sop.py](../../app/api/sop.py), [app/api/queue.py](../../app/api/queue.py), [app/api/improvements.py](../../app/api/improvements.py), [app/api/exports.py](../../app/api/exports.py), [app/api/settings.py](../../app/api/settings.py), [app/api/email_templates.py](../../app/api/email_templates.py), [app/api/email_debug.py](../../app/api/email_debug.py), [app/api/locks.py](../../app/api/locks.py), [app/api/help.py](../../app/api/help.py), [app/api/audit.py](../../app/api/audit.py), [app/api/diagnostics.py](../../app/api/diagnostics.py), [migrations/](../../migrations/) (001–057)
- **Components Used:** all `.vue` files under [frontend/src/views/](../../frontend/src/views/) and [frontend/src/components/](../../frontend/src/components/) (enumerated per module above)
- **APIs Used:** every route registered in [app/main.py](../../app/main.py) across the 21 routers + 2 sub-routers (sop.global_router, exports.captions_router) + the `/v1/ws/sessions/{id}` WebSocket + `/v1/health` + `/v1/version`
- **Database Tables Used:** sessions, sources, slides, speakers, segments, words, bullets, session_speakers, session_slide_resources, slide_time_ranges, replay_log, alignments, validation_results, normalization_results, discrepancies, corrections, transcription_discrepancies, word_alignment, correction_ledger, ledger_pointers, audit_events, session_audit, sop_state, sop_transitions, sop_checks, sop_approvals, session_stage_assignees, stage_assignees, session_types, templates, session_templates, org_settings, people, groups, group_members, prompt_templates, email_templates, email_attempts, improvements, artifacts, artifact_versions, instructor_profiles, session_instructor_map, session_patterns, key_points_annotations, auth_users, help_articles, help_article_versions, session_locks
- **Permission Logic Used:** JWT presence (`CurrentUser`) + `require_admin`/`is_admin` resolving to the hardcoded `LEGACY_ADMIN_EMAIL` (`johndean@vin.com`) gate; `SESSION_TRASH_ALLOWED` wider allowlist; two inline `email == johndean@vin.com` checks in diagnostics; one client-side `meta.adminOnly` route guard. `auth_users.role` exists (migration 045) but is NOT read by `get_current_user` — role tiers are NOT active.
- **Confidence Score:** High — every endpoint, route, table, flag default, and permission gate cited is read directly from source; the few unverifiable items are explicitly tagged (dashboard backend IMPLEMENTATION NOT FOUND; WS auth model NOT VERIFIED IN CODE).
- **Evidence Links:** [app/config.py:100-134](../../app/config.py#L100) (flag defaults), [app/security/roles.py:54,88-92](../../app/security/roles.py#L54) (admin gate), [app/auth.py:36-39,172-205](../../app/auth.py#L36) (User has email only; role never read), [frontend/src/router/index.ts:44,63](../../frontend/src/router/index.ts#L44) (adminOnly guard), [app/api/diagnostics.py:534,632](../../app/api/diagnostics.py#L534) (inline email gates), [app/api/corrections.py:362](../../app/api/corrections.py#L362) (SPLIT_MERGE_ENABLED 503), [app/api/help.py:174](../../app/api/help.py#L174) (HELP_ASK_AI_ENABLED 404)
