# Processing Pipeline — Technical Spec

Developer-facing reference for the Celery DAG that drives a session from
`uploading` to `ready`.

> Every claim is verified against current code. File:line links are relative to
> this document's location (`docs/technical/`).

## Architecture

```
POST /v1/gcs/upload-complete
  └─ enqueue_ingest(session_id)
        └─ ingest_task                      (rounds.tasks.ingest)
              ├─ ai_pipeline == 'direct':
              │     ├─ slide_extract_task    (parallel, if slide sources)
              │     └─ ai_process_task       (Gemini multimodal → ready)
              │           └─ stt_background_task → lcs_discrepancies_task → classify
              │           └─ kp_task, sop_auto_init_task
              └─ else (standard / enhanced):
                    ├─ frame_task             (parallel, Redis signals)
                    ├─ slide_extract_task     (parallel, if slide sources)
                    └─ chain(transcribe_task, finalize_task)
                          transcribe_task
                            ├─ anchor_task    (reads frame Redis → Redis AnchorHit[])
                            │     └─ normalize_task
                            │           ├─ fusion_task → align_task → finalize_task
                            │           └─ lcs_discrepancies_task → classify
                            │           └─ (enhanced) ai_process_task refine
                            └─ template_autodetect_task
```

- The orchestrator is `ingest_task` ([app/tasks/ingest.py:32-201](../../app/tasks/ingest.py#L32-L201)).
- Tasks chain via two mechanisms: an explicit Celery `chain(transcribe, finalize)`
  ([ingest.py:181-182](../../app/tasks/ingest.py#L181-L182)) and in-task
  `apply_async` triggers (transcribe→anchor→normalize→fusion→align→finalize).
- `frame_task` runs in parallel and does **not** trigger anything; `anchor_task`
  reads its output from Redis at execution time, degrading gracefully to empty
  signals ([frame_task.py:21-22](../../app/tasks/frame_task.py#L21-L22),
  [anchor_task.py:85-87](../../app/tasks/anchor_task.py#L85-L87)).
- All tasks run on a single Celery queue (`celery`) with one worker replica;
  Celery Beat is embedded via `-B` ([celery_app.py:62-89](../../app/tasks/celery_app.py#L62-L89)).
- Tasks open their own synchronous SQLAlchemy engine
  (`DATABASE_URL.replace("+asyncpg", "")`) per invocation and dispose it in a
  `finally` ([ingest.py:47-48](../../app/tasks/ingest.py#L47-L48)).

## Frontend Components

- **ProcessingView.vue** (`/p/:id`) — the only frontend surface for this module
  ([frontend/src/views/ProcessingView.vue](../../frontend/src/views/ProcessingView.vue)).
  - Pulls live state from `useSyncController(id)` (WS-backed): `processingStage`,
    `processingProgress`, `processingSubstage`, `metrics`, `failureCategory`,
    `failureUserMessage` ([ProcessingView.vue:86-91](../../frontend/src/views/ProcessingView.vue#L86-L91)).
  - Subscribes to additional WS events via `useWsSubscriber`: `slide_progress`,
    `template_autodetect`, `polls_autoplaced`, `align_gate_failed`,
    `gemini_loop_truncated` ([ProcessingView.vue:95-133](../../frontend/src/views/ProcessingView.vue#L95-L133)).
  - Three step sets (`STANDARD_STEPS`, `AI_DIRECT_STEPS`, `AI_ENHANCED_STEPS`) and
    three stage→step maps select the rendered list based on the detected pipeline
    ([ProcessingView.vue:39-70](../../frontend/src/views/ProcessingView.vue#L39-L70)).
  - Polls `sessions.get(id)` every 3s and ticks elapsed time every 1s as a WS
    fallback ([ProcessingView.vue:314-327](../../frontend/src/views/ProcessingView.vue#L314-L327)).
  - On `ready`/`complete`, redirects to `/e/:id`
    ([ProcessingView.vue:289-298](../../frontend/src/views/ProcessingView.vue#L289-L298)).
- **API client** (`frontend/src/services/api.ts`): `sessions.retry(id)` →
  `POST /v1/diag/reingest/{id}`; `sessions.pipelineConfig(id)`; `sessions.get`;
  `sessions.remove`; `sessions.failureReason`
  ([api.ts:178-180](../../frontend/src/services/api.ts#L178)).

## Backend Services

| Task | Celery name | Module | Role |
|---|---|---|---|
| `ingest_task` | `rounds.tasks.ingest` | [ingest.py](../../app/tasks/ingest.py) | Orchestrator; routes pipeline, fans out, chains finalize |
| `transcribe_task` | `rounds.tasks.transcribe` | [transcribe.py](../../app/tasks/transcribe.py) | Chunked Google STT → segments + words |
| `ai_process_task` | `rounds.tasks.ai_process` | [ai_process.py](../../app/tasks/ai_process.py) | Gemini multimodal (direct) / text refine (enhanced) |
| `stt_background_task` | `rounds.tasks.stt_background` | [ai_process.py:711](../../app/tasks/ai_process.py#L711) | Post-direct word-level STT + discrepancies |
| `template_autodetect_task` | `rounds.tasks.template_autodetect` | [ai_process.py:866](../../app/tasks/ai_process.py#L866) | Heuristic template suggestion |
| `frame_task` | `rounds.tasks.frame` | [frame_task.py](../../app/tasks/frame_task.py) | FFmpeg + cv2 visual-change signals → Redis |
| `anchor_task` | `rounds.tasks.anchor` | [anchor_task.py](../../app/tasks/anchor_task.py) | Visual + semantic + phrase anchors → Redis |
| `normalize_task` | `rounds.tasks.normalize` | [normalize.py](../../app/tasks/normalize.py) | IIL filler/terminology normalization |
| `slide_extract_task` | `rounds.tasks.slide_extract` | [slide_extract.py](../../app/tasks/slide_extract.py) | PDF/PPTX → slides + bullets + thumbnails |
| `slide_extract_selected_pages_task` | `rounds.tasks.slide_extract.selected_pages` | [slide_extract.py:31](../../app/tasks/slide_extract.py#L31) | Re-extract specific PDF pages |
| `fusion_task` | `rounds.tasks.fusion` | [fusion.py](../../app/tasks/fusion.py) | Boundary fusion → slide_time_ranges + replay_log |
| `align_task` | `rounds.tasks.align` | [align.py](../../app/tasks/align.py) | 4-signal segment→slide alignment |
| `lcs_discrepancies_task` | `rounds.tasks.lcs_discrepancies` | [lcs_discrepancies.py](../../app/tasks/lcs_discrepancies.py) | LCS diff → discrepancies + word_alignment |
| `finalize_task` | `rounds.tasks.finalize` | [finalize.py](../../app/tasks/finalize.py) | Mark ready; trigger KP + SOP init |
| `upload_watchdog_task` | `rounds.tasks.upload_watchdog` | [upload_watchdog.py](../../app/tasks/upload_watchdog.py) | Beat: recover stuck uploads |

Downstream tasks triggered by the pipeline (outside the assigned scope but
referenced): `rounds.tasks.classify_discrepancies` ([classify_task.py:57](../../app/tasks/classify_task.py#L57)),
`rounds.tasks.kp` ([kp_task.py:26](../../app/tasks/kp_task.py#L26)),
`rounds.tasks.sop.auto_init` + `rounds.tasks.sop.check_deadlines`
([sop_tasks.py:51](../../app/tasks/sop_tasks.py#L51), [:452](../../app/tasks/sop_tasks.py#L452)).

### Engines

| Engine | Module | Responsibility |
|---|---|---|
| Segmenter | [segmenter.py](../../app/engines/segmenter.py) | Deterministic 4-rule word→segment grouping, SHA256 ids |
| Anchor | [anchor.py](../../app/engines/anchor.py) | ANCHORS phrase detection + cross-validation + semantic shifts |
| Fusion | [fusion.py](../../app/engines/fusion.py) | Weighted boundary fusion + 5-assertion gate |
| Alignment | [alignment.py](../../app/engines/alignment.py) | 4-signal per-segment slide scoring |
| Pre-ready gate | [pre_ready_gate.py](../../app/engines/pre_ready_gate.py) | 5-assertion completeness gate |
| State machine | [state_machine.py](../../app/engines/state_machine.py) | ALLOWED_TRANSITIONS, audit append, WS emit |
| LLM client | [llm_client.py](../../app/engines/llm_client.py) | Gemini calls + LLMError categories |

## APIs

| Method | Path | File:Line | Auth |
|---|---|---|---|
| POST | `/v1/gcs/upload-url` | [gcs_upload.py:69](../../app/api/gcs_upload.py#L69) | CurrentUser (JWT) |
| POST | `/v1/gcs/upload-complete` | [gcs_upload.py:110](../../app/api/gcs_upload.py#L110) | CurrentUser (JWT) |
| GET | `/v1/sessions/{id}/pipeline-config` | [sessions.py:323](../../app/api/sessions.py#L323) | CurrentUser (JWT) |
| GET | `/v1/sessions/{id}/audit-log` | [sessions.py:306](../../app/api/sessions.py#L306) | CurrentUser (JWT) |
| GET | `/v1/sessions/deleted` | [sessions.py:266](../../app/api/sessions.py#L266) | require_admin (LEGACY_ADMIN_EMAIL) |
| POST | `/v1/diag/reingest/{id}` | [diagnostics.py:94](../../app/api/diagnostics.py#L94) | CurrentUser (JWT) |
| POST | `/v1/diag/realign/{id}` | [diagnostics.py:180](../../app/api/diagnostics.py#L180) | CurrentUser (JWT) |
| POST | `/v1/diag/abort-session/{id}` | [diagnostics.py:433](../../app/api/diagnostics.py#L433) | CurrentUser (JWT) |
| POST | `/v1/diag/autoplace-polls/{id}` | [diagnostics.py:251](../../app/api/diagnostics.py#L251) | CurrentUser (JWT) |
| POST | `/v1/diag/init-session-stages/{id}` | [diagnostics.py:209](../../app/api/diagnostics.py#L209) | CurrentUser (JWT) |

`POST /v1/gcs/upload-url` returns a 60-minute v4 PUT signed URL plus the scoped
`gcs_uri` ([gcs_upload.py:69-86](../../app/api/gcs_upload.py#L69-L86)).
`POST /v1/gcs/upload-complete` validates files, enforces R7 scope, inserts
`sources`, reserves the rate-limit slot, parses manifest/chat, and calls
`enqueue_ingest` ([gcs_upload.py:110-219](../../app/api/gcs_upload.py#L110-L219)).

## Data Models

Verified columns are those the pipeline reads/writes (not full DDL):

- **sources**: `session_id`, `role` (`video`/`audio`/`audio_enhance`/`slide`/
  `manifest`/`chat`/`other`), `filename`, `gcs_uri` (UNIQUE), `content_type`,
  `size_bytes`, `duration_sec` ([gcs_upload.py:154-169](../../app/api/gcs_upload.py#L154-L169)).
- **session_templates**: `ai_pipeline`, `ai_mode`, `ai_model`, `prompt_mode`,
  `custom_prompt`, `template_id`, `iil_config` (jsonb), `auto_detected_template_id`,
  `auto_detected_confidence` ([ai_process.py:104-113](../../app/tasks/ai_process.py#L104-L113),
  [ai_process.py:960-971](../../app/tasks/ai_process.py#L960-L971)).
- **segments**: `id`, `session_id`, `seq`, `start_ms`, `end_ms`, `text`,
  `confidence`, `flags` (jsonb), `slide_id`, `speaker_id`, `content_hash`,
  `updated_at`. UNIQUE conflict key is `(session_id, content_hash)`
  ([transcribe.py:116-136](../../app/tasks/transcribe.py#L116-L136),
  [ai_process.py:455-485](../../app/tasks/ai_process.py#L455-L485)).
- **words**: `id`, `segment_id`, `seq`, `word`, `start_ms`, `end_ms`,
  `confidence`. Conflict key `(segment_id, seq)`
  ([transcribe.py:154-174](../../app/tasks/transcribe.py#L154-L174)).
- **slides**: `session_id`, `slide_index`, `title`, `image_uri`, `thumbnail_uri`,
  `full_text`, `start_ms`, `end_ms`. Conflict key `(session_id, slide_index)`
  ([slide_extract.py:285-304](../../app/tasks/slide_extract.py#L285-L304),
  [fusion.py:188-197](../../app/tasks/fusion.py#L188-L197)).
- **bullets**: `slide_id`, `text`, `position`. Conflict key `(slide_id, position)`
  ([slide_extract.py:311-321](../../app/tasks/slide_extract.py#L311-L321)).
- **speakers**: `session_id`, `name`, `role`, `avatar_color`
  ([ai_process.py:399-408](../../app/tasks/ai_process.py#L399-L408)).
- **slide_time_ranges**: `session_id`, `slide_id`, `start_time`, `end_time`,
  `slide_soft_start`, `slide_soft_end`, `confidence`, `sources` (jsonb), `status`
  ([fusion.py:163-184](../../app/tasks/fusion.py#L163-L184)).
- **alignments**: `session_id`, `segment_id`, `slide_id`, `confidence`, `signals`
  (jsonb), `sources` (jsonb), `drift_flag`, `anchor_hit`, `uncertain_flag`,
  `status`, `attempt_number`. Conflict key `(session_id, segment_id)`
  ([align.py:250-266](../../app/tasks/align.py#L250-L266)).
- **validation_results**: `alignment_id`, `verdict` (`APPROVE`/`REVIEW`),
  `details` (jsonb) ([align.py:314-320](../../app/tasks/align.py#L314-L320)).
- **normalization_results**: `session_id`, `segment_id`, `normalized_text`,
  `template_id`, `validation_results` (jsonb), `repair_applied`, `repair_attempts`.
  Conflict key `(session_id, segment_id)`
  ([normalize.py:185-198](../../app/tasks/normalize.py#L185-L198)).
- **transcription_discrepancies**: `session_id`, `segment_id`, `ai_text`,
  `stt_text`, `category` ([lcs_discrepancies.py:124-137](../../app/tasks/lcs_discrepancies.py#L124-L137)).
- **word_alignment**: `segment_id`, `gemini_idx`, `stt_word_id`, `stt_start_ms`,
  `stt_end_ms`, `match_kind`. Conflict key `(segment_id, gemini_idx)`
  ([lcs_discrepancies.py:152-162](../../app/tasks/lcs_discrepancies.py#L152-L162)).
- **replay_log**: `session_id`, `input_hash`, `fusion_inputs` (jsonb),
  `fusion_output` (jsonb) ([fusion.py:201-211](../../app/tasks/fusion.py#L201-L211)).
- **session_audit**: `session_id`, `processing_log` (jsonb array), `updated_at`,
  `finalized_at` ([state_machine.py:79-95](../../app/engines/state_machine.py#L79-L95)).
- **audit_events**: `session_id`, `actor_email`, `kind`, `summary`, `details`
  (jsonb) ([gcs_upload.py:176-189](../../app/api/gcs_upload.py#L176-L189),
  [align.py:365-373](../../app/tasks/align.py#L365-L373)).

> Migration files were not opened for this spec; column claims are derived from
> the SQL the tasks execute. The seed doc maps these to migrations
> (001_init, 009, 011, 013, 014, 015, 036). **NOT VERIFIED IN CODE** at the
> migration-DDL level.

## Events

WebSocket events published by the pipeline (consumed by ProcessingView /
useSyncController):

| Event `type` | Emitted by | Payload keys |
|---|---|---|
| `processing_update` | state machine + ai_process | `stage`, `progress`, `substage` |
| `metrics_update` | ai_process, slide_extract, finalize | `segments`, `markers?`, `slides_total?`, `slides_aligned?`, `duration_sec?`, `speakers?` |
| `session_failed` | RoundsTask, ai_process, abort-session | `category`, `user_message`, `reason` |
| `slide_progress` | slide_extract (PDF) | `slide`, `total` |
| `stt_ready` | stt_background | `word_count` |
| `stt_background_failed` | stt_background failure | `reason` |
| `gemini_loop_truncated` | ai_process | `segments_truncated` |
| `template_autodetect` | template_autodetect | `template_id`, `confidence` |
| `timeline_ready` | finalize | (none) |
| `align_gate_failed` | align halt | `gate`, `reason` |

Evidence: [state_machine.py:98-111](../../app/engines/state_machine.py#L98-L111),
[ai_process.py:229-236](../../app/tasks/ai_process.py#L229-L236),
[celery_app.py:176-191](../../app/tasks/celery_app.py#L176-L191),
[slide_extract.py:268-272](../../app/tasks/slide_extract.py#L268-L272),
[finalize.py:148-155](../../app/tasks/finalize.py#L148-L155),
[align.py:386-390](../../app/tasks/align.py#L386-L390).

## State Management

- The session lifecycle is the only stateful surface, owned by the state machine
  ([state_machine.py:40-49](../../app/engines/state_machine.py#L40-L49)).
- `transition_session_sync` (Celery) locks the session row `FOR UPDATE`, validates
  the move against `ALLOWED_TRANSITIONS`, raises `ConflictError` on an illegal move
  or terminal source state, flips status, appends the audit log, and emits WS — all
  in one transaction ([state_machine.py:114-170](../../app/engines/state_machine.py#L114-L170)).
- Inter-task signals are passed via Redis with a 24h TTL:
  `rounds:frame:{id}` + `rounds:frame:done:{id}` (frame),
  `rounds:anchor:{id}` + `rounds:anchor:done:{id}` + `rounds:semantic:{id}` (anchor)
  ([frame_task.py:39-42](../../app/tasks/frame_task.py#L39-L42),
  [anchor_task.py:27-30](../../app/tasks/anchor_task.py#L27-L30)).
- Each task is idempotent via check-before-execute guards (existing rows or Redis
  done flags) ([transcribe.py:52-59](../../app/tasks/transcribe.py#L52-L59),
  [fusion.py:43-51](../../app/tasks/fusion.py#L43-L51),
  [frame_task.py:74-77](../../app/tasks/frame_task.py#L74-L77)).

## Validation

- **R7 scope** — `find_out_of_scope_uri` rejects any `gcs_uri` not under
  `gs://<bucket>/sessions/<id>/` ([gcs_upload.py:128-137](../../app/api/gcs_upload.py#L128-L137)).
- **validate_files** — minimum `audio_enhance` bytes + max media duration
  ([rate_limit.py:98-129](../../app/middleware/rate_limit.py#L98-L129)).
- **Segmenter rules** — 1 split-on-punctuation, 2 merge <2s, 3 split >20s, 4 split
  on ≥500ms silence, applied in locked order
  ([segmenter.py:127-160](../../app/engines/segmenter.py#L127-L160)).
- **Fusion gate** (`run_fusion_gate`) — 5 assertions on the slide_time_ranges
  ([fusion.py:383-449](../../app/engines/fusion.py#L383-L449)).
- **Pre-ready gate** (`run_pre_ready_gate`) — 5 assertions on the gate-input dicts
  ([pre_ready_gate.py:42-96](../../app/engines/pre_ready_gate.py#L42-L96)).
- **Anchor cross-validation** — confirmed iff phrase + (visual within window OR
  semantic > 0.3) ([anchor.py:84-101](../../app/engines/anchor.py#L84-L101)).
- **Repetition-loop guard** — MIN_BLOCK=80, MIN_REPS=3
  ([ai_process.py:63-82](../../app/tasks/ai_process.py#L63-L82)).

## Security

- All pipeline endpoints require a valid JWT via the `CurrentUser` dependency;
  there is no per-endpoint role check on upload-complete, pipeline-config, or the
  `/v1/diag/*` rescue routes ([gcs_upload.py:70](../../app/api/gcs_upload.py#L70),
  [diagnostics.py:95](../../app/api/diagnostics.py#L95)).
- The R7 invariant prevents an upload-complete caller from registering media
  outside the session's own GCS prefix
  ([gcs_upload.py:128-137](../../app/api/gcs_upload.py#L128-L137)).
- Rate limiting: `check_user_quota` rejects when the user already has
  `MAX_CONCURRENT_SESSIONS` (3) in flight or the global queue exceeds
  `MAX_QUEUE_LENGTH` (10) ([rate_limit.py:33-66](../../app/middleware/rate_limit.py#L33-L66),
  [config.py:46-47](../../app/config.py#L46-L47)). Slots are reserved on
  upload-complete and released on success/failure
  ([gcs_upload.py:148](../../app/api/gcs_upload.py#L148),
  [finalize.py:84-90](../../app/tasks/finalize.py#L84-L90)).
- Secrets (`GCP_KEY_B64`, `GEMINI_API_KEY`) come from env/Settings; the pipeline
  reads them via `app.config.settings` ([config.py:32-90](../../app/config.py#L32-L90)).

## Permissions

> Verified permission reality. Role-based authorization is scaffold-only.

- The pipeline tasks run server-side under the worker process; they have no
  user-permission concept.
- API access is gated by JWT presence only. No pipeline-related endpoint reads a
  role. `app/security/roles.py` (`is_admin`/`require_admin`) is documented as not
  yet wired into endpoints, and `auth_users.role` (migration 045) is not loaded by
  `get_current_user` ([roles.py:10-19](../../app/security/roles.py#L10-L19)).
- The single real authorization gate adjacent to this module is the hardcoded
  `user.email == "johndean@vin.com"` (`LEGACY_ADMIN_EMAIL`) check via
  `require_admin`, used on `GET /v1/sessions/deleted`
  ([roles.py:54](../../app/security/roles.py#L54),
  [sessions.py:276](../../app/api/sessions.py#L276)). The diagnostic
  reingest/realign/abort endpoints used to recover pipelines do **not** apply it.
- The frontend `adminOnly` route guard (router/index.ts) is client-side only and
  not a backend authorization control. **NOT VERIFIED IN CODE** which routes it
  protects (not in scope of files read).

## Integrations

- **Google Cloud Storage** (`google.cloud.storage`) — signed PUT URLs, source
  download, chunk staging, thumbnail upload, manifest/chat text read
  ([gcs_upload.py:492-502](../../app/api/gcs_upload.py#L492-L502),
  [transcribe.py:368-377](../../app/tasks/transcribe.py#L368-L377)).
- **Google Speech-to-Text** (`google.cloud.speech`) — `long_running_recognize`,
  LINEAR16/16kHz/en-US, word offsets + auto punctuation
  ([transcribe.py:316-329](../../app/tasks/transcribe.py#L316-L329)).
- **Google Gemini** via `app.engines.llm_client.call_gemini_multimodal` /
  `call_gemini_text` ([ai_process.py:224](../../app/tasks/ai_process.py#L224),
  [ai_process.py:602](../../app/tasks/ai_process.py#L602)). Model from
  `session_templates.ai_model`; classify default `GEMINI_CLASSIFY_MODEL`
  (`gemini-2.5-flash-lite`) ([config.py:85](../../app/config.py#L85)).
- **FFmpeg / ffprobe** — subprocess calls for chunking, frame sampling, stream +
  duration probing ([transcribe.py:297-303](../../app/tasks/transcribe.py#L297-L303),
  [frame_task.py:176-211](../../app/tasks/frame_task.py#L176-L211)).
- **OpenCV / NumPy** — grayscale absdiff + histogram Bhattacharyya distance
  ([frame_task.py:214-263](../../app/tasks/frame_task.py#L214-L263)).
- **PyMuPDF (fitz)** + **python-pptx** — slide extraction
  ([slide_extract.py:242-258](../../app/tasks/slide_extract.py#L242-L258),
  [slide_extract.py:358-369](../../app/tasks/slide_extract.py#L358-L369)).
- **Redis** — broker/backend + signal hand-off + rate-limit sets.

## Background Jobs

- The entire module is background work on Celery. App config:
  `task_acks_late=True`, `task_reject_on_worker_lost=True`,
  `worker_prefetch_multiplier=1`, JSON serializer, UTC
  ([celery_app.py:51-64](../../app/tasks/celery_app.py#L51-L64)).
- **Beat schedule** ([celery_app.py:71-89](../../app/tasks/celery_app.py#L71-L89)):
  - `upload-watchdog` every `UPLOAD_WATCHDOG_INTERVAL_SEC` (60s) — returns
    `{"disabled": True}` unless `UPLOAD_WATCHDOG_ENABLED`
    ([upload_watchdog.py:67-68](../../app/tasks/upload_watchdog.py#L67-L68)).
  - `sop-check-deadlines` every 3600s.
- **Per-task retry policy:** `ingest`/`slide_extract`/`align` `max_retries=2`;
  `transcribe`/`ai_process`/`normalize`/`frame`/`anchor`/`fusion` `max_retries=3`;
  `finalize`/`template_autodetect` `max_retries=1`; `stt_background`
  `max_retries=1`; `upload_watchdog` `max_retries=0`
  (see each task decorator, e.g. [ingest.py:36](../../app/tasks/ingest.py#L36),
  [transcribe.py:41](../../app/tasks/transcribe.py#L41)).
- **STT parallelism:** chunks transcribe in a ThreadPool sized
  `min(12, chunk_count)` ([transcribe.py:346](../../app/tasks/transcribe.py#L346)).
- **Watchdog match criteria:** `status='uploading'`, `updated_at` older than
  `UPLOAD_STUCK_THRESHOLD_SEC` (300), has an audio/video source, and no recent
  `upload_watchdog`-tagged audit within `UPLOAD_WATCHDOG_COOLDOWN_SEC` (600);
  LIMIT 50/tick ([upload_watchdog.py:74-100](../../app/tasks/upload_watchdog.py#L74-L100)).

## Error Handling

- **RoundsTask.on_failure** (base class) categorizes the exception, transitions to
  `failed`, releases the rate-limit slot, and emits `session_failed`
  ([celery_app.py:115-191](../../app/tasks/celery_app.py#L115-L191)).
- **retry_with_backoff** raises Celery `Retry` with countdown
  `60 * 2**attempt` + optional 10% jitter
  ([celery_app.py:194-212](../../app/tasks/celery_app.py#L194-L212)).
- **Terminal LLM categories** (`gemini_context_overflow`, `gemini_config`,
  `gemini_model_deprecated`, `validation_error`) bypass retries
  ([llm_client.py:42-47](../../app/engines/llm_client.py#L42-L47),
  [ai_process.py:138-139](../../app/tasks/ai_process.py#L138-L139),
  [transcribe.py:224-230](../../app/tasks/transcribe.py#L224-L230)).
- **`_fail_session_terminal`** in ai_process maps category→user_message and emits
  a `session_failed` WS event ([ai_process.py:150-195](../../app/tasks/ai_process.py#L150-L195)).
- **Gate failures** (`fusion`, `pre_ready_gate`) raise `GateFailure`; in
  `align_task` this halts the session with an `audit_events` row + WS event rather
  than retrying ([align.py:231-242](../../app/tasks/align.py#L231-L242)).
- **Non-fatal tasks:** `slide_extract`, `lcs_discrepancies`, and `stt_background`
  return error dicts / log warnings without marking the session failed
  ([slide_extract.py:229-234](../../app/tasks/slide_extract.py#L229-L234),
  [lcs_discrepancies.py:195-201](../../app/tasks/lcs_discrepancies.py#L195-L201),
  [ai_process.py:837-856](../../app/tasks/ai_process.py#L837-L856)).
- **Frontend** hydrates the failure reason from `sessions.failureReason` when the
  WS missed the `session_failed` event
  ([ProcessingView.vue:301-311](../../frontend/src/views/ProcessingView.vue#L301-L311)).

## Performance Considerations

- **Parallel fan-out:** `frame_task` + `slide_extract_task` run alongside the
  transcribe chain; the chain reads frame output from Redis when it runs
  ([ingest.py:160-182](../../app/tasks/ingest.py#L160-L182)).
- **Chunked STT:** media is split into 5-minute WAVs (`TRANSCRIPTION_CHUNK_MINUTES`)
  and transcribed in parallel threads, reducing wall-clock for long media
  ([transcribe.py:282-349](../../app/tasks/transcribe.py#L282-L349),
  [config.py:81](../../app/config.py#L81)).
- **Frame sampling rate** is `FRAME_SAMPLE_FPS=2` (locked), bounding the number of
  frames decoded ([config.py:52](../../app/config.py#L52),
  [frame_task.py:124](../../app/tasks/frame_task.py#L124)).
- **Pre-flight token probe** in the LLM client estimates input tokens against
  per-model context limits to fail-fast before paying upload + generate cost
  ([llm_client.py:50-67](../../app/engines/llm_client.py#L50-L67)).
- **Hallucination-loop truncation** caps runaway Gemini output that would burn
  100k+ tokens ([ai_process.py:55-62](../../app/tasks/ai_process.py#L55-L62)).
- **Bounded watchdog scan:** LIMIT 50 per beat tick
  ([upload_watchdog.py:93](../../app/tasks/upload_watchdog.py#L93)).
- **Per-task engine lifecycle:** each task creates and disposes its own sync engine;
  there is no shared connection pool across tasks (a deliberate isolation choice,
  at the cost of connection setup per task) ([ingest.py:47-201](../../app/tasks/ingest.py#L47-L201)).

## Source Verification
- **Files Used:** app/tasks/ingest.py, app/tasks/transcribe.py, app/tasks/ai_process.py, app/tasks/normalize.py, app/tasks/slide_extract.py, app/tasks/frame_task.py, app/tasks/anchor_task.py, app/tasks/fusion.py, app/tasks/align.py, app/tasks/lcs_discrepancies.py, app/tasks/finalize.py, app/tasks/upload_watchdog.py, app/tasks/celery_app.py, app/tasks/classify_task.py, app/tasks/kp_task.py, app/tasks/sop_tasks.py, app/engines/anchor.py, app/engines/segmenter.py, app/engines/fusion.py, app/engines/alignment.py, app/engines/pre_ready_gate.py, app/engines/state_machine.py, app/engines/llm_client.py, app/config.py, app/api/gcs_upload.py, app/api/sessions.py, app/api/diagnostics.py, app/middleware/rate_limit.py, app/security/roles.py, frontend/src/views/ProcessingView.vue, frontend/src/services/api.ts
- **Components Used:** ProcessingView.vue, useSyncController, useWsSubscriber, services/api.ts
- **APIs Used:** POST /v1/gcs/upload-url, POST /v1/gcs/upload-complete, GET /v1/sessions/{id}/pipeline-config, GET /v1/sessions/{id}/audit-log, GET /v1/sessions/deleted, POST /v1/diag/reingest/{id}, POST /v1/diag/realign/{id}, POST /v1/diag/abort-session/{id}, POST /v1/diag/autoplace-polls/{id}, POST /v1/diag/init-session-stages/{id}
- **Database Tables Used:** sessions, sources, session_templates, segments, words, slides, bullets, speakers, slide_time_ranges, alignments, validation_results, normalization_results, transcription_discrepancies, word_alignment, replay_log, session_audit, audit_events, polls, poll_options, chat_messages, session_speakers, session_slide_resources
- **Permission Logic Used:** JWT presence (CurrentUser) on all pipeline endpoints; LEGACY_ADMIN_EMAIL gate via require_admin only on GET /v1/sessions/deleted; role-based auth scaffold-only
- **Confidence Score:** High — task graph, weights, events, and SQL all traced to current source.
- **Evidence Links:** [celery_app.py:51-89](../../app/tasks/celery_app.py#L51-L89), [ingest.py:141-193](../../app/tasks/ingest.py#L141-L193), [fusion.py:241-449](../../app/engines/fusion.py#L241-L449), [state_machine.py:114-170](../../app/engines/state_machine.py#L114-L170), [config.py:52-103](../../app/config.py#L52-L103)
