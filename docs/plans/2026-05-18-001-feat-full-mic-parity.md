# Plan: Rounds → Full MIC Pipeline Parity (Zero-Gap)

**Type:** feat
**Status:** complete — all 17 phases shipped 2026-05-18
**Created:** 2026-05-18
**Predecessor:** [`2026-05-17-001-feat-rounds-bootstrap-plan.md`](./2026-05-17-001-feat-rounds-bootstrap-plan.md) (Phases 1-10 complete; ingest stub shipped)
**Scope:** Close every gap surfaced by the audit on 2026-05-18. Reach MIC SSOT parity on upload → ingest → render path.

---

## 1. Context

The audit on 2026-05-18 ([conversation transcript]) identified **24 critical + 18 major + 5 minor** gaps between Rounds and MIC's pipeline:

- Frame task / anchor task / normalize task / fusion task / AI MODE / classify task: **not ported**
- Words table / bullets table / alignments table / slide_time_ranges / replay_log / session_audit / validation_results: **not in schema**
- State machine (`ALLOWED_TRANSITIONS`): **not enforced**
- LOCKED weights (FUSION_*, ALIGN_*, IIL_*): **stored but unread**
- UploadView's 7 AI-selection form fields: **never reach backend**
- Settings AI Models / Discrepancy backend: **local refs only, no persistence**

This plan closes 100% of those gaps.

Estimated scope:
- ~6,700 LOC across `app/tasks/*.py`, `app/engines/*.py`, `app/api/*.py`, frontend wiring
- 14 new tables
- 17 implementation phases (6a-6q)
- 4-8 weeks of focused work

---

## 2. Phase Order & Implementation Units

### Phase 6a — Pipeline config schema + UploadView wiring

Makes the UploadView form's 7 AI-selection fields reach the backend. Foundational for 6d.

- **U73.** Migration `009_session_templates.sql` — `session_templates(session_id, ai_pipeline, ai_model, prompt_mode, custom_prompt, iil_config JSONB, template_id, auto_detected_template_id, auto_detected_confidence)`. `templates(id, name, filler_policy, structure_extraction, key_points, tone, terminology, rewrite)` + seed `lecture_v1`.
- **U74.** Extend `SessionIn` Pydantic to accept `pipeline_config: dict`. `POST /v1/sessions` writes `session_templates` row in same transaction.
- **U75.** UploadView `processBatch()` builds `pipeline_config` from `pipeline / aiMode / model / style / tier1-3 / stt / customPrompt` refs and sends with session create.
- **U76.** `org_settings` UPSERT for `default_ai_model`, `classify_backend`, `classify_model`. SectionAIModels / SectionDiscrepancy GET on mount + PUT on change.
- **U77.** Default ai_model / classify_backend prefills `UploadView` form on mount (read `/v1/settings`).

**Verify:** Upload with `pipeline=direct, model=gemini-2.5-pro` → `session_templates` row has `ai_pipeline='direct', ai_model='gemini-2.5-pro'`. SectionAIModels selection persists across reload.

### Phase 6b — State machine + session_audit

- **U78.** Migration `010_state_machine.sql` — `sessions.status CHECK IN ('uploading','transcribing','normalizing','fusing','aligning','ready','failed','ingesting')`. Add `session_audit(session_id, processing_log JSONB)`.
- **U79.** `app/engines/state_machine.py` ports MIC `ALLOWED_TRANSITIONS` map + `transition_session_sync()` + `transition_session()` async. Terminal `failed` enforcement. Row-lock via `SELECT FOR UPDATE`.
- **U80.** Replace every raw `UPDATE sessions SET status = '…'` in tasks with `transition_session_sync()`. Audit log append + WS publish hooks (WS noops until 6n).
- **U81.** `ConflictError` mapped to HTTP 409 with structured envelope.

**Verify:** Illegal transition (`ready→transcribing`) raises 409 `INVALID_TRANSITION`. Audit log accumulates one row per status change.

