# Quality & AI Accuracy — Technical Spec

> Module key: `quality-discrepancies`. Paths are relative to this file (`docs/technical/`). Every claim is tied to a source line.

## Architecture

The module spans three layers:

1. **Producer (Celery):** `lcs_discrepancies_task` LCS-diffs each segment's raw STT words against its AI/normalized text, inserting one `transcription_discrepancies` row per word-level divergence and, in the same transaction, populating `word_alignment` for the editor's per-word highlighter ([../../app/tasks/lcs_discrepancies.py:26](../../app/tasks/lcs_discrepancies.py#L26)). It then enqueues classify.
2. **Classifier (Celery + Gemini/Vertex):** `classify_discrepancies_task` loads unclassified rows, batches them (15/batch), calls Gemini (or Vertex), and writes `category` + `is_meaningful` verdicts ([../../app/tasks/classify_task.py:60](../../app/tasks/classify_task.py#L60)).
3. **Read + resolve (FastAPI + Vue):** `GET /v1/sessions/{id}/discrepancies` lists rows; the editor's `DiscrepanciesPane` renders the AI↔STT comparison; `POST /v1/sessions/{id}/corrections` (`text_edit`/`mark_ok`) auto-closes a discrepancy ([../../app/api/discrepancies.py:49](../../app/api/discrepancies.py#L49); [../../app/api/corrections.py:602](../../app/api/corrections.py#L602)).

A parallel **alignment review queue** (`GET /v1/sessions/{id}/review-queue`) ranks `uncertain`/`review` alignment rows by a fixed priority function ([../../app/api/corrections.py:978](../../app/api/corrections.py#L978)). The **IIL normalization + validation engine** is the upstream producer of the "AI text" side and enforces the raw-STT clinical-safety fallback ([../../app/iil/validation.py:212](../../app/iil/validation.py#L212)).

## Frontend Components

### `DiscrepanciesPane.vue`

- **Props:** `activeSegmentId`, `focusedSlideId`, `slideRailMode`, `liveSegments`, `liveSlides`, `liveDiscrepancies`, `liveWords`, `sessionId` ([../../frontend/src/components/editor/DiscrepanciesPane.vue:36](../../frontend/src/components/editor/DiscrepanciesPane.vue#L36)).
- **Emits:** `segmentClick`, `clearFocus`, `requestEdit`, `discrepancyResolved` ([DiscrepanciesPane.vue:47](../../frontend/src/components/editor/DiscrepanciesPane.vue#L47)).
- **State:** `mode` (`all`|`flagged`|`meaningful`, default `flagged`); `resolving` (a `Set` guarding double-fire) ([DiscrepanciesPane.vue:55](../../frontend/src/components/editor/DiscrepanciesPane.vue#L55), [DiscrepanciesPane.vue:83](../../frontend/src/components/editor/DiscrepanciesPane.vue#L83)).
- **Derived:** `flagsBySeg` groups `DiscrepancyRow[]` by `segment_id`; `meaningfulSegmentIds` keeps segments with any `is_meaningful === true`; `totalDiffs`/`meaningfulCount` drive the toolbar ([DiscrepanciesPane.vue:109](../../frontend/src/components/editor/DiscrepanciesPane.vue#L109)).
- **`renderSTT`:** joins `liveWords` for a segment, finds each `stt_text` fragment's byte range, merges overlapping ranges, then emits HTML-escaped text with `<mark class="compare-diff">` wrappers (single-pass to avoid matching inside an injected tag) ([DiscrepanciesPane.vue:157](../../frontend/src/components/editor/DiscrepanciesPane.vue#L157)).
- **`onMarkOk(seg, dismiss)`:** POSTs a `mark_ok` correction with empty old/new text (and `note: 'dismissed'` when dismissing — see Validation), then optimistically emits `discrepancyResolved` ([DiscrepanciesPane.vue:62](../../frontend/src/components/editor/DiscrepanciesPane.vue#L62)).
- **Data-test-ids:** `seg-edit-disc`, `seg-reassign-disc`, `seg-mark-ok-<id>`, `seg-dismiss-<id>` ([DiscrepanciesPane.vue:301](../../frontend/src/components/editor/DiscrepanciesPane.vue#L301)).

### `FlagLegend.vue`

Static three-chip legend (`flag-drift`, `flag-uncertain`, `flag-low_confidence`). No props, no logic ([../../frontend/src/components/editor/FlagLegend.vue:9](../../frontend/src/components/editor/FlagLegend.vue#L9)).

### Host: `EditorView.vue`

Mounts `DiscrepanciesPane`, passes the live arrays, and wires WS-driven `scheduleQuietRefresh` on `classification_complete`/`classification_partial`/`discrepancy_resolved`/`correction_applied` ([../../frontend/src/views/EditorView.vue:1381](../../frontend/src/views/EditorView.vue#L1381), [EditorView.vue:440](../../frontend/src/views/EditorView.vue#L440)).

## Backend Services

### `lcs_discrepancies_task` ([../../app/tasks/lcs_discrepancies.py:26](../../app/tasks/lcs_discrepancies.py#L26))

- Uses a sync SQLAlchemy engine (`DATABASE_URL` with `+asyncpg` stripped).
- Skips when both discrepancies and alignment already exist; otherwise selectively (re)builds whichever is missing (`write_diffs`, `write_alignment`) ([lcs_discrepancies.py:57](../../app/tasks/lcs_discrepancies.py#L57)).
- For each segment, pairs raw STT words (with `id`/`start_ms`/`end_ms` via `array_agg ORDER BY w.seq`) against `normalized_text` (falling back to `segments.text`) ([lcs_discrepancies.py:68](../../app/tasks/lcs_discrepancies.py#L68), [lcs_discrepancies.py:113](../../app/tasks/lcs_discrepancies.py#L113)).
- Writes one discrepancy per `diff_words` entry; writes one `word_alignment` row per `align_words` pair (UPSERT on `(segment_id, gemini_idx)`) ([lcs_discrepancies.py:118](../../app/tasks/lcs_discrepancies.py#L118), [lcs_discrepancies.py:144](../../app/tasks/lcs_discrepancies.py#L144)).
- Enqueues `classify_discrepancies_task` (non-fatal if enqueue fails) ([lcs_discrepancies.py:182](../../app/tasks/lcs_discrepancies.py#L182)).
- `max_retries=2`; terminal failure is non-fatal and returns `{error}` ([lcs_discrepancies.py:195](../../app/tasks/lcs_discrepancies.py#L195)).

### `classify_discrepancies_task` ([../../app/tasks/classify_task.py:60](../../app/tasks/classify_task.py#L60))

- Custom base `_ClassifyTask` overrides `on_failure` so a failure never transitions the session — log + WS `classification_failed` only ([classify_task.py:30](../../app/tasks/classify_task.py#L30)).
- Reads `org_settings.classify_backend` (default `gemini-dev`) and `classify_model` (default `settings.GEMINI_CLASSIFY_MODEL`); both stored as jsonb and unwrapped if quoted ([classify_task.py:90](../../app/tasks/classify_task.py#L90), [classify_task.py:101](../../app/tasks/classify_task.py#L101)).
- `use_vertex = (backend == "vertex")` ([classify_task.py:109](../../app/tasks/classify_task.py#L109)).
- Pre-flight probe of up to 3 pending items; aborts on a terminal LLM category ([classify_task.py:131](../../app/tasks/classify_task.py#L131)).
- Writes verdicts immediately (partial results are kept). Validates each verdict `id` is a UUID before UPDATE ([classify_task.py:162](../../app/tasks/classify_task.py#L162)).
- All-done → `classification_complete`; partial → `classification_partial` then `raise LLMError` to trigger retry; `max_retries=3` ([classify_task.py:207](../../app/tasks/classify_task.py#L207)).

### IIL engine

- `normalize()` runs the 3-tier rule-based normalizer; RULE 4 returns raw text on any exception; idempotent ([../../app/iil/normalization.py:93](../../app/iil/normalization.py#L93)).
- `validate_and_repair()` runs four checks and up to 2 deterministic repairs (zero LLM calls), with raw-STT fallback on terminal failure ([../../app/iil/validation.py:212](../../app/iil/validation.py#L212)).
- `extract_key_points()` produces ≤5 points (≤12 words each) from normalized text + slide bullets, gated by slide presence and segment status ([../../app/iil/key_points.py:42](../../app/iil/key_points.py#L42)).
- `update_instructor_profile()` computes rolling averages and frequency-based filler discovery (>3% of session words), non-fatal on error ([../../app/iil/adaptive_learning.py:28](../../app/iil/adaptive_learning.py#L28)).

### LLM client ([../../app/engines/llm_client.py](../../app/engines/llm_client.py))

- `classify_discrepancies(items, model_id, already_classified_ids, use_vertex)` — batches by `DISCREPANCY_BATCH_SIZE=15`, returns partial results, `None` only when every batch fails ([llm_client.py:422](../../app/engines/llm_client.py#L422), [llm_client.py:308](../../app/engines/llm_client.py#L308)).
- `_classify_batch` retries missing ids once; still-missing rows stay `NULL` for the next Celery retry ([llm_client.py:383](../../app/engines/llm_client.py#L383)).
- `_classify_batch_once` validates `is_meaningful` is a bool and coerces unknown categories to `other` ([llm_client.py:369](../../app/engines/llm_client.py#L369)).
- Dispatch: `call_gemini_text` (dev key) vs `call_vertex_ai_text` (Vertex), both `temperature=0.1`, JSON mime ([llm_client.py:217](../../app/engines/llm_client.py#L217), [llm_client.py:269](../../app/engines/llm_client.py#L269)).

### Diff engine ([../../app/engines/diff.py](../../app/engines/diff.py))

- `diff_words(stt, ai)` — DP LCS, emits `WordDiff(stt, ai, position, category)` per divergence; `_classify_heuristic` assigns a cheap pre-classify category (filler/punctuation/terminology/medication/drift/other) ([diff.py:67](../../app/engines/diff.py#L67), [diff.py:45](../../app/engines/diff.py#L45)).
- `align_words(stt, ai)` — same DP table, emits one `WordPair(ai_idx, stt_idx, match_kind)` per Gemini token (`exact`|`unmatched`); output length always equals `len(ai_words)` ([diff.py:125](../../app/engines/diff.py#L125)).

## APIs

| Method | Path | Auth | Purpose | Source |
|---|---|---|---|---|
| GET | `/v1/sessions/{session_id}/discrepancies` | JWT | List per-segment LCS diffs; query `category`, `meaningful_only` | [../../app/api/discrepancies.py:49](../../app/api/discrepancies.py#L49) |
| GET | `/v1/sessions/{session_id}/review-queue` | JWT | Alignment rows in `uncertain`/`review`, priority-ordered | [../../app/api/corrections.py:978](../../app/api/corrections.py#L978) |
| POST | `/v1/sessions/{session_id}/corrections` | JWT | Apply correction; `text_edit`/`mark_ok` auto-close a discrepancy | [../../app/api/corrections.py:332](../../app/api/corrections.py#L332) |

Routers registered in `app/main.py` (`corrections_router`, `disc_router`) ([../../app/main.py:218](../../app/main.py#L218), [main.py:220](../../app/main.py#L220)).

**`GET /discrepancies` response** (`DiscrepancyListResponse`): `session_id`, `count`, `classified_count`, `classification_status` (`complete|partial|pending`), `discrepancies[]` where each row is `{id, segment_id, ai_text, stt_text, category, is_meaningful, classifier_model, classified_at, created_at}` ([../../app/api/discrepancies.py:29](../../app/api/discrepancies.py#L29)).

**`GET /review-queue` response:** `{session_id, count, items[]}` where each item is `{segment_id, alignment_id, status, confidence, drift_flag, uncertain_flag, slide_id, priority_score}` ([../../app/api/corrections.py:1017](../../app/api/corrections.py#L1017)).

Frontend clients: `discrepancies.list` ([../../frontend/src/services/api.ts:261](../../frontend/src/services/api.ts#L261)) and `sessions.reviewQueue` ([../../frontend/src/services/api.ts:547](../../frontend/src/services/api.ts#L547)).

## Data Models

### `transcription_discrepancies` ([../../migrations/017_discrepancies_full.sql:9](../../migrations/017_discrepancies_full.sql#L9))

`id UUID PK`, `session_id UUID FK→sessions CASCADE`, `segment_id UUID FK→segments CASCADE`, `ai_text TEXT`, `stt_text TEXT`, `category TEXT`, `is_meaningful BOOLEAN` (NULL until classify), `classifier_model TEXT`, `classified_at TIMESTAMPTZ`, `created_at TIMESTAMPTZ`. Indexes: by `session_id`, and a partial index `WHERE is_meaningful IS NULL`.

> Resolution columns (`resolved`, `resolution_correction_id`, `resolved_at`) are written by the corrections endpoint ([../../app/api/corrections.py:607](../../app/api/corrections.py#L607)) but are **not** defined in 017 — they originate in a later migration. **NOT VERIFIED IN CODE:** the exact migration that adds these three columns was not read; their existence is inferred from the UPDATE that sets them.

### `alignments` + `validation_results` ([../../migrations/014_align.sql:6](../../migrations/014_align.sql#L6))

`alignments`: `confidence REAL [0..1]`, `signals`/`sources` JSONB, `drift_flag`, `anchor_hit`, `uncertain_flag`, `status CHECK IN ('assigned','uncertain','review')`, `attempt_number`, UNIQUE `(session_id, segment_id)`. `validation_results`: `verdict CHECK IN ('APPROVE','REVIEW','ESCALATE')`.

### `word_alignment` ([../../migrations/036_word_alignment.sql:23](../../migrations/036_word_alignment.sql#L23))

PK `(segment_id, gemini_idx)`, `stt_word_id UUID FK→words`, `stt_start_ms`/`stt_end_ms INTEGER`, `match_kind TEXT` (`exact`|`fuzzy`|`unmatched`).

### IIL tables

- `instructor_profiles` ([../../migrations/019_iil_learning.sql:5](../../migrations/019_iil_learning.sql#L5)) + persistent features `filler_words JSONB`, `avg_compression_ratio REAL` ([../../migrations/021_iil_features.sql:6](../../migrations/021_iil_features.sql#L6)).
- `session_instructor_map`, `session_patterns`, `key_points_annotations` ([../../migrations/019_iil_learning.sql:19](../../migrations/019_iil_learning.sql#L19)).

### Legacy (unused) ([../../migrations/002_discrepancies.sql:3](../../migrations/002_discrepancies.sql#L3))

`discrepancies` (`kind`, `severity`, `classification` JSONB, `is_resolved`) and `corrections` (`actor_email`, `kind`, `was`/`now_` JSONB). The live endpoint does not read either ([../../app/api/discrepancies.py:7](../../app/api/discrepancies.py#L7)). **IMPLEMENTATION NOT FOUND:** no live route queries these two tables.

### `NormalizedResult` (in-process model) ([../../app/iil/normalization.py:57](../../app/iil/normalization.py#L57))

`raw_text`, `normalized_text`, `filler_count`, `compression_ratio`, `tier1_removed`, `tier2_removed`, `tier2_kept`, `tier3_compressed`, `repair_applied`, `repair_attempts`, `validation_checks`.

## Events

WebSocket events (publisher: `publish_ws_event_sync`):

- `correction_applied` — on every correction (incl. undo/redo) ([../../app/api/corrections.py:624](../../app/api/corrections.py#L624)).
- `discrepancy_resolved` — when a `text_edit`/`mark_ok` closes a discrepancy ([../../app/api/corrections.py:630](../../app/api/corrections.py#L630)).
- `classification_complete` / `classification_partial` — classify progress ([../../app/tasks/classify_task.py:208](../../app/tasks/classify_task.py#L208), [classify_task.py:225](../../app/tasks/classify_task.py#L225)).
- `classification_failed` — non-fatal classify failure ([../../app/tasks/classify_task.py:46](../../app/tasks/classify_task.py#L46)).

Frontend subscriber maps all four classify/resolve events to a quiet refresh ([../../frontend/src/views/EditorView.vue:440](../../frontend/src/views/EditorView.vue#L440)).

## State Management

- **Server-authoritative.** Discrepancy state lives in `transcription_discrepancies`; the pane holds no persistent local state beyond the filter `mode` and the in-flight `resolving` set ([../../frontend/src/components/editor/DiscrepanciesPane.vue:55](../../frontend/src/components/editor/DiscrepanciesPane.vue#L55)).
- **Optimistic resolve:** the pane emits `discrepancyResolved` immediately; the WS event triggers an eventual quiet refetch to reconcile ([DiscrepanciesPane.vue:73](../../frontend/src/components/editor/DiscrepanciesPane.vue#L73); [EditorView.vue:442](../../frontend/src/views/EditorView.vue#L442)).
- **Correction ledger pointer:** undo/redo move `ledger_pointers.current_pointer`; rows are never mutated; `_next_seq` serializes writes under a `FOR UPDATE` lock on the pointer row ([../../app/api/corrections.py:153](../../app/api/corrections.py#L153)).

## Validation

- **Backend correction validation:** `correction_type` must be in `ALLOWED_CORRECTION_TYPES`; session and segment existence are checked (404 otherwise) ([../../app/api/corrections.py:345](../../app/api/corrections.py#L345)). The `CorrectionRequest` model has no `note` field — the UI's `note: 'dismissed'` is silently dropped by FastAPI ([../../app/api/corrections.py:90](../../app/api/corrections.py#L90); UI [../../frontend/src/components/editor/DiscrepanciesPane.vue:71](../../frontend/src/components/editor/DiscrepanciesPane.vue#L71)).
- **Discrepancy filters:** `category` and `meaningful_only` only ([../../app/api/discrepancies.py:54](../../app/api/discrepancies.py#L54)).
- **Verdict validation:** id-is-UUID + boolean `is_meaningful` + category coercion ([../../app/tasks/classify_task.py:166](../../app/tasks/classify_task.py#L166); [../../app/engines/llm_client.py:375](../../app/engines/llm_client.py#L375)).
- **IIL checks:** four content-based checks with deterministic repair routing ([../../app/iil/validation.py:242](../../app/iil/validation.py#L242)).

## Security

- All three endpoints require a valid JWT via `CurrentUser` ([../../app/api/discrepancies.py:53](../../app/api/discrepancies.py#L53); [../../app/api/corrections.py:333](../../app/api/corrections.py#L333), [corrections.py:979](../../app/api/corrections.py#L979)).
- `renderSTT` HTML-escapes before injecting `<mark>` and uses `v-html` only on its own escaped output, mitigating XSS from STT text ([../../frontend/src/components/editor/DiscrepanciesPane.vue:177](../../frontend/src/components/editor/DiscrepanciesPane.vue#L177)).
- LLM JSON is fence-stripped and type-checked before any DB write; classify never trusts raw model output for the row id without a UUID parse ([../../app/engines/llm_client.py:316](../../app/engines/llm_client.py#L316); [../../app/tasks/classify_task.py:166](../../app/tasks/classify_task.py#L166)).
- Corrections are append-only (no UPDATE/DELETE), giving an immutable audit trail ([../../app/api/corrections.py:9](../../app/api/corrections.py#L9)).

## Permissions

No role-based authorization in this module. Authorization = JWT presence. There is no `require_admin`, no `auth_users.role` read, and none of these routes are behind the client-side `adminOnly` guard ([../../frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)). `applied_by` is captured from `user.email` for audit, not authorization ([../../app/api/corrections.py:531](../../app/api/corrections.py#L531)).

## Integrations

- **Gemini (developer API key)** via `google-genai` SDK — default classify backend; model default `gemini-2.5-flash-lite` ([../../app/config.py:85](../../app/config.py#L85); [../../app/engines/llm_client.py:217](../../app/engines/llm_client.py#L217)).
- **Vertex AI Gemini** — opt-in (`VERTEX_AI_CLASSIFY_ENABLED=false` default; `VERTEX_AI_LOCATION=us-central1`); routed when `org_settings.classify_backend = 'vertex'` ([../../app/config.py:86](../../app/config.py#L86); [../../app/engines/llm_client.py:269](../../app/engines/llm_client.py#L269)).
- **Google STT** — provides the raw `words` rows that form the STT side of every diff (upstream of this module) ([../../app/tasks/lcs_discrepancies.py:79](../../app/tasks/lcs_discrepancies.py#L79)).

## Background Jobs

| Task | Name | Trigger | Retries | Failure posture | Source |
|---|---|---|---|---|---|
| LCS diff + word alignment | `rounds.tasks.lcs_discrepancies` | after normalize | `max_retries=2` | non-fatal; logs + returns error | [../../app/tasks/lcs_discrepancies.py:20](../../app/tasks/lcs_discrepancies.py#L20) |
| Discrepancy classification | `rounds.tasks.classify_discrepancies` | enqueued by LCS task | `max_retries=3`, 60s backoff base | non-fatal; never marks session failed | [../../app/tasks/classify_task.py:54](../../app/tasks/classify_task.py#L54) |

IIL adaptive learning (`update_instructor_profile`) runs after a session lands ready, idempotent and non-fatal ([../../app/iil/adaptive_learning.py:9](../../app/iil/adaptive_learning.py#L9)). **NOT VERIFIED IN CODE:** the exact Celery task wrapper (`learn_iil_task`, referenced in the module docstring) was not opened in this pass.

## Error Handling

- **Classify on_failure:** WS `classification_failed`, session unchanged ([../../app/tasks/classify_task.py:36](../../app/tasks/classify_task.py#L36)).
- **Terminal LLM categories** (`gemini_context_overflow`, `gemini_config`, `gemini_model_deprecated`, `validation_error`) → fail-fast, no retry burn ([../../app/engines/llm_client.py:42](../../app/engines/llm_client.py#L42)).
- **Partial classify** → `LLMError` → Celery retry on remaining `NULL` rows only ([../../app/tasks/classify_task.py:230](../../app/tasks/classify_task.py#L230)).
- **LCS terminal failure** → non-fatal `{error}` return ([../../app/tasks/lcs_discrepancies.py:199](../../app/tasks/lcs_discrepancies.py#L199)).
- **`_emit_ws`** is best-effort and never raises ([../../app/api/corrections.py:123](../../app/api/corrections.py#L123)).
- **UI:** Mark OK/Dismiss errors → toast with HTTP status; classify-failed late events → info toast ([../../frontend/src/components/editor/DiscrepanciesPane.vue:75](../../frontend/src/components/editor/DiscrepanciesPane.vue#L75); [../../frontend/src/views/EditorView.vue:453](../../frontend/src/views/EditorView.vue#L453)).
- **IIL fail-safe (RULE 4)** → raw text on any normalize exception ([../../app/iil/normalization.py:126](../../app/iil/normalization.py#L126)).

## Performance Considerations

- **Batch size 15** keeps Gemini JSON payloads under the per-response truncation threshold; missing ids retried once per batch ([../../app/engines/llm_client.py:308](../../app/engines/llm_client.py#L308), [llm_client.py:383](../../app/engines/llm_client.py#L383)).
- **Pre-flight probe** of 3 items avoids looping thousands of doomed batches against a retired model ([../../app/tasks/classify_task.py:131](../../app/tasks/classify_task.py#L131)).
- **Single DB round-trip** in the LCS task fetches STT words + ids + timestamps via `array_agg` so L2 alignment denormalizes timestamps without a second query ([../../app/tasks/lcs_discrepancies.py:68](../../app/tasks/lcs_discrepancies.py#L68)).
- **`word_alignment` denormalizes** `stt_start_ms`/`stt_end_ms` for O(1) frontend lookup (~600 KB/hour-session per the migration note) ([../../migrations/036_word_alignment.sql:18](../../migrations/036_word_alignment.sql#L18)).
- **`renderSTT`** merges overlapping highlight ranges and walks the text once to bound per-segment cost ([../../frontend/src/components/editor/DiscrepanciesPane.vue:162](../../frontend/src/components/editor/DiscrepanciesPane.vue#L162)).
- **Partial-index** `WHERE is_meaningful IS NULL` makes the classify "remaining rows" sweep cheap ([../../migrations/017_discrepancies_full.sql:23](../../migrations/017_discrepancies_full.sql#L23)).
- **Idempotent re-runs:** classify skips already-classified ids; LCS task skips when both products already exist ([../../app/tasks/classify_task.py:113](../../app/tasks/classify_task.py#L113); [../../app/tasks/lcs_discrepancies.py:57](../../app/tasks/lcs_discrepancies.py#L57)).

## Source Verification
- **Files Used:** app/api/discrepancies.py, app/api/corrections.py, app/tasks/classify_task.py, app/tasks/lcs_discrepancies.py, app/engines/llm_client.py, app/engines/diff.py, app/iil/validation.py, app/iil/normalization.py, app/iil/adaptive_learning.py, app/iil/key_points.py, app/prompts.py, app/config.py, app/main.py, migrations/002_discrepancies.sql, migrations/014_align.sql, migrations/017_discrepancies_full.sql, migrations/019_iil_learning.sql, migrations/021_iil_features.sql, migrations/036_word_alignment.sql, frontend/src/components/editor/DiscrepanciesPane.vue, frontend/src/components/editor/FlagLegend.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** DiscrepanciesPane.vue, FlagLegend.vue, EditorView.vue
- **APIs Used:** GET /v1/sessions/{id}/discrepancies, GET /v1/sessions/{id}/review-queue, POST /v1/sessions/{id}/corrections
- **Database Tables Used:** transcription_discrepancies, alignments, validation_results, word_alignment, correction_ledger, ledger_pointers, segments, words, normalization_results, org_settings, instructor_profiles, session_instructor_map, session_patterns, key_points_annotations; legacy discrepancies + corrections (002, unused)
- **Permission Logic Used:** JWT (CurrentUser) only; no role enforcement on any route in this module
- **Confidence Score:** High — endpoints, tasks, engines, and migrations read in full. Two items tagged NOT VERIFIED IN CODE (resolution-columns migration; learn_iil_task wrapper).
- **Evidence Links:** [app/tasks/lcs_discrepancies.py:26](../../app/tasks/lcs_discrepancies.py#L26), [app/tasks/classify_task.py:60](../../app/tasks/classify_task.py#L60), [app/engines/llm_client.py:422](../../app/engines/llm_client.py#L422), [app/api/corrections.py:1005](../../app/api/corrections.py#L1005), [migrations/017_discrepancies_full.sql:9](../../migrations/017_discrepancies_full.sql#L9)
