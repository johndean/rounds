# Processing Pipeline — Demo Questions

Code-true Q&A grouped by persona. Every answer is verified against current
source. File links are relative to this file's location
(`ai-demo-knowledge/demo-questions/`).

---

## User

### Q: After my upload finishes, do I have to do anything to start processing?
**Verified Answer:** No. When the upload completes, the backend automatically
enqueues the processing pipeline (`enqueue_ingest`) inside the
`/v1/gcs/upload-complete` handler. You're taken to the "Building your output"
screen and the pipeline runs to completion on its own.
**Supporting Evidence:** upload-complete calls `enqueue_ingest(session_id)` after
inserting sources; ProcessingView shows the live progress.
**Source Files:** [app/api/gcs_upload.py:198-206](../../app/api/gcs_upload.py#L198-L206), [frontend/src/views/ProcessingView.vue:355-416](../../frontend/src/views/ProcessingView.vue#L355-L416)
**API References:** POST /v1/gcs/upload-complete
**Database References:** sources, sessions

### Q: What happens when processing finishes?
**Verified Answer:** When the session reaches `ready` (or `complete`), the
Processing screen automatically redirects you to the editor at `/e/:id` after a
short delay.
**Supporting Evidence:** A `watch` on the processing stage / session status
redirects to `/e/${id}` 600ms after reaching ready.
**Source Files:** [frontend/src/views/ProcessingView.vue:289-298](../../frontend/src/views/ProcessingView.vue#L289-L298)
**API References:** GET /v1/sessions/{id} (polled), WS /v1/ws/sessions/{id}
**Database References:** sessions.status

### Q: What do the steps on the processing screen mean?
**Verified Answer:** The step list depends on the pipeline. Standard sessions
show: Uploading → Transcribing → Applying IIL → Detecting boundaries → Matching
slides. AI direct shows: Preparing files → AI analysis → Mapping slides →
Finalizing. AI enhanced shows: Uploading → Transcribing → AI enhancement →
Applying IIL → Matching slides.
**Supporting Evidence:** Three step arrays selected by detected pipeline.
**Source Files:** [frontend/src/views/ProcessingView.vue:39-70](../../frontend/src/views/ProcessingView.vue#L39-L70), [frontend/src/views/ProcessingView.vue:136-146](../../frontend/src/views/ProcessingView.vue#L136-L146)
**API References:** GET /v1/sessions/{id}/pipeline-config
**Database References:** session_templates.ai_pipeline, session_templates.ai_mode

### Q: My session failed — can I retry without re-uploading?
**Verified Answer:** Yes. The failure card has a Retry button that calls
reingest, which resets the session to `uploading`, deletes the prior segments,
and re-runs the pipeline against the already-uploaded source. There's also
"Delete & start over" which soft-deletes the session.
**Supporting Evidence:** `onRetry` calls `sessions.retry`, which maps to
`/v1/diag/reingest/{id}`; reingest resets status and deletes segments.
**Source Files:** [frontend/src/views/ProcessingView.vue:246-266](../../frontend/src/views/ProcessingView.vue#L246-L266), [frontend/src/services/api.ts:178-180](../../frontend/src/services/api.ts#L178), [app/api/diagnostics.py:117-131](../../app/api/diagnostics.py#L117-L131)
**API References:** POST /v1/diag/reingest/{id}
**Database References:** sessions.status, segments

### Q: The screen says the AI service is busy — what should I do?
**Verified Answer:** That's the `gemini_overloaded` failure. The card shows a tip
to wait 1-2 minutes and retry, because Google's load usually clears. Retrying
re-runs the pipeline.
**Supporting Evidence:** Failure card renders a `gemini_overloaded`-specific tip.
**Source Files:** [frontend/src/views/ProcessingView.vue:338-340](../../frontend/src/views/ProcessingView.vue#L338-L340), [app/tasks/celery_app.py:92-93](../../app/tasks/celery_app.py#L92-L93)
**API References:** WS /v1/ws/sessions/{id} (session_failed)
**Database References:** sessions.status

---

## Executive

### Q: What does the processing pipeline actually produce for the business?
**Verified Answer:** A complete first-pass transcript: time-stamped segments and
words, a speaker roster, extracted slide decks (text + bullets + thumbnails),
automatic slide-to-segment alignment, and transcription discrepancies — all
written to Postgres and ready for the Copy Edit → Medical Review → Publish
workflow. No manual transcription is required.
**Supporting Evidence:** Tasks write segments/words, speakers, slides/bullets,
alignments, and discrepancies.
**Source Files:** [app/tasks/transcribe.py:112-192](../../app/tasks/transcribe.py#L112-L192), [app/tasks/align.py:245-328](../../app/tasks/align.py#L245-L328), [app/tasks/slide_extract.py:281-322](../../app/tasks/slide_extract.py#L281-L322)
**API References:** POST /v1/gcs/upload-complete
**Database References:** segments, words, speakers, slides, bullets, alignments, transcription_discrepancies

### Q: There are two pipelines — which one runs, and why two?
**Verified Answer:** Routing is per-session on `session_templates.ai_pipeline`.
`'direct'` sends media + slides straight to Gemini multimodal (one task, fastest
path, jumps straight to ready). Anything else (default `'enhanced'`) runs the
classic Google Speech-to-Text chain with separate transcribe, IIL normalize,
fusion, and alignment stages. Both produce the same output shape.
**Supporting Evidence:** `ingest_task` branches on `ai_pipeline`.
**Source Files:** [app/tasks/ingest.py:88-193](../../app/tasks/ingest.py#L88-L193)
**API References:** GET /v1/sessions/{id}/pipeline-config
**Database References:** session_templates.ai_pipeline

### Q: How is correctness protected at scale — what stops a bad transcript from shipping?
**Verified Answer:** Several gates. An empty STT result is fatal (session won't
go ready). Normalization falls back to raw verbatim text on validation failure so
broken cleanup never ships. Fusion runs a 5-assertion gate; alignment runs a
second 5-assertion pre-ready gate plus a fusion-output gate — any failure halts
the session to `failed` with an auditable reason rather than fabricating output.
**Supporting Evidence:** Empty-transcript raise, raw-fallback invariant, and the
two gate engines.
**Source Files:** [app/tasks/transcribe.py:106-107](../../app/tasks/transcribe.py#L106-L107), [app/tasks/normalize.py:176-180](../../app/tasks/normalize.py#L176-L180), [app/engines/fusion.py:383-449](../../app/engines/fusion.py#L383-L449), [app/engines/pre_ready_gate.py:42-96](../../app/engines/pre_ready_gate.py#L42-L96)
**API References:** none
**Database References:** sessions.status, alignments, validation_results, audit_events

---

## Operations

### Q: A session is stuck on "uploading" — how do I recover it?
**Verified Answer:** Two ways. There's a background watchdog (`upload_watchdog`,
Celery Beat) that re-enqueues sessions stuck on `uploading` past 300s that have an
audio/video source — but it's feature-flagged OFF by default. Operationally you
curl `POST /v1/diag/reingest/{id}`, which resets the session to `uploading`,
deletes prior segments, and re-runs ingest.
**Supporting Evidence:** Watchdog match criteria + default-OFF flag; reingest
endpoint behavior.
**Source Files:** [app/tasks/upload_watchdog.py:67-115](../../app/tasks/upload_watchdog.py#L67-L115), [app/config.py:100](../../app/config.py#L100), [app/api/diagnostics.py:94-171](../../app/api/diagnostics.py#L94-L171)
**API References:** POST /v1/diag/reingest/{id}
**Database References:** sessions.status, sources, segments, session_audit

### Q: How do I force-break a session that's wedged so the UI stops looping?
**Verified Answer:** `POST /v1/diag/abort-session/{id}` forces the session into
`failed` (bypassing the state machine), appends an audit log entry, and publishes
a `session_failed` WS event so any open Processing/SessionDetail tab flips out of
the "Preparing files" loop. Then reingest or delete.
**Supporting Evidence:** abort-session handler.
**Source Files:** [app/api/diagnostics.py:433-512](../../app/api/diagnostics.py#L433-L512)
**API References:** POST /v1/diag/abort-session/{id}
**Database References:** sessions.status, session_audit

### Q: A finished session has no Discrepancies tab data — how do I backfill it?
**Verified Answer:** `POST /v1/diag/realign/{id}` re-triggers
`lcs_discrepancies_task`, which is idempotent: it preserves existing discrepancies
and only fills in the missing `word_alignment` rows (the table was added in
migration 036 after some sessions had finished STT + LCS).
**Supporting Evidence:** realign handler + lcs_discrepancies idempotency.
**Source Files:** [app/api/diagnostics.py:180-199](../../app/api/diagnostics.py#L180-L199), [app/tasks/lcs_discrepancies.py:35-63](../../app/tasks/lcs_discrepancies.py#L35-L63)
**API References:** POST /v1/diag/realign/{id}
**Database References:** transcription_discrepancies, word_alignment

### Q: Why does re-running ingest sometimes do nothing?
**Verified Answer:** `ingest_task` refuses to re-run if segments already exist
(returns `segments_exist_no_reingest`) to prevent cross-pipeline overwrites of
`segments.text`. You must go through `/v1/diag/reingest`, which deletes segments
first. Similarly, each task has a check-before-execute guard that skips if its
output rows or Redis done-flag already exist.
**Supporting Evidence:** ingest segment-existence guard; reingest deletes segments.
**Source Files:** [app/tasks/ingest.py:96-113](../../app/tasks/ingest.py#L96-L113), [app/api/diagnostics.py:126-131](../../app/api/diagnostics.py#L126-L131)
**API References:** POST /v1/diag/reingest/{id}
**Database References:** segments

### Q: How are tasks retried, and which failures don't retry?
**Verified Answer:** Retryable failures back off exponentially (60/120/240s) with
optional jitter up to `CELERY_MAX_RETRIES` (3). Terminal LLM categories —
`gemini_context_overflow`, `gemini_config`, `gemini_model_deprecated`,
`validation_error` — skip retries and fail the session immediately so the budget
isn't burned on unfixable inputs.
**Supporting Evidence:** retry_with_backoff + TERMINAL_LLM_CATEGORIES.
**Source Files:** [app/tasks/celery_app.py:194-212](../../app/tasks/celery_app.py#L194-L212), [app/engines/llm_client.py:42-47](../../app/engines/llm_client.py#L42-L47), [app/tasks/ai_process.py:132-145](../../app/tasks/ai_process.py#L132-L145)
**API References:** none
**Database References:** sessions.status

### Q: Is Celery Beat safe to run — won't multiple workers double-fire it?
**Verified Answer:** Beat is embedded into the worker via the `-B` flag, and the
design assumes a single worker replica so no leader election is needed. The two
scheduled tasks are `upload-watchdog` (60s) and `sop-check-deadlines` (3600s).
**Supporting Evidence:** Beat schedule + the single-replica note.
**Source Files:** [app/tasks/celery_app.py:66-89](../../app/tasks/celery_app.py#L66-L89)
**API References:** none
**Database References:** sessions, session_audit, audit_events, sop_state

---

## Finance

### Q: How does the pipeline control LLM/API spend?
**Verified Answer:** Several mechanisms. A pre-flight token-count probe estimates
input tokens against per-model context limits to fail-fast before paying the
upload + first generate_content cost. A hallucination-loop truncator clips runaway
Gemini repetition (observed burning 100k+ output tokens). Terminal LLM categories
skip retries so unfixable inputs don't re-bill. Per-user concurrency
(`MAX_CONCURRENT_SESSIONS=3`) and a global queue cap (`MAX_QUEUE_LENGTH=10`) bound
how much work runs at once.
**Supporting Evidence:** token probe, loop truncator, terminal categories, rate
limits.
**Source Files:** [app/engines/llm_client.py:50-67](../../app/engines/llm_client.py#L50-L67), [app/tasks/ai_process.py:55-82](../../app/tasks/ai_process.py#L55-L82), [app/config.py:46-47](../../app/config.py#L46-L47), [app/middleware/rate_limit.py:33-66](../../app/middleware/rate_limit.py#L33-L66)
**API References:** POST /v1/gcs/upload-url (quota check), POST /v1/gcs/upload-complete
**Database References:** sessions

### Q: Does the standard pipeline avoid Gemini cost entirely?
**Verified Answer:** The standard STT chain uses Google Speech-to-Text for
transcription (not Gemini). Gemini is used in the AI Mode direct/enhanced
transcription path and in discrepancy classification. So a plain-transcript
standard session bills STT + the classify step rather than the multimodal Gemini
call.
**Supporting Evidence:** transcribe uses google.cloud.speech; ai_process uses
Gemini; classify is a separate downstream task.
**Source Files:** [app/tasks/transcribe.py:245-329](../../app/tasks/transcribe.py#L245-L329), [app/tasks/ai_process.py:296-302](../../app/tasks/ai_process.py#L296-L302), [app/tasks/lcs_discrepancies.py:182-187](../../app/tasks/lcs_discrepancies.py#L182-L187)
**API References:** none
**Database References:** session_templates.ai_pipeline

### Q: What caps the size/length of media that can be processed?
**Verified Answer:** Uploads are validated against `MAX_VIDEO_DURATION_MINUTES`
(180) and `MAX_UPLOAD_SIZE_MB` (2048). Duration is re-checked inside frame
detection and the AI direct path, raising a validation error if exceeded — so an
oversized clip fails fast rather than running up cost.
**Supporting Evidence:** validate_files + in-pipeline duration re-checks.
**Source Files:** [app/middleware/rate_limit.py:119-129](../../app/middleware/rate_limit.py#L119-L129), [app/config.py:48-49](../../app/config.py#L48-L49), [app/tasks/ai_process.py:357-363](../../app/tasks/ai_process.py#L357-L363)
**API References:** POST /v1/gcs/upload-complete
**Database References:** sources.duration_sec, sources.size_bytes

---

## Compliance

### Q: Is there an audit trail of how each session was processed?
**Verified Answer:** Yes. Every state transition appends a JSONB entry (stage,
status, started_at, completed_at, actor, reason, metadata) to
`session_audit.processing_log`, and `ready` stamps `finalized_at`. It's readable
via `GET /v1/sessions/{id}/audit-log`. Upload-complete additionally writes
`audit_events` rows for sources, manifest, and chat parses, and gate failures
write an `align.gate_failure` audit_events row.
**Supporting Evidence:** state machine audit append + audit-log endpoint + gate
audit writes.
**Source Files:** [app/engines/state_machine.py:52-95](../../app/engines/state_machine.py#L52-L95), [app/api/sessions.py:306-320](../../app/api/sessions.py#L306-L320), [app/tasks/align.py:362-374](../../app/tasks/align.py#L362-L374)
**API References:** GET /v1/sessions/{id}/audit-log
**Database References:** session_audit, audit_events

### Q: Are the AI scoring weights documented and protected from drift?
**Verified Answer:** Yes. The fusion weights (visual 0.5 / anchor 0.3 / semantic
0.2, threshold 0.35), alignment weights, anchor cross-validate window, IIL
thresholds, and retry/backoff constants are all in a LOCKED block in
`app/config.py` and are pinned by
`tests/test_health.py::test_locked_weights_match_audit`. Changing them requires a
coordinated config + test update.
**Supporting Evidence:** LOCKED weights block + the pinning invariant comment.
**Source Files:** [app/config.py:51-77](../../app/config.py#L51-L77), [app/config.py:9-11](../../app/config.py#L9-L11)
**API References:** none
**Database References:** none

### Q: Is the slide-boundary detection reproducible for review?
**Verified Answer:** Yes. Fusion boundary timestamps are locked to 0.5s precision,
and every fusion run writes a `replay_log` row containing the input hash, the full
fusion inputs, and the fusion output — so a reviewer can reproduce exactly which
signals produced which boundaries.
**Supporting Evidence:** 0.5s lock + replay_log write.
**Source Files:** [app/engines/fusion.py:96-98](../../app/engines/fusion.py#L96-L98), [app/tasks/fusion.py:198-212](../../app/tasks/fusion.py#L198-L212)
**API References:** none
**Database References:** replay_log

### Q: How are clinically-sensitive terms (drug names, doses) protected during cleanup?
**Verified Answer:** The IIL normalize step runs a deterministic validate-and-
repair with no LLM calls, restoring words from the word-level SSOT on check
failure. If validation terminally fails, `segments.text` keeps the raw STT
verbatim — broken normalization never ships. This is the stated clinical-safety
invariant.
**Supporting Evidence:** validate_and_repair usage + raw-fallback invariant.
**Source Files:** [app/tasks/normalize.py:136-180](../../app/tasks/normalize.py#L136-L180)
**API References:** none
**Database References:** normalization_results, segments

### Q: Can media be registered outside its own session's storage scope?
**Verified Answer:** No. The R7 invariant: `/v1/gcs/upload-complete` rejects any
`gcs_uri` not under `gs://<bucket>/sessions/<id>/` with a 400 validation error.
This is the locked scope guard.
**Supporting Evidence:** find_out_of_scope_uri check in upload-complete.
**Source Files:** [app/api/gcs_upload.py:128-137](../../app/api/gcs_upload.py#L128-L137)
**API References:** POST /v1/gcs/upload-complete
**Database References:** sources.gcs_uri

---

## Administrator

### Q: What's the real authorization on the pipeline and its rescue endpoints?
**Verified Answer:** JWT presence only. Every pipeline endpoint and every
`/v1/diag/*` rescue endpoint requires a valid token (`CurrentUser`) but performs
no role check. Role-based auth is scaffold-only: `app/security/roles.py` is
documented as not wired into endpoints, and `auth_users.role` (migration 045) is
not read by `get_current_user`. The only real admin gate nearby is the hardcoded
`user.email == "johndean@vin.com"` (`LEGACY_ADMIN_EMAIL`) check used on
`GET /v1/sessions/deleted`.
**Supporting Evidence:** CurrentUser-only handlers; roles scaffold note;
LEGACY_ADMIN_EMAIL.
**Source Files:** [app/api/diagnostics.py:94-95](../../app/api/diagnostics.py#L94-L95), [app/security/roles.py:10-19](../../app/security/roles.py#L10-L19), [app/security/roles.py:54](../../app/security/roles.py#L54), [app/api/sessions.py:266-277](../../app/api/sessions.py#L266-L277)
**API References:** POST /v1/diag/*, GET /v1/sessions/deleted
**Database References:** auth_users (role column not consulted)

### Q: How do I enable or disable the stuck-upload watchdog?
**Verified Answer:** It's controlled by the `UPLOAD_WATCHDOG_ENABLED` env var
(default False) on the worker. Flip it true in Railway worker env + restart to
activate; set it back to false + restart to disable — no code change. While off,
the beat task returns `{"disabled": True}` in ~1ms. Tune `UPLOAD_STUCK_THRESHOLD_SEC`
(300), `UPLOAD_WATCHDOG_INTERVAL_SEC` (60), and `UPLOAD_WATCHDOG_COOLDOWN_SEC` (600).
**Supporting Evidence:** flag + early return + the three tunables.
**Source Files:** [app/config.py:92-111](../../app/config.py#L92-L111), [app/tasks/upload_watchdog.py:67-68](../../app/tasks/upload_watchdog.py#L67-L68)
**API References:** none
**Database References:** sessions, sources, session_audit

### Q: What configuration determines which pipeline and AI model a session uses?
**Verified Answer:** `session_templates` per session: `ai_pipeline`
(`direct`/`enhanced`), `ai_mode`, `ai_model`, `prompt_mode`, `custom_prompt`,
`template_id`, and `iil_config`. `ingest_task` reads `ai_pipeline`; `ai_process`
reads the AI fields; `normalize` reads `iil_config` + the joined template's filler
policy. The default `ai_pipeline` when unset is `enhanced`.
**Supporting Evidence:** ingest + ai_process + normalize reads.
**Source Files:** [app/tasks/ingest.py:67-88](../../app/tasks/ingest.py#L67-L88), [app/tasks/ai_process.py:104-130](../../app/tasks/ai_process.py#L104-L130), [app/tasks/normalize.py:62-97](../../app/tasks/normalize.py#L62-L97)
**API References:** GET /v1/sessions/{id}/pipeline-config
**Database References:** session_templates, templates

### Q: Where do GCP/Gemini credentials and STT settings come from?
**Verified Answer:** From `app.config.settings` (Pydantic, env-backed):
`GCP_PROJECT_ID`, `GCS_BUCKET`, `GEMINI_API_KEY`, `GEMINI_CLASSIFY_MODEL`
(`gemini-2.5-flash-lite`), `TRANSCRIPTION_BACKEND` (`google_stt_chunked`), and
`TRANSCRIPTION_CHUNK_MINUTES` (5). The tasks read these at runtime.
**Supporting Evidence:** settings fields + task usage.
**Source Files:** [app/config.py:35-87](../../app/config.py#L35-L87), [app/tasks/transcribe.py:80-89](../../app/tasks/transcribe.py#L80-L89)
**API References:** none
**Database References:** none

---

## Power User

### Q: How exactly are transcript segments formed from raw words?
**Verified Answer:** Via the deterministic 4-rule segmenter applied in locked
order: (1) split on sentence-ending punctuation, (2) merge consecutive groups
under 2s, (3) split groups over 20s at the word-count midpoint (recursive), (4)
split on silence gaps ≥ 500ms. Each segment gets a content-deterministic id
`SHA256(session_id + start_ms)`, so identical inputs produce identical ids across
re-runs (idempotent UPSERT).
**Supporting Evidence:** segment_words rule order + make_segment_id.
**Source Files:** [app/engines/segmenter.py:41-160](../../app/engines/segmenter.py#L41-L160)
**API References:** none
**Database References:** segments.content_hash

### Q: When is a slide-boundary anchor "confirmed" versus speculative?
**Verified Answer:** An anchor is confirmed (confidence 0.9) only when an ANCHORS
phrase (e.g. "next slide", "as you can see", "moving on") appears in the segment
AND a visual change is within ±`ANCHOR_CROSS_VALIDATE_WINDOW` (5.0s) OR a semantic
shift > 0.3 is nearby. Otherwise it's speculative (confidence 0.3) and not used as
a boundary signal in fusion.
**Supporting Evidence:** detect_anchors confirmation logic + ANCHORS list.
**Source Files:** [app/engines/anchor.py:22-105](../../app/engines/anchor.py#L22-L105)
**API References:** none
**Database References:** none (anchors stored in Redis rounds:anchor:{id})

### Q: How are the fusion signals combined into a boundary?
**Verified Answer:** Per visual signal, the score is
`0.5*visual + 0.3*anchor + 0.2*semantic`. The signal gate forbids semantic from
triggering a boundary alone when visual change is below threshold and no anchor is
confirmed. Candidates over the 0.35 boundary threshold are kept, merged within a
3s window (max-score wins), locked to 0.5s, and expanded into soft windows
(±5s). Visual-only iteration is MIC-verbatim (no proportional padding).
**Supporting Evidence:** run_fusion score formula, signal gate, merge/lock/soft
windows.
**Source Files:** [app/engines/fusion.py:101-335](../../app/engines/fusion.py#L101-L335)
**API References:** none
**Database References:** slide_time_ranges, replay_log

### Q: How does the alignment engine pick which slide a segment belongs to?
**Verified Answer:** Four weighted signals per segment-vs-slide:
semantic (0.35, token overlap / slide tokens), coverage (0.25, fraction of segment
inside the slide range), temporal (0.25, linear proximity to slide center),
sequential (0.15, backward jumps penalized 0.8). The winner is chosen by absolute
dominance over the runner-up; dominance < 0.6 → uncertain (no slide). Best score
< 0.6 while confident → drift_flag with a 0.3 confidence penalty.
**Supporting Evidence:** align_segment scoring + dominance/drift rules.
**Source Files:** [app/engines/alignment.py:73-197](../../app/engines/alignment.py#L73-L197)
**API References:** none
**Database References:** alignments, validation_results

### Q: What are the two gates between fusion and "ready", and what fails them?
**Verified Answer:** First, the fusion-output gate in align: 0 slide_time_ranges
halts the session. Then the 5-assertion pre-ready gate: GATE_1 coverage (segments
exist), GATE_2 completeness (no null required fields), GATE_3 timestamps
(start<end, no overlaps), GATE_4 template-id match, GATE_5 IIL (normalized_text
present when IIL enabled). Separately, fusion itself runs a 5-assertion gate
(boundary count, spacing stddev, timeline coverage, no overlap, no gaps over 1s).
Any failure halts the session to `failed` with an audit_events row + WS event.
**Supporting Evidence:** align gates + pre_ready_gate + fusion gate.
**Source Files:** [app/tasks/align.py:91-242](../../app/tasks/align.py#L91-L242), [app/engines/pre_ready_gate.py:42-96](../../app/engines/pre_ready_gate.py#L42-L96), [app/engines/fusion.py:383-449](../../app/engines/fusion.py#L383-L449)
**API References:** none
**Database References:** sessions.status, alignments, validation_results, audit_events

### Q: In AI direct mode, how are segment timestamps assigned if Gemini doesn't give them?
**Verified Answer:** Proportionally. After parsing, the media duration is probed
via ffprobe (with a fallback). Each segment's duration is `(len(text)/total_chars)
* duration_sec`, walked cumulatively from 0, and the last segment's end is clamped
to the full duration. Word-level STT timestamps are filled in later, asynchronously,
by `stt_background_task`.
**Supporting Evidence:** proportional timestamp loop + stt_background.
**Source Files:** [app/tasks/ai_process.py:353-373](../../app/tasks/ai_process.py#L353-L373), [app/tasks/ai_process.py:711-831](../../app/tasks/ai_process.py#L711-L831)
**API References:** none
**Database References:** segments.start_ms, segments.end_ms, words

### Q: How does frame_task hand its visual signals to anchor/fusion without chaining?
**Verified Answer:** Via Redis. `frame_task` runs in parallel and writes
`VisualSignal[]` to `rounds:frame:{id}` (24h TTL) plus a done flag; it triggers
nothing. `anchor_task` (triggered by transcribe) reads that key at execution time
and degrades to empty signals if frame hasn't finished. `fusion_task` likewise
loads visual, anchor, and semantic signals from Redis.
**Supporting Evidence:** frame Redis keys + anchor/fusion loaders.
**Source Files:** [app/tasks/frame_task.py:39-42](../../app/tasks/frame_task.py#L39-L42), [app/tasks/frame_task.py:266-287](../../app/tasks/frame_task.py#L266-L287), [app/tasks/anchor_task.py:85-87](../../app/tasks/anchor_task.py#L85-L87), [app/tasks/fusion.py:93-96](../../app/tasks/fusion.py#L93-L96)
**API References:** none
**Database References:** none (Redis-backed signal hand-off)

---

## Source Verification
- **Files Used:** app/tasks/ingest.py, app/tasks/transcribe.py, app/tasks/ai_process.py, app/tasks/normalize.py, app/tasks/slide_extract.py, app/tasks/frame_task.py, app/tasks/anchor_task.py, app/tasks/fusion.py, app/tasks/align.py, app/tasks/lcs_discrepancies.py, app/tasks/finalize.py, app/tasks/upload_watchdog.py, app/tasks/celery_app.py, app/engines/anchor.py, app/engines/segmenter.py, app/engines/fusion.py, app/engines/alignment.py, app/engines/pre_ready_gate.py, app/engines/state_machine.py, app/engines/llm_client.py, app/config.py, app/api/gcs_upload.py, app/api/sessions.py, app/api/diagnostics.py, app/middleware/rate_limit.py, app/security/roles.py, frontend/src/views/ProcessingView.vue, frontend/src/services/api.ts
- **Components Used:** ProcessingView.vue
- **APIs Used:** POST /v1/gcs/upload-url, POST /v1/gcs/upload-complete, GET /v1/sessions/{id}/pipeline-config, GET /v1/sessions/{id}/audit-log, GET /v1/sessions/deleted, POST /v1/diag/reingest/{id}, POST /v1/diag/realign/{id}, POST /v1/diag/abort-session/{id}
- **Database Tables Used:** sessions, sources, session_templates, templates, segments, words, slides, bullets, speakers, slide_time_ranges, alignments, validation_results, normalization_results, transcription_discrepancies, word_alignment, replay_log, session_audit, audit_events, auth_users
- **Permission Logic Used:** JWT presence (CurrentUser) on all pipeline + diag endpoints; LEGACY_ADMIN_EMAIL gate via require_admin only on GET /v1/sessions/deleted; role-based auth scaffold-only
- **Confidence Score:** High — every answer cites a verified file:line in current source.
- **Evidence Links:** [ingest.py:88-193](../../app/tasks/ingest.py#L88-L193), [fusion.py:101-335](../../app/engines/fusion.py#L101-L335), [alignment.py:73-197](../../app/engines/alignment.py#L73-L197), [celery_app.py:194-212](../../app/tasks/celery_app.py#L194-L212), [config.py:51-111](../../app/config.py#L51-L111)