### Phase 6c — MICTask base class

- **U82.** `app/tasks/celery_app.py::RoundsTask(Task)` — `abstract=True`, `_backoff_base=settings.CELERY_RETRY_BACKOFF_BASE`, `on_failure()` categorizes via `_categorize_exception()`, calls `_fail_session()` (transitions to failed via state machine, releases Redis active-counter, emits WS).
- **U83.** `retry_with_backoff(exc, attempt)` = `60 * 2^attempt + jitter`. Replaces every task's hand-rolled retry block.
- **U84.** All 5 existing tasks (`ingest, transcribe, slide_extract, align, finalize`) switch to `base=RoundsTask`.

**Verify:** Forced exception in `transcribe_task` → session marked failed with categorized `user_message`. Retries follow 60/120/240s pattern.

### Phase 6d — AI MODE direct path (Pipeline 3)

The biggest user-facing unlock. With this shipped, `pipeline=direct` (UploadView default) becomes a real end-to-end path.

- **U85.** `app/tasks/ai_process.py::ai_process_task` — port `_process_direct` from MIC (869 LOC, but `direct` half is ~350 LOC). Reads `session_templates.iil_config`, downloads media from GCS, builds prompt (transcript / summary / key-moments / structured-notes / custom-prompt), calls `call_gemini_multimodal()`, parses response JSON.
- **U86.** Parse Gemini response → write `segments + words + slides + alignments` atomically. Transition `uploading → ready` directly.
- **U87.** `ingest_task` reads `session_templates.ai_pipeline`. If `direct`, `ai_process_task.delay()` and return. Else standard chain.
- **U88.** Custom-prompt support — reads `iil_config.custom_prompt` and substitutes for default system prompt.

**Verify:** Upload 5-min .mp4 with `pipeline=direct, ai_mode=transcript, model=gemini-2.5-flash` → segments written by Gemini, status flips ready, editor renders the transcript.

### Phase 6e — Frame task + anchor task

- **U89.** Migration `011_anchor.sql` — no new tables (Redis-backed), but adds `chat_messages.confirmed_anchor BOOL`, `polls.confirmed_anchor BOOL`.
- **U90.** `app/tasks/frame_task.py` — FFmpeg 1fps JPEG extraction → cv2 absdiff → 3-frame persistence → Bhattacharyya histogram stability → `VisualSignal[]` to Redis `rounds:frame:{id}` (TTL 86400). Reads `VISUAL_CHANGE_THRESHOLD=8.0`.
- **U91.** `app/engines/anchor.py` + `app/tasks/anchor_task.py` — reads frame signals from Redis + segments from DB → computes `semantic_shifts` from token overlap → `detect_anchors()` → AnchorHit[] to Redis. Anchor confirmed iff `visual_change within ±5s OR semantic_shift > 0.3`. Triggers `normalize_task`.
- **U92.** `ingest_task` triggers `transcribe` + `frame` in **parallel** (Celery `group()` not `chain()`). `transcribe` triggers `anchor` on completion. `anchor` triggers `normalize`.

**Verify:** Upload session with 5 slide transitions → Redis has VisualSignal[] + AnchorHit[]. Anchor count ≈ 5.

### Phase 6f — Manifest + chat parsers

- **U93.** Migration `012_manifest.sql` — `session_speakers(session_id, name, role, credentials, bio, sort_order)`, `session_slide_resources(session_id, slide_number, label, url, sort_order)`, `sessions` adds `code, title_long, title_short, ce_broker_id, class_id, tags JSONB, publishing_links JSONB, polls JSONB, polls_parsed JSONB`.
- **U94.** Port `app/services/extras2_parser.py` from MIC (manifest .txt → ParsedManifest with speakers/resources/polls/links).
- **U95.** `/v1/gcs/upload-complete` calls `_parse_manifest_from_gcs(session_id, manifest_uri)` after Source rows write. Updates session columns + writes speakers/resources rows. Non-fatal on parse failure.
- **U96.** Port `app/engines/chat_parser.py` — parses uploaded chat .txt → `chat_messages` rows. Hooked into `/upload-complete` for `role='chat'` sources.
- **U97.** Manifest summary returned in `/upload-complete` response (`speakers[], slide_resource_count, publishing_links[]`).

