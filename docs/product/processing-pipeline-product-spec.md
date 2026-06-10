# Processing Pipeline — Product Spec

The Processing Pipeline is the automated chain that turns an uploaded recording
into a first-pass transcript with speaker labels and slide alignment. It runs
entirely on the backend (Celery workers) and surfaces to the operator as a
single "Building your output" progress screen.

> Every claim below is verified against current code. File:line links are
> relative to this document's location (`docs/product/`).

## Overview

When an upload completes, the backend enqueues a Celery DAG that drives a session
from status `uploading` to `ready`. There are two pipelines, chosen per session
by `session_templates.ai_pipeline`:

- **Standard / enhanced (STT-based):** `transcribe` (Google Speech-to-Text,
  chunked) → `frame` (visual change detection, in parallel) → `anchor`
  (visual + semantic cross-validation) → `normalize` (IIL filler removal) →
  `fusion` (slide boundary detection) → `align` (segment→slide alignment) →
  `finalize` (mark ready). See [ingest.py](../../app/tasks/ingest.py#L160-L193).
- **AI Mode direct (`ai_pipeline = 'direct'`):** a single task `ai_process` sends
  the media + slide files straight to Gemini multimodal, parses the returned
  transcript (with slide markers + speaker labels), and transitions
  `uploading → ready` directly (skipping the intermediate stages). See
  [ingest.py:141-158](../../app/tasks/ingest.py#L141-L158) and
  [ai_process.py:201-576](../../app/tasks/ai_process.py#L201-L576).

The orchestrator is `ingest_task` ([ingest.py:32-201](../../app/tasks/ingest.py#L32-L201)),
kicked off from `POST /v1/gcs/upload-complete`
([gcs_upload.py:198-206](../../app/api/gcs_upload.py#L198-L206)).

## Purpose

Convert raw uploaded media (video/audio + optional PDF/PPTX slides + optional
manifest/chat files) into structured, reviewer-ready data: time-stamped
`segments`, `words`, `speakers`, `slides` with `bullets`, slide `alignments`,
and `transcription_discrepancies`. This first pass is what the downstream Copy
Edit → Medical Review → Publish workflow refines. The pipeline is fully
automated — no operator action is required between upload and `ready`.

## User Value

- An operator uploads a recording and receives a complete first-pass transcript
  without manual transcription.
- Slide decks are matched to spoken segments automatically via a multi-signal
  fusion + alignment engine ([fusion.py](../../app/engines/fusion.py),
  [alignment.py](../../app/engines/alignment.py)).
- Filler words ("um", "uh") and Tier 1/2/3 disfluencies are removed under a
  template-driven policy, while clinical terms (drug names, doses) are preserved
  via a validate-and-repair safety net ([normalize.py:136-209](../../app/tasks/normalize.py#L136-L209)).
- The live progress screen shows which stage is running, elapsed time, an
  estimate of remaining time, and running counts of segments/markers/slides
  ([ProcessingView.vue:355-416](../../frontend/src/views/ProcessingView.vue#L355-L416)).
- On failure, the operator gets a category-specific message plus Retry and
  Delete actions ([ProcessingView.vue:333-353](../../frontend/src/views/ProcessingView.vue#L333-L353)).

## Navigation

- The processing screen is the route `/p/:id` (ProcessingView). The component
  documents its route as `/p/:id` ([ProcessingView.vue:3](../../frontend/src/views/ProcessingView.vue#L3)).
- On reaching `ready` (or `complete`), the view auto-redirects to the editor at
  `/e/:id` after a 600ms delay
  ([ProcessingView.vue:289-298](../../frontend/src/views/ProcessingView.vue#L289-L298)).
- The pipeline itself has no other dedicated UI surface; it is driven by Celery
  and observed over a WebSocket (`/v1/ws/sessions/{id}`) plus a 3-second polling
  fallback ([ProcessingView.vue:319](../../frontend/src/views/ProcessingView.vue#L319)).

## Screens

There is one screen for this module: **ProcessingView** (`/p/:id`),
[frontend/src/views/ProcessingView.vue](../../frontend/src/views/ProcessingView.vue).

It renders two mutually-exclusive cards:

1. **Processing card** ("Building your output") — shows the step list, a template
   badge, a progress bar with `% complete` / elapsed / estimated-remaining, and a
   metrics panel (Segments / Markers / Slides aligned over total).
   ([ProcessingView.vue:355-416](../../frontend/src/views/ProcessingView.vue#L355-L416))
2. **Failure card** — shown when `sessionStatus === 'failed'`. Displays a
   category title, the user-facing failure message, an optional tip (for
   `gemini_overloaded` and `gemini_context_overflow`), and Retry / Delete buttons.
   ([ProcessingView.vue:333-353](../../frontend/src/views/ProcessingView.vue#L333-L353))

The step list shown depends on the detected pipeline
([ProcessingView.vue:39-70](../../frontend/src/views/ProcessingView.vue#L39-L70)):

- **Standard:** Uploading video → Transcribing speech → Applying IIL →
  Detecting boundaries → Matching slides.
- **AI direct:** Preparing files → AI analysis → Mapping slides → Finalizing.
- **AI enhanced:** Uploading files → Transcribing speech → AI enhancement →
  Applying IIL → Matching slides.

## User Flows

### Standard / enhanced upload-to-ready

1. Upload completes; `POST /v1/gcs/upload-complete` inserts `sources`, reserves a
   rate-limit slot, parses any manifest/chat, and calls `enqueue_ingest`
   ([gcs_upload.py:110-219](../../app/api/gcs_upload.py#L110-L219)).
2. `ingest_task` checks the session is still `uploading`, refuses to re-run if
   `segments` already exist, then transitions `uploading → transcribing`, fans out
   `frame_task` (and `slide_extract_task` if slide sources exist) in parallel, and
   chains `transcribe_task → finalize_task`
   ([ingest.py:52-193](../../app/tasks/ingest.py#L52-L193)).
3. `transcribe_task` downloads the primary media, chunks it into N-minute WAVs
   (default 5 min), runs Google STT `long_running_recognize` per chunk in parallel,
   segments words via the deterministic 4-rule segmenter, and writes `segments` +
   `words` ([transcribe.py:43-216](../../app/tasks/transcribe.py#L43-L216),
   [segmenter.py:127-160](../../app/engines/segmenter.py#L127-L160)).
4. `transcribe_task` then triggers `anchor_task` and `template_autodetect_task`
   ([transcribe.py:198-214](../../app/tasks/transcribe.py#L198-L214)).
5. `anchor_task` reads `frame_task`'s visual signals from Redis (or proceeds with
   none), computes semantic shifts, detects ANCHORS-phrase anchors, stores
   `AnchorHit[]` in Redis, and triggers `normalize_task`
   ([anchor_task.py:39-148](../../app/tasks/anchor_task.py#L39-L148)).
6. `normalize_task` applies the template's filler policy + IIL tiers per segment,
   writes `normalization_results`, updates `segments.text`, transitions to
   `normalizing`, and triggers `fusion_task` + `lcs_discrepancies_task` (and
   enhanced AI refinement when applicable)
   ([normalize.py:35-312](../../app/tasks/normalize.py#L35-L312)).
7. `fusion_task` loads Redis signals, runs the locked-weight fusion engine + the
   5-assertion gate, writes `slide_time_ranges` + `replay_log`, transitions to
   `fusing`, and triggers `align_task`
   ([fusion.py:23-251](../../app/tasks/fusion.py#L23-L251)).
8. `align_task` runs the 4-signal alignment engine + pre-ready gate, writes
   `alignments` + `validation_results`, updates `segments.slide_id`, transitions to
   `aligning`, and triggers `finalize_task`
   ([align.py:36-432](../../app/tasks/align.py#L36-L432)).
9. `finalize_task` verifies segments exist, transitions through any remaining
   intermediate states to `ready`, releases the rate-limit slot, triggers
   `kp_task` + `sop_auto_init_task`, auto-places polls, and emits
   `timeline_ready` + final `metrics_update`
   ([finalize.py:27-162](../../app/tasks/finalize.py#L27-L162)).
10. ProcessingView sees the `ready` stage and redirects to `/e/:id`.

### AI Mode direct upload-to-ready

1. `ingest_task` sees `ai_pipeline = 'direct'`, enqueues `slide_extract_task` (if
   slide sources exist) and `ai_process_task`
   ([ingest.py:141-158](../../app/tasks/ingest.py#L141-L158)).
2. `ai_process_task._process_direct` downloads media + slides, calls Gemini
   multimodal with the mode-specific prompt, parses the response into segments
   with slide markers + speaker labels, runs a filler safety-net and a
   hallucination-loop truncator, assigns proportional timestamps, waits up to 60s
   for `slide_extract_task` to populate slide rows, then writes `speakers`,
   `slides`, `segments` atomically and transitions `uploading → ready`
   ([ai_process.py:201-534](../../app/tasks/ai_process.py#L201-L534)).
3. It then fires `stt_background_task` (word-level STT + discrepancies),
   `kp_task`, and `sop_auto_init_task`
   ([ai_process.py:543-564](../../app/tasks/ai_process.py#L543-L564)).
4. ProcessingView (driven by `processing_update` progress events 5→100) redirects
   to the editor on `ready`.

### Failure + retry

1. A terminal failure in any task triggers `RoundsTask.on_failure`, which
   categorizes the exception, transitions the session to `failed`, releases the
   rate-limit slot, and emits a `session_failed` WS event
   ([celery_app.py:115-191](../../app/tasks/celery_app.py#L115-L191)).
2. The failure card appears. **Retry** calls `sessions.retry(id)`, which maps to
   `POST /v1/diag/reingest/{id}`
   ([api.ts:178-180](../../frontend/src/services/api.ts#L178)).
3. `reingest` resets the session to `uploading`, deletes prior `segments`, logs an
   audit entry, and re-enqueues `ingest_task`
   ([diagnostics.py:94-171](../../app/api/diagnostics.py#L94-L171)).
4. **Delete & start over** calls `sessions.remove(id)`, soft-deleting the session
   ([ProcessingView.vue:268-286](../../frontend/src/views/ProcessingView.vue#L268-L286)).

## Business Rules

- **Single-pipeline routing:** `ingest_task` routes on
  `session_templates.ai_pipeline` — `'direct'` → Gemini multimodal; anything else
  (default `'enhanced'`) → STT chain
  ([ingest.py:88-141](../../app/tasks/ingest.py#L88-L141)).
- **No silent re-run:** `ingest_task` refuses to run if `segments` already exist,
  returning `segments_exist_no_reingest` — re-running must go through
  `/v1/diag/reingest`, which deletes segments first
  ([ingest.py:96-113](../../app/tasks/ingest.py#L96-L113)).
- **Empty transcript is fatal:** `transcribe_task` raises if STT returns 0 words,
  refusing to mark the session ready
  ([transcribe.py:106-107](../../app/tasks/transcribe.py#L106-L107)).
- **IIL policy floor:** the template's `filler_policy` caps which IIL tiers run —
  `light` allows only Tier 1; `medium` allows Tier 1+2; `strict` allows all three.
  `iil_config` tier flags can disable but cannot re-enable above the policy floor
  ([normalize.py:251-269](../../app/tasks/normalize.py#L251-L269)).
- **Clinical-safety fallback:** on terminal normalization-validation failure,
  `segments.text` keeps the raw STT verbatim — broken normalization never ships
  ([normalize.py:176-180](../../app/tasks/normalize.py#L176-L180)).
- **Anchor confirmation (Section 7):** an anchor is confirmed (confidence 0.9)
  only when an ANCHORS phrase appears AND a visual change is within
  ±`ANCHOR_CROSS_VALIDATE_WINDOW` OR a semantic shift > 0.3; otherwise it is
  speculative (confidence 0.3) and not used as a boundary signal
  ([anchor.py:56-105](../../app/engines/anchor.py#L56-L105)).
- **Signal gate (Section 2):** semantic signal alone cannot trigger a slide
  boundary when visual change is below threshold and no anchor is confirmed
  ([fusion.py:121-131](../../app/engines/fusion.py#L121-L131)).
- **Boundary timestamps locked to 0.5s** for replay reproducibility
  ([fusion.py:96-98](../../app/engines/fusion.py#L96-L98)).
- **Gemini hallucination-loop guard (BR-015):** in the AI direct path, any 80+
  char block repeated 3+ times in one segment is truncated to its first
  occurrence ([ai_process.py:37-82](../../app/tasks/ai_process.py#L37-L82)).
- **AI direct → ready shortcut:** the only legal `uploading → ready` transition is
  the AI Mode direct path ([state_machine.py:40-47](../../app/engines/state_machine.py#L40-L47)).
- **STT background is non-critical:** in the AI direct path, `stt_background_task`
  failures never mark the session failed (the Gemini transcript is authoritative)
  ([ai_process.py:837-860](../../app/tasks/ai_process.py#L837-L860)).
- **Locked processing weights** (fusion, alignment, anchor, IIL thresholds,
  retry/backoff) are pinned in [app/config.py:52-77](../../app/config.py#L52-L77)
  and protected by `tests/test_health.py::test_locked_weights_match_audit`.

## Validation Rules

- **Upload scope (R7):** `/v1/gcs/upload-complete` rejects any `gcs_uri` outside
  `gs://<bucket>/sessions/<id>/` with 400 VALIDATION_FAILED
  ([gcs_upload.py:128-137](../../app/api/gcs_upload.py#L128-L137)).
- **Session must exist** before sources are inserted (else 404)
  ([gcs_upload.py:139-146](../../app/api/gcs_upload.py#L139-L146)).
- **File validation** (`validate_files`): an `audio_enhance` source below a
  minimum byte size is rejected as likely-silent; `video`/`audio` durations over
  `MAX_VIDEO_DURATION_MINUTES` (180) are rejected
  ([rate_limit.py:98-129](../../app/middleware/rate_limit.py#L98-L129)).
- **Video duration cap in-pipeline:** both `frame_task` and `ai_process` re-check
  duration against `MAX_VIDEO_DURATION_MINUTES` and raise if exceeded
  ([frame_task.py:116-121](../../app/tasks/frame_task.py#L116-L121),
  [ai_process.py:357-363](../../app/tasks/ai_process.py#L357-L363)).
- **Fusion gate (5 assertions):** boundary count, spacing stddev, timeline
  coverage, no-overlap, and no-gaps-over-1s. A violation raises `GateFailure`
  ([fusion.py:383-449](../../app/engines/fusion.py#L383-L449)).
- **Pre-ready gate (5 assertions):** coverage, completeness (no null required
  fields), timestamps (start<end, no overlaps), template-id match, and IIL
  (normalized_text present when IIL enabled). A violation raises `GateFailure`
  ([pre_ready_gate.py:42-96](../../app/engines/pre_ready_gate.py#L42-L96)).
- **Fusion-output gate (Gate 1 in align):** if fusion produced 0 slide_time_ranges,
  `align_task` halts the session instead of fabricating an alignment
  ([align.py:91-110](../../app/tasks/align.py#L91-L110)).

## States

Session status is governed by the locked state machine
([state_machine.py:40-49](../../app/engines/state_machine.py#L40-L49)):

```
uploading    → transcribing | ready | failed
transcribing → normalizing  | failed
normalizing  → fusing       | failed
fusing       → aligning     | failed
aligning     → ready        | failed
ready        → complete     | failed
```

- `failed` and `complete` are terminal — no transitions out
  ([state_machine.py:49](../../app/engines/state_machine.py#L49),
  [:140-144](../../app/engines/state_machine.py#L140-L144)).
- Every transition appends a JSONB entry to `session_audit.processing_log` and
  emits a `processing_update` WS event
  ([state_machine.py:52-111](../../app/engines/state_machine.py#L52-L111)).
- A pre-ready / fusion-output gate failure inside `align_task` drives the session
  to `failed` with an `audit_events` row and an `align_gate_failed` WS event
  ([align.py:348-392](../../app/tasks/align.py#L348-L392)).

The intermediate processing stages (`transcribing`, `normalizing`, `fusing`,
`aligning`) exist only for the standard/enhanced chain. The AI Mode direct path
jumps `uploading → ready` and never visits them.

## Dependencies

- **Google Cloud Storage** — source media, slide decks, STT chunk staging, and
  slide thumbnails ([transcribe.py:274-356](../../app/tasks/transcribe.py#L274-L356),
  [slide_extract.py:277-279](../../app/tasks/slide_extract.py#L277-L279)).
- **Google Speech-to-Text** (`long_running_recognize`) — the standard/enhanced
  transcription backend ([transcribe.py:245-362](../../app/tasks/transcribe.py#L245-L362)).
- **Google Gemini (multimodal + text)** — the AI Mode direct/enhanced path and
  discrepancy classification ([ai_process.py:296-302](../../app/tasks/ai_process.py#L296-L302)).
- **FFmpeg / ffprobe** — audio chunking, frame extraction, duration probing
  ([transcribe.py:297-303](../../app/tasks/transcribe.py#L297-L303),
  [frame_task.py:202-211](../../app/tasks/frame_task.py#L202-L211)).
- **OpenCV (cv2) + NumPy** — visual change detection
  ([frame_task.py:214-263](../../app/tasks/frame_task.py#L214-L263)).
- **PyMuPDF (fitz) + python-pptx** — slide text/bullet/thumbnail extraction
  ([slide_extract.py:242-431](../../app/tasks/slide_extract.py#L242-L431)).
- **Redis** — Celery broker/result backend, rate-limit slots, and inter-task
  signal hand-off (frame → anchor → fusion)
  ([celery_app.py:26-29](../../app/tasks/celery_app.py#L26-L29),
  [frame_task.py:266-268](../../app/tasks/frame_task.py#L266-L268)).
- **PostgreSQL** — sessions, sources, segments, words, slides, alignments, etc.
- **IIL validation engine** (`app/iil/validation.py`) — per-segment validate-and-
  repair ([normalize.py:143-161](../../app/tasks/normalize.py#L143-L161)).

## Error Handling

- **Categorized failures:** `RoundsTask._categorize_exception` maps exceptions to
  stable categories (`gemini_overloaded`, `gemini_quota`, `gemini_config`,
  `gemini_error`, `storage_error`, `stt_error`, `validation_error`, `unknown`)
  with user-facing messages ([celery_app.py:92-145](../../app/tasks/celery_app.py#L92-L145)).
- **Retry with backoff:** retryable failures retry with exponential 60/120/240s
  delays plus optional jitter, up to `CELERY_MAX_RETRIES` (3)
  ([celery_app.py:194-212](../../app/tasks/celery_app.py#L194-L212)).
- **Fail-fast on terminal LLM categories:** `gemini_context_overflow`,
  `gemini_config`, `gemini_model_deprecated`, `validation_error` skip retries and
  mark the session failed immediately
  ([ai_process.py:132-145](../../app/tasks/ai_process.py#L132-L145),
  [llm_client.py:42-47](../../app/engines/llm_client.py#L42-L47)).
- **Graceful degradation:** `anchor_task` proceeds with empty visual signals if
  `frame_task` hasn't finished ([anchor_task.py:85-87](../../app/tasks/anchor_task.py#L85-L87));
  `slide_extract_task` and `lcs_discrepancies_task` swallow terminal errors and
  return rather than failing the session
  ([slide_extract.py:229-234](../../app/tasks/slide_extract.py#L229-L234),
  [lcs_discrepancies.py:195-201](../../app/tasks/lcs_discrepancies.py#L195-L201)).
- **Stuck-upload recovery:** `upload_watchdog_task` (Celery Beat, default OFF)
  re-enqueues sessions stuck on `uploading` past the threshold
  ([upload_watchdog.py:45-132](../../app/tasks/upload_watchdog.py#L45-L132)).
- **UI failure card:** category-specific titles + tips, with Retry / Delete
  actions and a polling fallback if the WS misses the failure event
  ([ProcessingView.vue:199-311](../../frontend/src/views/ProcessingView.vue#L199-L311)).

## Permissions

> Verified permission reality. Role-based authorization is scaffold-only.

- Every pipeline-adjacent API requires only a valid JWT (`CurrentUser`). There is
  no role check on `POST /v1/gcs/upload-complete`, `GET
  /{id}/pipeline-config`, or any `/v1/diag/*` operator endpoint — JWT presence is
  the only gate ([gcs_upload.py:111-115](../../app/api/gcs_upload.py#L111-L115),
  [diagnostics.py:94-95](../../app/api/diagnostics.py#L94-L95)).
- The role helper `app/security/roles.py` (`is_admin` / `require_admin`) exists but
  is documented as **"Phase 8 scaffold only — not yet wired into any endpoint"**;
  `auth_users.role` (migration 045) is not read by `get_current_user`
  ([roles.py:10-19](../../app/security/roles.py#L10-L19)).
- Real admin enforcement today is a hardcoded `user.email == "johndean@vin.com"`
  gate (`LEGACY_ADMIN_EMAIL`) reached via `require_admin`. In the sessions module
  it gates the soft-deleted-sessions list (`GET /v1/sessions/deleted`)
  ([sessions.py:266-277](../../app/api/sessions.py#L266-L277),
  [roles.py:54](../../app/security/roles.py#L54)). The processing pipeline tasks
  and the diagnostic rescue endpoints do not use it.

## Reporting Impacts

The pipeline populates the per-session metric columns that downstream views and
reports read:

- `sessions.duration_sec`, `word_count`, `segment_count` are set by
  `transcribe_task` / `ai_process` ([transcribe.py:175-192](../../app/tasks/transcribe.py#L175-L192),
  [ai_process.py:489-506](../../app/tasks/ai_process.py#L489-L506)).
- Live counts (segments, markers, slides total/aligned, duration) are emitted as
  `metrics_update` WS events and shown in the ProcessingView metrics panel
  ([finalize.py:148-155](../../app/tasks/finalize.py#L148-L155),
  [ProcessingView.vue:399-415](../../frontend/src/views/ProcessingView.vue#L399-L415)).
- `replay_log` records the exact fusion inputs/outputs + input hash for replay /
  audit ([fusion.py:198-212](../../app/tasks/fusion.py#L198-L212)).
- No dedicated reporting/analytics endpoint for the pipeline was found.
  **IMPLEMENTATION NOT FOUND** for pipeline-level aggregate reporting.

## Audit Requirements

- **State-transition log:** every status change appends a JSONB entry (stage,
  status, started_at, completed_at, actor, reason, metadata) to
  `session_audit.processing_log`; `ready` also stamps `finalized_at`
  ([state_machine.py:52-95](../../app/engines/state_machine.py#L52-L95)). Exposed
  read-only via `GET /v1/sessions/{id}/audit-log`
  ([sessions.py:306-320](../../app/api/sessions.py#L306-L320)).
- **Upload evidence:** `/v1/gcs/upload-complete` writes `audit_events` rows for
  sources, manifest parse, and chat parse
  ([gcs_upload.py:174-189](../../app/api/gcs_upload.py#L174-L189)).
- **Gate failures:** `align_task._halt_session` writes an `audit_events` row
  (`align.gate_failure`) with the gate id + reason
  ([align.py:362-374](../../app/tasks/align.py#L362-L374)).
- **Operator actions:** `reingest`, `abort-session`, and `upload_watchdog`
  re-enqueues all append `session_audit.processing_log` entries tagged with their
  actor ([diagnostics.py:132-153](../../app/api/diagnostics.py#L132-L153),
  [upload_watchdog.py:135-159](../../app/tasks/upload_watchdog.py#L135-L159)).

## Data Relationships

- `sessions` (1) → `sources` (N): uploaded media/slide/manifest/chat files
  ([gcs_upload.py:152-169](../../app/api/gcs_upload.py#L152-L169)).
- `sessions` (1) → `session_templates` (1): pipeline + IIL config read by ingest
  ([ingest.py:67-88](../../app/tasks/ingest.py#L67-L88)).
- `sessions` (1) → `segments` (N) → `words` (N): transcript hierarchy
  ([transcribe.py:112-174](../../app/tasks/transcribe.py#L112-L174)).
- `sessions` (1) → `slides` (N) → `bullets` (N): extracted deck content
  ([slide_extract.py:281-322](../../app/tasks/slide_extract.py#L281-L322)).
- `sessions` (1) → `speakers` (N): speaker roster (AI direct + alignment seed)
  ([ai_process.py:392-410](../../app/tasks/ai_process.py#L392-L410)).
- `slide_time_ranges` (fusion output) → `alignments` (align output, one per
  segment) → `validation_results` (verdict per alignment)
  ([fusion.py:159-197](../../app/tasks/fusion.py#L159-L197),
  [align.py:245-328](../../app/tasks/align.py#L245-L328)).
- `segments` ↔ `normalization_results` (1:1 via UNIQUE(session_id, segment_id))
  ([normalize.py:181-209](../../app/tasks/normalize.py#L181-L209)).
- `segments` → `transcription_discrepancies` + `word_alignment` (LCS diff output)
  ([lcs_discrepancies.py:118-174](../../app/tasks/lcs_discrepancies.py#L118-L174)).

## Known Constraints

- **Single worker replica:** Celery Beat is embedded into the worker via `-B`;
  the design assumes one replica so no leader election is needed
  ([celery_app.py:66-89](../../app/tasks/celery_app.py#L66-L89)).
- **Idempotency by content hash:** segments use a deterministic
  `content_hash = SHA256(session_id + start_ms)` as the conflict key, not
  `(session_id, seq)` — re-segmentation can shift seq while preserving the hash
  ([ai_process.py:442-453](../../app/tasks/ai_process.py#L442-L453),
  [segmenter.py:41-43](../../app/engines/segmenter.py#L41-L43)).
- **Slide-extract race in AI direct:** `ai_process` polls up to 60s for
  `slide_extract_task` rows; if none arrive it falls back to AI-marker placeholder
  slides ([ai_process.py:673-705](../../app/tasks/ai_process.py#L673-L705)).
- **Enhanced refinement is a no-op for transcript mode:** `_process_enhanced`
  returns immediately when `ai_mode == 'transcript'`
  ([ai_process.py:605-607](../../app/tasks/ai_process.py#L605-L607)).
- **Upload watchdog is feature-flagged OFF by default** — must be enabled via the
  `UPLOAD_WATCHDOG_ENABLED` env var on the worker
  ([config.py:100](../../app/config.py#L100)).
- **No video-only sessions break frame detection:** audio-only sessions skip
  visual signals cleanly ([frame_task.py:109-113](../../app/tasks/frame_task.py#L109-L113)).
- **Single-virtual-slide fallback:** sessions with no slides get one virtual
  full-session slide_time_range from fusion
  ([fusion.py:69-91](../../app/tasks/fusion.py#L69-L91)).
- **Default pipeline is `enhanced`,** but `_process_enhanced` only refines text for
  non-transcript AI modes; the standard STT chain (transcribe→…→finalize) is the
  effective path for plain transcript sessions
  ([ingest.py:88](../../app/tasks/ingest.py#L88),
  [ingest.py:160-182](../../app/tasks/ingest.py#L160-L182)).

## Source Verification
- **Files Used:** app/tasks/ingest.py, app/tasks/transcribe.py, app/tasks/ai_process.py, app/tasks/normalize.py, app/tasks/slide_extract.py, app/tasks/frame_task.py, app/tasks/anchor_task.py, app/tasks/fusion.py, app/tasks/align.py, app/tasks/lcs_discrepancies.py, app/tasks/finalize.py, app/tasks/upload_watchdog.py, app/tasks/celery_app.py, app/engines/anchor.py, app/engines/segmenter.py, app/engines/fusion.py, app/engines/alignment.py, app/engines/pre_ready_gate.py, app/engines/state_machine.py, app/engines/llm_client.py, app/config.py, app/api/gcs_upload.py, app/api/sessions.py, app/api/diagnostics.py, app/middleware/rate_limit.py, app/security/roles.py, frontend/src/views/ProcessingView.vue, frontend/src/services/api.ts
- **Components Used:** ProcessingView.vue (`/p/:id`)
- **APIs Used:** POST /v1/gcs/upload-url, POST /v1/gcs/upload-complete, GET /v1/sessions/{id}/pipeline-config, GET /v1/sessions/{id}/audit-log, GET /v1/sessions/deleted, POST /v1/diag/reingest/{id}, POST /v1/diag/realign/{id}, POST /v1/diag/abort-session/{id}
- **Database Tables Used:** sessions, sources, session_templates, segments, words, slides, bullets, speakers, slide_time_ranges, alignments, validation_results, normalization_results, transcription_discrepancies, word_alignment, replay_log, session_audit, audit_events, polls, poll_options, chat_messages
- **Permission Logic Used:** JWT presence (CurrentUser) on all pipeline endpoints; LEGACY_ADMIN_EMAIL ("johndean@vin.com") gate via require_admin only on GET /v1/sessions/deleted; role-based auth is scaffold-only (not wired)
- **Confidence Score:** High — every claim traced to a specific file:line in current source.
- **Evidence Links:** [ingest.py:32-201](../../app/tasks/ingest.py#L32-L201), [state_machine.py:40-49](../../app/engines/state_machine.py#L40-L49), [fusion.py:241-373](../../app/engines/fusion.py#L241-L373), [ProcessingView.vue:39-70](../../frontend/src/views/ProcessingView.vue#L39-L70), [config.py:52-77](../../app/config.py#L52-L77)
