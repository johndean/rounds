# Workflow: Ingest Pipeline (uploading → ready)

This is the Celery-driven pipeline that turns an uploaded session's media + slide files into a first-pass transcript with segments, slides, speakers, and slide alignment, ending in `sessions.status = 'ready'`.

There are two distinct paths, selected by `session_templates.ai_pipeline`:

- **`enhanced`** (default) — STT-based chain: `transcribe → anchor → normalize → fusion → align → finalize`, with `frame` + `slide_extract` running in parallel.
- **`direct`** (AI MODE) — single `ai_process` task sends media + slides straight to Gemini multimodal and writes everything atomically, marking `ready` itself. `slide_extract` runs in parallel.

The orchestrator reads the chosen path at [app/tasks/ingest.py:88](../../app/tasks/ingest.py#L88) and branches at [app/tasks/ingest.py:141](../../app/tasks/ingest.py#L141).

---

## Trigger

- `enqueue_ingest(session_id)` calls `ingest_task.apply_async(args=[session_id], queue="celery")` ([app/tasks/ingest.py:204](../../app/tasks/ingest.py#L204)). The module docstring states this is called from `/v1/gcs/upload-complete` ([app/tasks/ingest.py:5](../../app/tasks/ingest.py#L5)).
- `ingest_task` itself is the entry point ([app/tasks/ingest.py:38](../../app/tasks/ingest.py#L38)).
- Downstream tasks are triggered by their predecessors, not by the orchestrator:
  - `transcribe_task` triggers `anchor_task` ([app/tasks/transcribe.py:201](../../app/tasks/transcribe.py#L201)) and `template_autodetect_task` ([app/tasks/transcribe.py:212](../../app/tasks/transcribe.py#L212)) at the end of STT.
  - `anchor_task` triggers `normalize_task` ([app/tasks/anchor_task.py:145](../../app/tasks/anchor_task.py#L145)).
  - `normalize_task` triggers `fusion_task` + `lcs_discrepancies_task` (and enhanced `ai_process_task` when `ai_mode != 'transcript'`) ([app/tasks/normalize.py:272](../../app/tasks/normalize.py#L272)).
  - `fusion_task` triggers `align_task` ([app/tasks/fusion.py:242](../../app/tasks/fusion.py#L242)).
  - `align_task` triggers `finalize_task` ([app/tasks/align.py:419](../../app/tasks/align.py#L419)).
  - `frame_task` does NOT trigger a successor — `anchor_task` reads its Redis output ([app/tasks/frame_task.py:21](../../app/tasks/frame_task.py#L21)).
- The `enhanced` orchestration also chains `transcribe_task.s() | finalize_task.s()` explicitly so `finalize` always runs ([app/tasks/ingest.py:181](../../app/tasks/ingest.py#L181)).

## Inputs

- `session_id` (string UUID) — the only argument to every task.
- `session_templates` row — `ai_pipeline`, `ai_mode`, `ai_model`, `prompt_mode`, `custom_prompt`, `iil_config`, `template_id` (read at [app/tasks/ingest.py:67](../../app/tasks/ingest.py#L67), [app/tasks/ai_process.py:104](../../app/tasks/ai_process.py#L104), [app/tasks/normalize.py:62](../../app/tasks/normalize.py#L62)).
- `sources` rows — media (`role IN ('video','audio','audio_enhance')`) and slide files (`role = 'slide'`). Source selection priority differs by task; e.g. transcribe orders `video, audio, else` ([app/tasks/transcribe.py:61](../../app/tasks/transcribe.py#L61)) while ai_process orders `audio, audio_enhance, video, slide` ([app/tasks/ai_process.py:241](../../app/tasks/ai_process.py#L241)).
- GCS media bytes — downloaded per task via `gs://` URI helpers.
- `frame_task` Redis output (`rounds:frame:{id}`) consumed by `anchor_task`; `anchor_task` Redis output (`rounds:anchor:{id}` / `rounds:semantic:{id}`) consumed by `fusion_task` ([app/tasks/frame_task.py:39](../../app/tasks/frame_task.py#L39), [app/tasks/anchor_task.py:27](../../app/tasks/anchor_task.py#L27)).

### Locked processing constants (read from config)

- `TRANSCRIPTION_BACKEND = "google_stt_chunked"`, `TRANSCRIPTION_CHUNK_MINUTES = 5` ([app/config.py:80](../../app/config.py#L80)).
- `FRAME_SAMPLE_FPS = 2`, `VISUAL_CHANGE_THRESHOLD = 8.0` ([app/config.py:52](../../app/config.py#L52)); `_HIST_BHATT_THRESHOLD = 0.05` ([app/tasks/frame_task.py:42](../../app/tasks/frame_task.py#L42)).
- `MAX_VIDEO_DURATION_MINUTES = 180` ([app/config.py:49](../../app/config.py#L49)) — enforced in `frame_task` ([app/tasks/frame_task.py:116](../../app/tasks/frame_task.py#L116)) and `ai_process` direct ([app/tasks/ai_process.py:357](../../app/tasks/ai_process.py#L357)).

## Validations

- **Status gate (ingest):** `ingest_task` skips unless `sessions.status = 'uploading'` ([app/tasks/ingest.py:61](../../app/tasks/ingest.py#L61)). Missing session → `{"skipped": True, "reason": "not_found"}` ([app/tasks/ingest.py:58](../../app/tasks/ingest.py#L58)).
- **Re-run guard (ingest):** if segments already exist, `ingest_task` refuses to re-run and instructs the operator to call `/v1/diag/reingest/{id}` first ([app/tasks/ingest.py:101](../../app/tasks/ingest.py#L101)).
- **Check-before-execute (per task, idempotency):** `transcribe` skips if segments exist ([app/tasks/transcribe.py:53](../../app/tasks/transcribe.py#L53)); `slide_extract` skips if slides exist ([app/tasks/slide_extract.py:176](../../app/tasks/slide_extract.py#L176)); `frame`/`anchor` skip on a Redis `done` flag ([app/tasks/frame_task.py:75](../../app/tasks/frame_task.py#L75), [app/tasks/anchor_task.py:53](../../app/tasks/anchor_task.py#L53)); `normalize` skips if `normalization_results` exist ([app/tasks/normalize.py:52](../../app/tasks/normalize.py#L52)); `fusion` skips if `slide_time_ranges` exist ([app/tasks/fusion.py:44](../../app/tasks/fusion.py#L44)); `align` skips if `alignments` exist ([app/tasks/align.py:53](../../app/tasks/align.py#L53)).
- **No-source errors:** transcribe raises if no media source ([app/tasks/transcribe.py:77](../../app/tasks/transcribe.py#L77)); ai_process raises `LLMError` if no sources / no media ([app/tasks/ai_process.py:261](../../app/tasks/ai_process.py#L261)).
- **Empty-transcript guard:** transcribe raises if STT returned 0 words ([app/tasks/transcribe.py:106](../../app/tasks/transcribe.py#L106)); ai_process raises if Gemini returns an empty transcript or it empties after cleanup ([app/tasks/ai_process.py:306](../../app/tasks/ai_process.py#L306), [app/tasks/ai_process.py:350](../../app/tasks/ai_process.py#L350)).
- **Video-too-long:** `frame_task` and ai_process direct raise when duration exceeds `MAX_VIDEO_DURATION_MINUTES` ([app/tasks/frame_task.py:116](../../app/tasks/frame_task.py#L116), [app/tasks/ai_process.py:357](../../app/tasks/ai_process.py#L357)).
- **Gemini hallucination-loop detector (BR-015):** repeated ≥80-char block ×3 is truncated to first occurrence ([app/tasks/ai_process.py:37](../../app/tasks/ai_process.py#L37), called at [app/tasks/ai_process.py:331](../../app/tasks/ai_process.py#L331)).
- **Fusion gate:** `run_fusion_gate(...)` enforces a 5-assertion bounded check before persist ([app/tasks/fusion.py:156](../../app/tasks/fusion.py#L156)); raises `GateFailure` ([app/tasks/fusion.py:230](../../app/tasks/fusion.py#L230)).
- **Align GATE 1 (fusion_output):** if fusion produced 0 `slide_time_ranges`, the session is halted (no time-proportional fallback) ([app/tasks/align.py:96](../../app/tasks/align.py#L96)).
- **Align GATE 2 (pre_ready_gate):** `run_pre_ready_gate(...)` runs before the persist transaction; `GateFailure` halts the session ([app/tasks/align.py:231](../../app/tasks/align.py#L231)).
- **Finalize segment check:** if `segments` count is 0, finalize transitions to `failed` with reason `no_segments` ([app/tasks/finalize.py:59](../../app/tasks/finalize.py#L59)).
- **GCS scope (R7):** out-of-scope `gcs_uri` enforcement lives at upload-complete, not in these tasks (see CLAUDE.md backend boundaries). NOT VERIFIED IN CODE within the files listed for this workflow.

## Approvals

None. The ingest pipeline is fully automated; there is no human approval step between `uploading` and `ready`. Reviewer-facing workflow (Copy Edit → Medical Review → Publish) is the separate SOP layer documented in [sop-stage-advancement.md](./sop-stage-advancement.md).

## Notifications

WebSocket events are published via `publish_ws_event_sync(session_id, {...})`. Observed event types:

- `processing_update` (with `stage`, `progress`, `substage`) — ai_process direct, e.g. progress 5/10/20/30/40/70/75/80/85/95/100 ([app/tasks/ai_process.py:229](../../app/tasks/ai_process.py#L229)).
- `metrics_update` — ai_process ([app/tasks/ai_process.py:310](../../app/tasks/ai_process.py#L310), [app/tasks/ai_process.py:509](../../app/tasks/ai_process.py#L509)), slide_extract ([app/tasks/slide_extract.py:211](../../app/tasks/slide_extract.py#L211)), finalize ([app/tasks/finalize.py:149](../../app/tasks/finalize.py#L149)).
- `slide_progress` / `slide_extract` per-page progress ([app/tasks/slide_extract.py:268](../../app/tasks/slide_extract.py#L268)).
- `gemini_loop_truncated` ([app/tasks/ai_process.py:341](../../app/tasks/ai_process.py#L341)).
- `stt_ready` / `stt_background_failed` (background STT for AI MODE direct) ([app/tasks/ai_process.py:818](../../app/tasks/ai_process.py#L818), [app/tasks/ai_process.py:850](../../app/tasks/ai_process.py#L850)).
- `template_autodetect` ([app/tasks/ai_process.py:974](../../app/tasks/ai_process.py#L974)).
- `align_gate_failed` ([app/tasks/align.py:386](../../app/tasks/align.py#L386)).
- `timeline_ready` ([app/tasks/finalize.py:148](../../app/tasks/finalize.py#L148)).
- `session_failed` (with `category`, `user_message`) on terminal failure ([app/tasks/celery_app.py:179](../../app/tasks/celery_app.py#L179), [app/tasks/ai_process.py:177](../../app/tasks/ai_process.py#L177)).

Email notifications: none in the ingest pipeline. (SMTP email exists only in the SOP deadline path — see [sop-stage-advancement.md](./sop-stage-advancement.md).)

## Outputs

Database rows written:

- `segments` (+ per-word `words`) — transcribe ([app/tasks/transcribe.py:119](../../app/tasks/transcribe.py#L119)) or ai_process direct ([app/tasks/ai_process.py:455](../../app/tasks/ai_process.py#L455)). Idempotency key is `content_hash` via `ON CONFLICT (session_id, content_hash)`.
- `sessions.duration_sec / word_count / segment_count` updated ([app/tasks/transcribe.py:175](../../app/tasks/transcribe.py#L175), [app/tasks/ai_process.py:489](../../app/tasks/ai_process.py#L489)).
- `slides` + `bullets` (+ uploaded thumbnail PNGs to `gs://<bucket>/sessions/<id>/slides/`) — slide_extract for PDF ([app/tasks/slide_extract.py:281](../../app/tasks/slide_extract.py#L281)) and PPTX ([app/tasks/slide_extract.py:392](../../app/tasks/slide_extract.py#L392)).
- `speakers` — ai_process direct ([app/tasks/ai_process.py:399](../../app/tasks/ai_process.py#L399)); align inserts a placeholder `Presenter` if none exist ([app/tasks/align.py:148](../../app/tasks/align.py#L148)).
- `normalization_results` (one per segment) + rewritten `segments.text` — normalize ([app/tasks/normalize.py:186](../../app/tasks/normalize.py#L186)).
- `slide_time_ranges` + `replay_log` + `slides.start_ms/end_ms` — fusion ([app/tasks/fusion.py:165](../../app/tasks/fusion.py#L165), [app/tasks/fusion.py:199](../../app/tasks/fusion.py#L199)).
- `alignments` + `validation_results` + `segments.slide_id/speaker_id` — align ([app/tasks/align.py:250](../../app/tasks/align.py#L250), [app/tasks/align.py:315](../../app/tasks/align.py#L315), [app/tasks/align.py:281](../../app/tasks/align.py#L281)).
- `transcription_discrepancies` + `word_alignment` — lcs_discrepancies ([app/tasks/lcs_discrepancies.py:124](../../app/tasks/lcs_discrepancies.py#L124), [app/tasks/lcs_discrepancies.py:152](../../app/tasks/lcs_discrepancies.py#L152)).
- `session_templates.auto_detected_template_id / auto_detected_confidence` — template_autodetect ([app/tasks/ai_process.py:960](../../app/tasks/ai_process.py#L960)).
- Redis: `rounds:frame:{id}` + done flag (frame), `rounds:anchor:{id}` / `rounds:semantic:{id}` + done flag (anchor) ([app/tasks/frame_task.py:266](../../app/tasks/frame_task.py#L266), [app/tasks/anchor_task.py:108](../../app/tasks/anchor_task.py#L108)).

Downstream tasks fired from finalize / ai_process completion: `kp_task`, `sop_auto_init_task`, `auto_place_polls`, plus `stt_background_task` + `lcs_discrepancies_task` for the direct path ([app/tasks/finalize.py:94](../../app/tasks/finalize.py#L94), [app/tasks/ai_process.py:547](../../app/tasks/ai_process.py#L547)).

## Status Changes

Session statuses are mutated only through the state machine ([app/engines/state_machine.py:40](../../app/engines/state_machine.py#L40)). Allowed transitions:

```
uploading    → transcribing | ready | failed
transcribing → normalizing  | failed
normalizing  → fusing       | failed
fusing       → aligning     | failed
aligning     → ready        | failed
ready        → complete     | failed
```

Pipeline progression (enhanced path):

- `ingest_task`: `uploading → transcribing` ([app/tasks/ingest.py:167](../../app/tasks/ingest.py#L167)).
- `normalize_task`: `transcribing → normalizing` ([app/tasks/normalize.py:213](../../app/tasks/normalize.py#L213)).
- `fusion_task`: `normalizing → fusing` ([app/tasks/fusion.py:215](../../app/tasks/fusion.py#L215)).
- `align_task`: `fusing → aligning` ([app/tasks/align.py:415](../../app/tasks/align.py#L415)).
- `finalize_task`: `aligning → ready` (with legacy intermediate-state walk if invoked early) ([app/tasks/finalize.py:69](../../app/tasks/finalize.py#L69)).

Direct path: `ai_process_task` transitions `uploading → ready` directly ([app/tasks/ai_process.py:529](../../app/tasks/ai_process.py#L529)).

Failure: any task's terminal failure transitions to `failed` (see Exception Handling). Align gate halts also set `failed` ([app/tasks/align.py:379](../../app/tasks/align.py#L379)). Finalize sets `failed` on `no_segments` ([app/tasks/finalize.py:61](../../app/tasks/finalize.py#L61)).

## Audit Events

- Every state-machine transition appends a JSONB entry to `session_audit.processing_log` (`{stage, status, started_at, completed_at, metadata}`) ([app/engines/state_machine.py:52](../../app/engines/state_machine.py#L52)).
- Align gate failures additionally INSERT an `audit_events` row with `kind = 'align.gate_failure'` ([app/tasks/align.py:366](../../app/tasks/align.py#L366)).

No other `audit_events` rows are written by the ingest tasks listed for this workflow.

## Exception Handling

- **Retry discipline:** all tasks subclass `RoundsTask` and retry with exponential backoff (60/120/240s, optional jitter) up to each task's `max_retries` ([app/tasks/celery_app.py:194](../../app/tasks/celery_app.py#L194)). `max_retries` per task: ingest 2, transcribe 3, ai_process 3, normalize 3, frame 3, anchor 3, fusion 3, align 2, slide_extract 2, lcs_discrepancies 2, finalize 1.
- **Terminal failure handling:** `RoundsTask.on_failure` categorizes the exception, transitions the session to `failed`, releases the rate-limit slot, and emits `session_failed` ([app/tasks/celery_app.py:115](../../app/tasks/celery_app.py#L115)). Categories: `gemini_overloaded | gemini_quota | gemini_config | gemini_error | storage_error | stt_error | validation_error | unknown` ([app/tasks/celery_app.py:92](../../app/tasks/celery_app.py#L92)).
- **Fail-fast on terminal LLM categories:** transcribe and ai_process re-raise without retry when an `LLMError` is in `TERMINAL_LLM_CATEGORIES`; ai_process marks the session `failed` with a category-specific `user_message` ([app/tasks/transcribe.py:226](../../app/tasks/transcribe.py#L226), [app/tasks/ai_process.py:138](../../app/tasks/ai_process.py#L138), [app/tasks/ai_process.py:150](../../app/tasks/ai_process.py#L150)).
- **Non-fatal tasks (do NOT mark session failed):**
  - `slide_extract` returns `{slide_count: 0, error}` on terminal failure ([app/tasks/slide_extract.py:233](../../app/tasks/slide_extract.py#L233)).
  - `lcs_discrepancies` returns `{error}` — "discrepancies are an editor convenience, not a gate" ([app/tasks/lcs_discrepancies.py:199](../../app/tasks/lcs_discrepancies.py#L199)).
  - `template_autodetect` returns `lecture_v1 / 0.0` confidence on failure ([app/tasks/ai_process.py:986](../../app/tasks/ai_process.py#L986)).
  - `stt_background_task` uses `_SttBackgroundTask.on_failure` that never marks the session failed (AI MODE transcript is authoritative); emits `stt_background_failed` ([app/tasks/ai_process.py:837](../../app/tasks/ai_process.py#L837)).
- **Graceful degradation:** `anchor_task` proceeds with empty visual signals if `frame_task` hasn't finished ([app/tasks/anchor_task.py:86](../../app/tasks/anchor_task.py#L86)); fusion writes a single virtual slide range when there are 0 slides ([app/tasks/fusion.py:69](../../app/tasks/fusion.py#L69)); ai_process direct polls up to 60s for slide rows then falls back to placeholder slides ([app/tasks/ai_process.py:673](../../app/tasks/ai_process.py#L673)).

### Feature-flagged related tasks (defaults OFF)

- **Upload watchdog** — re-enqueues stuck `uploading` sessions. Default OFF; env flag `UPLOAD_WATCHDOG_ENABLED` (default `False`), interval `UPLOAD_WATCHDOG_INTERVAL_SEC` (default 60) ([app/config.py:100](../../app/config.py#L100), [app/tasks/upload_watchdog.py:17](../../app/tasks/upload_watchdog.py#L17)). Beat schedule registered at [app/tasks/celery_app.py:71](../../app/tasks/celery_app.py#L71).

---

## Source Verification
- **Files Used:** app/tasks/ingest.py, app/tasks/transcribe.py, app/tasks/ai_process.py, app/tasks/normalize.py, app/tasks/frame_task.py, app/tasks/slide_extract.py, app/tasks/anchor_task.py, app/tasks/fusion.py, app/tasks/align.py, app/tasks/lcs_discrepancies.py, app/tasks/finalize.py, app/tasks/celery_app.py, app/engines/state_machine.py, app/tasks/upload_watchdog.py, app/config.py
- **Components Used:** none (backend pipeline; no frontend components)
- **APIs Used:** trigger documented as `/v1/gcs/upload-complete` (per ingest.py docstring; the handler file itself was not read for this workflow); `/v1/diag/reingest/{id}` referenced as the reset path
- **Database Tables Used:** sessions, session_templates, sources, segments, words, slides, bullets, speakers, normalization_results, slide_time_ranges, replay_log, alignments, validation_results, transcription_discrepancies, word_alignment, session_audit (processing_log), audit_events; Redis keys `rounds:frame:*`, `rounds:anchor:*`, `rounds:semantic:*`
- **Permission Logic Used:** none (Celery worker tasks — no JWT/HTTP auth on task execution)
- **Confidence Score:** High — every claim traced to a read source line; the upload-complete trigger handler was not opened but is documented in the ingest task docstring.
- **Evidence Links:** [app/tasks/ingest.py:141](../../app/tasks/ingest.py#L141), [app/engines/state_machine.py:40](../../app/engines/state_machine.py#L40), [app/tasks/align.py:96](../../app/tasks/align.py#L96), [app/tasks/celery_app.py:115](../../app/tasks/celery_app.py#L115)