**Verify:** Upload `_manifest.txt` with 3 speakers + 5 slide resources → `session_speakers` has 3 rows, `session_slide_resources` has 5 rows. Frontend Session Detail shows speakers.

### Phase 6g — Normalize + IIL pipeline

- **U98.** Migration `013_normalize.sql` — `normalization_results(session_id, segment_id, normalized_text, template_id, validation_results JSONB)`, `templates(id, name, filler_policy, structure_extraction, key_points, tone, terminology, rewrite, filler_words JSONB)`. Seed `lecture_v1, training_v1, technical_v1, podcast_v1, sales_v1`.
- **U99.** `app/iil/validation.py` — 4-check repair loop (word_count, token_set, filler_compliance, terminology_preservation).
- **U100.** `app/tasks/normalize.py` — reads template config from `session_templates`, loads segments + words from DB, runs `validate_and_repair()` per segment, writes `normalization_results`.
- **U101.** IIL tier resolution — `iil_config.tier1/2/3` toggles + `filler_policy` floor logic.
- **U102.** Transitions `normalizing → fusing` after all segments normalized.

**Verify:** Session with `tier1=on, tier2=off, tier3=off` + `lecture_v1` template → normalized text drops "um/uh/er" but keeps "you know/basically". `normalization_results` row per segment.

### Phase 6h — Fusion engine

- **U103.** Migration `014_fusion.sql` — `slide_time_ranges(session_id, slide_id, start_time, end_time, slide_soft_start, slide_soft_end, confidence, sources JSONB, status, attempt_number)`. `replay_log(session_id, input_hash, fusion_inputs JSONB, fusion_output JSONB)`.
- **U104.** `app/engines/fusion.py` — `run_fusion(visual_signals, anchor_signals, semantic_shifts, total_duration)` consults `FUSION_WEIGHT_VISUAL=0.5 / ANCHOR=0.3 / SEMANTIC=0.2`, applies `FUSION_BOUNDARY_THRESHOLD=0.35`.
- **U105.** `app/tasks/fusion.py::fusion_task` — reads signals from Redis, runs engine, writes `slide_time_ranges` + `replay_log`. Rule 6 — replay log is non-optional.
- **U106.** `app/tasks/fusion.py::gate_task` — 5 assertions before `fusing → aligning`. Raises `GateFailure` on assertion failure.

**Verify:** Same session run twice with identical inputs → `replay_log.input_hash` matches. Removing one visual signal → different output. All 5 gate assertions pass.

### Phase 6i — Real align engine (4-signal scoring)

- **U107.** Migration `015_align.sql` — `alignments(session_id, segment_id, slide_id NULLABLE, confidence, signals JSONB, sources JSONB, drift_flag, anchor_hit, uncertain_flag, status CHECK IN ('assigned','uncertain','review'), attempt_number)`. `validation_results(alignment_id, verdict CHECK IN ('APPROVE','REVIEW','ESCALATE'))`.
- **U108.** `app/engines/alignment.py` — `align_segment(segment, slide_time_ranges, slides, bullets, normalization)` computes 4 signals (semantic, coverage, temporal, sequential) with `ALIGN_WEIGHT_*` weights.
- **U109.** Uncertain handling — `dominance < 0.6` → `slide_id=NULL, status='uncertain'`.
- **U110.** IIL drift flagging via `IIL_DRIFT_CONFIDENCE_PENALTY=0.3, IIL_DRIFT_REALIGN_WINDOW=20`.
- **U111.** `app/engines/pre_ready_gate.py` — 5 assertions before `aligning → ready`. Raises `GateFailure`.
- **U112.** `app/tasks/align.py` ports MIC's task body. Replaces today's time-proportional stub.

