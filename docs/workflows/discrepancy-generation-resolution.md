# Workflow: Discrepancy Generation & Resolution

How per-segment differences between the raw STT transcript and the AI-normalized text are detected, AI-classified as meaningful vs. noise, surfaced to the editor, and auto-closed when an operator edits or explicitly accepts the segment.

Three code units:
- **Generation** — [`app/tasks/lcs_discrepancies.py`](../../app/tasks/lcs_discrepancies.py) (LCS diff → `transcription_discrepancies` rows) and [`app/tasks/classify_task.py`](../../app/tasks/classify_task.py) (Gemini classification → `is_meaningful` + `category`).
- **Read** — [`app/api/discrepancies.py`](../../app/api/discrepancies.py) (`GET /v1/sessions/{id}/discrepancies`).
- **Resolution** — [`app/api/corrections.py`](../../app/api/corrections.py), the `CLOSES_DISCREPANCY_TYPES` auto-close on `text_edit` / `mark_ok`.

Table: [`migrations/017_discrepancies_full.sql`](../../migrations/017_discrepancies_full.sql); resolution columns added by [`migrations/029_corrections.sql`](../../migrations/029_corrections.sql).

## Trigger

- **Generation** — `lcs_discrepancies_task` is a Celery task (`name="rounds.tasks.lcs_discrepancies"`) that runs after `normalize_task` ([lcs_discrepancies.py:6-8](../../app/tasks/lcs_discrepancies.py#L6), [lcs_discrepancies.py:20-26](../../app/tasks/lcs_discrepancies.py#L20)). It can also be re-fired manually via the operator endpoint `POST /v1/diag/realign/{session_id}` (per CLAUDE.md). NOT VERIFIED IN CODE here: the exact pipeline call site that first enqueues it (lives outside the three assigned files).
- **Classification** — `lcs_discrepancies_task` enqueues `classify_discrepancies_task` (`queue="celery"`) on success, best-effort ([lcs_discrepancies.py:182-187](../../app/tasks/lcs_discrepancies.py#L182)).
- **Resolution** — an operator applies a correction via `POST /v1/sessions/{id}/corrections` with `correction_type` `text_edit` or `mark_ok` ([corrections.py:332](../../app/api/corrections.py#L332), [corrections.py:602](../../app/api/corrections.py#L602)).
- **Read** — the editor calls `GET /v1/sessions/{id}/discrepancies` ([discrepancies.py:49](../../app/api/discrepancies.py#L49)).

## Inputs

- **Generation** — `session_id` (str). The task SELECTs, per segment, the raw STT word vectors (`words.word/id/start_ms/end_ms` ordered by `seq`) and the normalized text (`normalization_results.normalized_text`), falling back to `segments.text` when no normalization row exists ([lcs_discrepancies.py:68-86](../../app/tasks/lcs_discrepancies.py#L68), [lcs_discrepancies.py:113](../../app/tasks/lcs_discrepancies.py#L113)). Diffing uses `app.engines.diff.diff_words` / `align_words` ([lcs_discrepancies.py:30](../../app/tasks/lcs_discrepancies.py#L30)).
- **Classification** — `session_id` (str). Reads pending `transcription_discrepancies` rows plus backend/model from `org_settings` keys `classify_backend` (default `gemini-dev`) and `classify_model` (default `settings.GEMINI_CLASSIFY_MODEL`) ([classify_task.py:79-108](../../app/tasks/classify_task.py#L79)).
- **Resolution** — `CorrectionRequest` body: `segment_id`, `correction_type`, plus `old_text`/`new_text` for `text_edit` ([corrections.py:90-112](../../app/api/corrections.py#L90)).
- **Read** — optional query filters `category` and `meaningful_only` ([discrepancies.py:54-55](../../app/api/discrepancies.py#L54)).

## Validations

- **Generation skip guard** — if discrepancies AND word-alignment both already exist for the session, the task returns `{skipped: True}` ([lcs_discrepancies.py:57-59](../../app/tasks/lcs_discrepancies.py#L57)). Otherwise it sets `write_diffs = (no existing discrepancies)` and `write_alignment = (no existing alignment)` independently, so a session that has diffs but no alignment still gets its `word_alignment` rebuilt ([lcs_discrepancies.py:61-62](../../app/tasks/lcs_discrepancies.py#L61)).
- A `[None]` `array_agg` from a missing LEFT JOIN is flattened to empty; segments with neither STT nor AI tokens are skipped ([lcs_discrepancies.py:96-116](../../app/tasks/lcs_discrepancies.py#L96)).
- `word_alignment` inserts are idempotent via `ON CONFLICT (segment_id, gemini_idx) DO UPDATE` ([lcs_discrepancies.py:158-162](../../app/tasks/lcs_discrepancies.py#L158)).
- **Classification idempotency** — rows whose `is_meaningful` is already set are passed to the engine as `already_classified_ids` and skipped ([classify_task.py:113-120](../../app/tasks/classify_task.py#L113)). A pre-flight single-batch probe aborts the whole task if the model is in a terminal state (e.g. retired model), avoiding thousands of doomed batches ([classify_task.py:127-144](../../app/tasks/classify_task.py#L127)). Verdict ids are UUID-validated before write; malformed ones are skipped ([classify_task.py:164-171](../../app/tasks/classify_task.py#L164)).
- **Resolution** — `apply_correction` validates `correction_type` ∈ `ALLOWED_CORRECTION_TYPES`, that the session exists, and that the segment belongs to the session ([corrections.py:345-353](../../app/api/corrections.py#L345)). The auto-close UPDATE only touches rows where `COALESCE(resolved, FALSE) = FALSE` ([corrections.py:602-618](../../app/api/corrections.py#L602)).
- **Read status label** — `complete` when count is 0 or all rows classified, `partial` when some classified, `pending` when none ([discrepancies.py:94-103](../../app/api/discrepancies.py#L94)).

## Approvals

**None.** No human approval gate exists in any of the three units. Classification is a fully automated AI step; resolution is a single operator action with no second-party sign-off.

## Notifications

- **WebSocket only** (no email). On classification:
  - `classification_complete` `{classified, meaningful, noise}` when all rows are done ([classify_task.py:207-213](../../app/tasks/classify_task.py#L207)).
  - `classification_partial` `{classified, total}` before a retry ([classify_task.py:225-229](../../app/tasks/classify_task.py#L225)).
  - `classification_failed` `{reason}` from the task's `on_failure` override ([classify_task.py:36-51](../../app/tasks/classify_task.py#L36)).
- On resolution: the corrections endpoint emits `correction_applied`, and — when a discrepancy was closed — an additional `discrepancy_resolved` `{discrepancy_id}` WS event ([corrections.py:624-634](../../app/api/corrections.py#L624)).

## Outputs

- **Generation** — rows in `transcription_discrepancies` (`session_id, segment_id, ai_text, stt_text, category`) and `word_alignment` (`segment_id, gemini_idx, stt_word_id, stt_start_ms, stt_end_ms, match_kind`) ([lcs_discrepancies.py:121-173](../../app/tasks/lcs_discrepancies.py#L121)). Returns `{session_id, diffs, alignments}` ([lcs_discrepancies.py:189-193](../../app/tasks/lcs_discrepancies.py#L189)).
- **Classification** — UPDATEs `category, is_meaningful, classifier_model, classified_at` on each row ([classify_task.py:172-189](../../app/tasks/classify_task.py#L172)). Returns `{classified, meaningful, noise, backend, model}` ([classify_task.py:214-221](../../app/tasks/classify_task.py#L214)).
- **Read** — `DiscrepancyListResponse` `{session_id, count, classified_count, classification_status, discrepancies[]}`; each row carries `ai_text`, `stt_text`, `category`, `is_meaningful`, `classifier_model`, timestamps ([discrepancies.py:29-46](../../app/api/discrepancies.py#L29), [discrepancies.py:105-111](../../app/api/discrepancies.py#L105)).
- **Resolution** — UPDATEs the matched discrepancy to `resolved=TRUE, resolution_correction_id=<correction>, resolved_at=now()` and returns `resolved_discrepancy_id` in the correction response ([corrections.py:607-620](../../app/api/corrections.py#L607), [corrections.py:648](../../app/api/corrections.py#L648)). Columns are from [migrations/029_corrections.sql:144-149](../../migrations/029_corrections.sql#L144).

### Auto-close rule (BR-018)

`CLOSES_DISCREPANCY_TYPES = frozenset({"text_edit", "mark_ok"})` ([corrections.py:63](../../app/api/corrections.py#L63)). Only these two correction types auto-close a segment's open discrepancy: `text_edit` (editing the text at the discrepancy site) and `mark_ok` (explicit "no change needed"). Other types — `find_replace`, `chat_edit`, `speaker_reassignment`, `split`, `merge`, slide/poll — deliberately do NOT close discrepancies ([corrections.py:55-63](../../app/api/corrections.py#L55)). The full allowed set is `slide_reassignment, text_edit, split, merge, mark_ok, chat_insert, chat_edit, chat_remove, poll_insert, poll_remove, speaker_reassignment` ([corrections.py:49-53](../../app/api/corrections.py#L49)).

## Status Changes

- **Discrepancy row state:** unclassified (`is_meaningful = NULL`) → classified (`is_meaningful` true/false, `category` set) → resolved (`resolved = TRUE`).
- **Session status:** **none of these tasks change session status.** Generation is "an editor convenience, not a gate" ([lcs_discrepancies.py:199](../../app/tasks/lcs_discrepancies.py#L199)); classification "must NEVER mark the session as 'failed'" and runs after the session is already `ready` ([classify_task.py:1-4](../../app/tasks/classify_task.py#L1), [classify_task.py:30-34](../../app/tasks/classify_task.py#L30)).

## Audit Events

- **None written by these three units.** Neither `lcs_discrepancies_task`, `classify_discrepancies_task`, nor the discrepancy auto-close path inserts an `audit_events` row. The corrections endpoint's record of the change is the append-only `correction_ledger` row plus the `resolution_correction_id` back-reference on the discrepancy ([corrections.py:533-561](../../app/api/corrections.py#L533)). NOT VERIFIED IN CODE: any audit row for discrepancy lifecycle.

## Exception Handling

- **Generation** — wrapped in try/except. On error, retries up to `max_retries=2` via `retry_with_backoff`; after exhaustion it logs and returns `{session_id, error}` WITHOUT raising (non-fatal — discrepancies don't gate readiness) ([lcs_discrepancies.py:195-203](../../app/tasks/lcs_discrepancies.py#L195)). The classify enqueue is itself wrapped so a broker hiccup doesn't fail generation ([lcs_discrepancies.py:182-187](../../app/tasks/lcs_discrepancies.py#L182)).
- **Classification** — `max_retries=3` with 60/120/240s backoff. Partial results are written immediately, then `LLMError` is raised to retry only the remaining rows ([classify_task.py:158-233](../../app/tasks/classify_task.py#L158)). `on_failure` logs + emits `classification_failed` but never transitions the session ([classify_task.py:36-51](../../app/tasks/classify_task.py#L36)). A terminal model fault aborts cleanly with `{aborted: True, reason}` ([classify_task.py:138-144](../../app/tasks/classify_task.py#L138)).
- **Resolution** — standard FastAPI `HTTPException` 400/404 on invalid type / missing session / mismatched segment ([corrections.py:345-353](../../app/api/corrections.py#L345)). The discrepancy UPDATE is part of the same transaction as the ledger append and commits together ([corrections.py:601-622](../../app/api/corrections.py#L601)).

### Feature flags

- These three workflows are **not** behind a feature flag. (The adjacent `split`/`merge` correction types are gated by `SPLIT_MERGE_ENABLED` and return 503 when off — [corrections.py:360-363](../../app/api/corrections.py#L360) — but `split`/`merge` are NOT in `CLOSES_DISCREPANCY_TYPES`, so that flag does not affect discrepancy resolution.)

## Source Verification
- **Files Used:** app/tasks/lcs_discrepancies.py, app/tasks/classify_task.py, app/api/discrepancies.py, app/api/corrections.py, migrations/017_discrepancies_full.sql, migrations/029_corrections.sql
- **Components Used:** none
- **APIs Used:** GET /v1/sessions/{id}/discrepancies, POST /v1/sessions/{id}/corrections (text_edit / mark_ok auto-close); Celery tasks rounds.tasks.lcs_discrepancies, rounds.tasks.classify_discrepancies
- **Database Tables Used:** transcription_discrepancies, word_alignment, segments, words, normalization_results, org_settings, correction_ledger
- **Permission Logic Used:** Read + corrections require JWT (`CurrentUser`); no admin gate on this surface. Tasks run as Celery workers (no per-user auth).
- **Confidence Score:** High — generation, classification, read, and resolution all traced to source; only the upstream enqueue site is outside scope.
- **Evidence Links:** [corrections.py:63](../../app/api/corrections.py#L63), [corrections.py:601-634](../../app/api/corrections.py#L601), [lcs_discrepancies.py:57-62](../../app/tasks/lcs_discrepancies.py#L57), [classify_task.py:207-233](../../app/tasks/classify_task.py#L207), [discrepancies.py:94-111](../../app/api/discrepancies.py#L94)