**Verify:** Session with 10 slides + 100 segments → `alignments` table has 100 rows with non-zero signals JSONB. 2-3 marked `uncertain`. Pre-ready gate emits 5 PASS log lines.

### Phase 6j — Words table + deterministic segment IDs

- **U113.** Migration `016_words.sql` — `words(id, segment_id, word, start_time, end_time, confidence CHECK 0-1)`. `segments.id` migration: TEXT (SHA256-style) + `CHECK (start_time < end_time)`.
- **U114.** `app/engines/segmenter.py` — port MIC's 4-rule deterministic segmenter (silence + max-length + punctuation + min-length).
- **U115.** `app/tasks/transcribe.py` writes `words` rows alongside `segments`. Segment ID = `SHA256(session_id + str(start_ms))`.
- **U116.** Backfill task `017_backfill_words.sql` — generate deterministic segment IDs for any existing rows.

**Verify:** Re-run transcribe on same session → segment IDs match (deterministic). `words` table populated. CHECK constraint blocks `start_time >= end_time`.

### Phase 6k — Slide extract upgrade

- **U117.** Migration `018_bullets.sql` — `bullets(slide_id, text, position, embedding vector(768))`. `slides` adds `slide_number INT, full_text TEXT, thumbnail_uri TEXT`.
- **U118.** Switch `app/tasks/slide_extract.py` from `pdftoppm` to PyMuPDF (`fitz`) — extract text + bullets + thumbnail per page.
- **U119.** PPTX MIME support via `python-pptx` (no LibreOffice needed for text extraction).
- **U120.** Multi-source handling — loop all PDF/PPTX source rows, not just first.
- **U121.** `Dockerfile` adds `python-pptx` (poetry) + keeps `poppler-utils` (only for PNG thumbs fallback).

**Verify:** Upload PDF with 24 pages and 5 bullets per slide → `slides` has 24 rows, `bullets` has 120 rows, each slide has `full_text` populated.

### Phase 6l — Discrepancy LCS + classify task

- **U122.** Migration `019_discrepancies_full.sql` — `transcription_discrepancies(session_id, segment_id, ai_text, stt_text, is_meaningful, classified_at, classifier_model)`.
- **U123.** `app/tasks/lcs_discrepancies.py` — runs LCS between raw STT (from `words`) and normalized text (from `normalization_results`) → writes discrepancy rows. Triggered by normalize completion.
- **U124.** `app/tasks/classify_task.py::classify_discrepancies_task` — actual Celery task (not just engine dispatcher). `_ClassifyTask.on_failure` override — never marks session failed.
- **U125.** Frontend Discrepancies tab gets populated from `/v1/sessions/{id}/discrepancies`.

**Verify:** Session with 5 LCS-detected differences → 5 discrepancy rows. Classify runs, all 5 have `is_meaningful` set. Failure path doesn't transition session.

### Phase 6m — AI MODE enhanced + template autodetect

- **U126.** `app/tasks/ai_process.py::_process_enhanced` — port MIC's enhanced path. Reads existing segments, sends transcript to Gemini for refinement, writes updated segments.
- **U127.** `ingest_task` routes `ai_pipeline=enhanced` to enhanced after normalize completes (not after transcribe).
- **U128.** `app/tasks/transcribe.py::template_autodetect_task` — non-blocking, runs on first 60s, writes `session_templates.auto_detected_template_id + auto_detected_confidence`. Lecture_v1 + confidence=0.0 on failure (TIL Rule 7).
- **U129.** Frontend exposes auto-detect result on Session Detail (not auto-applied, surfaced as suggestion).

**Verify:** Upload with `pipeline=enhanced, template=lecture` → standard pipeline runs, then AI MODE refines transcripts. `auto_detected_template_id` populates within 60s of upload.

### Phase 6n — WebSocket bridge

- **U130.** `app/engines/ws_bridge.py` — Redis pub/sub `rounds:ws:{session_id}` channel. `publish_ws_event_sync(session_id, payload)` for tasks. `start_ws_bridge(ws_manager)` for FastAPI lifespan.
- **U131.** `app/main.py` registers WS bridge in lifespan. `/v1/ws/sessions/{id}` endpoint connects clients.
- **U132.** Every task emits `processing_update` on status change. `session_failed` carries categorized payload. Classify emits `classification_failed`.
- **U133.** `ProcessingView` switches from 4s poll to WS subscribe. Falls back to poll if WS unavailable.
- **U134.** `EditorView` subscribes for live segment updates during ingest.

**Verify:** Upload session → ProcessingView shows hop status flip live without reload. Network tab shows WS frames, not poll requests.

### Phase 6o — Rate limit + idempotency

- **U135.** `app/middleware/rate_limit.py` — Redis `sessions:active:{user_email}` set, `MAX_CONCURRENT_SESSIONS=3`. `sessions:queue` length check, `MAX_QUEUE_LENGTH=10`.
- **U136.** `/v1/gcs/upload-url` rejects with 429 when over limit. `_fail_session()` releases counter.
- **U137.** `MAX_VIDEO_DURATION_MINUTES=180` enforcement — `/upload-complete` reads duration via ffprobe-as-a-service or trusts client-supplied `duration_sec`. Reject if over.
- **U138.** Multi-audio enhance size validator (per memory `feedback_multi_audio_stt_pollution`) — if `audio_enhance` < 100KB, reject with `VALIDATION_FAILED`.
- **U139.** `app/middleware/idempotency.py` — `Idempotency-Key` header → Redis lookup with `IDEMPOTENCY_KEY_TTL_SECONDS=86400`. Replay cached response on duplicate.
- **U140.** Apply idempotency middleware to POST `/v1/sessions`, `/v1/gcs/upload-complete`, mutating endpoints.

**Verify:** 4th concurrent upload by same user → 429. 19KB `audio_enhance.mp3` → 400 VALIDATION_FAILED. Duplicate POST with same `Idempotency-Key` → identical response from cache.

### Phase 6p — Artifact transformer + burn captions

- **U141.** Port `app/engines/artifact_transformer.py` (540 LOC) — generates `.docx, .srt, .txt, .zip, .vtt` from session segments + slides + normalization_results.
- **U142.** `/v1/sessions/{id}/exports/{format}` returns the artifact (streamed for .zip).
- **U143.** `app/tasks/burn_captions.py` (420 LOC) — ffmpeg burn-in pass writes captioned MP4 to GCS. Adds `captioned_video` artifact type.
- **U144.** Migration `020_artifacts.sql` — `artifacts(session_id, kind, gcs_uri, generated_at, generated_by)`.
- **U145.** Frontend Download menu actually fetches real artifacts.

**Verify:** Click Download → DOCX → file matches MIC's DOCX output byte-for-byte (when same inputs). Burn captions task produces playable MP4 with subtitles burned in.

### Phase 6q — IIL learning loop

- **U146.** Migration `021_iil_learning.sql` — `key_points_annotations(segment_id, label, score)`, `instructor_profiles(name, ...)`, `session_instructor_map(session_id, instructor_id)`, `session_patterns(session_id, pattern_name, frequency)`.
- **U147.** `app/tasks/kp_task.py` (234 LOC) — extracts key points from normalized transcript via Gemini.
- **U148.** `app/tasks/kp_task.py::learn_iil_task` — updates `instructor_profiles` based on patterns across that instructor's sessions.
- **U149.** Settings → AI Models surfaces learned per-instructor knobs (read-only summary).
- **U150.** Frontend Session Detail shows key points pinned by segment.

**Verify:** Same instructor on 3 sessions → `session_patterns` accumulates. KP annotations appear in Editor right rail.

---

## 3. Cross-cutting concerns

### Schema migrations sequence
009 → 021. All numbered, idempotent, applied by `scripts/migrate.py` in order. Each phase ships its own migration.

### Settings reads
Tasks consult `app.config.settings` for all LOCKED weights. Settings table (`org_settings`) is for user-tunable overrides (default model, classify backend, etc.) — never for processing weights.

### Backward compatibility
Existing sessions (status=`ingesting`, no `session_templates` row) get a default `session_templates` row backfilled by migration 009 with `ai_pipeline='enhanced', template_id='lecture_v1'`. They re-process correctly when manually re-triggered via `/v1/diag/reingest/{id}`.

### Frontend wiring per phase
Each backend phase has a matching frontend pass. UploadView gains the pipeline_config payload in 6a. SectionAIModels persists in 6a. ProcessingView gains hop status from real signals in 6e. EditorView gains discrepancies + key points from 6l + 6q.

---

## 4. Verification gate — end-to-end smoke

After 6q lands, this manual flow must pass cleanly on production:

1. Login as `johndean@vin.com`.
2. Set Settings → AI Models → default = `gemini-2.5-flash`. Reload — sticks.
3. Upload 5-minute test lecture (.mp4 + .pdf + extras2 manifest + chat.txt). Select `pipeline=enhanced, tier1/2/3=on, style=lecture, model=gemini-2.5-pro`.
4. Processing view shows live WS hop progression (not polled).
5. Manifest parsed: 3 speakers + 5 slide resources visible on Session Detail.
6. ~3 minutes later, session lands `ready`. Auto-redirect to editor.
7. Editor renders: segments (normalized, fillers removed), slides (with PyMuPDF-extracted bullets), real speaker chips, chat anchors (from chat parser).
8. Discrepancies tab shows LCS results, classified by Gemini.
9. Audit ledger reflects every state transition.
10. SOP auto-advanced to `prep`.
11. Download → DOCX produces a real-looking transcript.
12. Re-upload identical files with same `Idempotency-Key` → 200 + cached response (no duplicate session).
13. Upload 4th concurrent session as same user → 429.

When all 13 pass, plan is complete.

---

## 5. Estimated phase sizing

| Phase | LOC | New tables | Verify difficulty |
|---|---|---|---|
| 6a | 300 | 2 | Low |
| 6b | 250 | 1 | Low |
| 6c | 200 | 0 | Low |
| 6d | 600 | 0 | **High** (needs real Gemini call) |
| 6e | 700 | 0 | Medium |
| 6f | 500 | 2 | Low |
| 6g | 800 | 2 | Medium |
| 6h | 600 | 2 | Medium |
| 6i | 700 | 2 | Medium |
| 6j | 250 | 1 | Low |
| 6k | 300 | 1 | Low |
| 6l | 400 | 1 | Low |
| 6m | 400 | 0 | Medium |
| 6n | 200 | 0 | Medium |
| 6o | 150 | 0 | Low |
| 6p | 900 | 1 | Low |
| 6q | 500 | 4 | Medium |
| **Total** | **~6,700** | **19** | |

(Slightly higher than the audit estimate of 14 — split some tables for clarity.)

---

## 6. Open questions deferred to implementation

- Whether to keep PNG thumbnails alongside PyMuPDF (yes — Editor right rail needs them for the live preview).
- Whether `session_templates.id` should be UUID or `session_id` PK. (Pick PK — one template per session.)
- Whether WS reconnect logic lives in the frontend composable or the host (composable — `useSessionStatus(sessionId)`).
- Whether to migrate today's empty-DB production immediately or hold for batch deploy. (Batch — last phase commits trigger one Railway deploy.)

---

## 7. References

- 2026-05-18 audit report (this conversation, `compound-engineering:ce-adversarial-document-reviewer`-style audit).
- MIC SSOT: `C:\Users\JohnDean\Desktop\mic\` — every task body referenced by file:line.
- `docs/MIC-AUDIT.md` — the original MIC architecture reference shipped with Rounds.
- Memories: `feedback_multi_audio_stt_pollution.md`, `feedback_cost_consciousness.md`.
