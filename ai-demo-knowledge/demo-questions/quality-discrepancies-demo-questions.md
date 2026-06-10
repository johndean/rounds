# Quality & AI Accuracy — Demo Questions

> Module key: `quality-discrepancies`. Every answer below is verified against current code. Paths are relative to this file (`ai-demo-knowledge/demo-questions/`).

---

## User

### Q: How do I see where the AI might have gotten the transcript wrong?
- **Verified Answer:** Open a session in the Editor and switch to the Discrepancies tab. It shows the AI transcript on the left and the raw speech-to-text on the right, with the diverging words highlighted in both columns. By default it shows only "Flagged" segments.
- **Supporting Evidence:** The pane renders an AI/STT split with per-segment diff highlighting and defaults the filter to `flagged` ([../../frontend/src/components/editor/DiscrepanciesPane.vue:83](../../frontend/src/components/editor/DiscrepanciesPane.vue#L83), [DiscrepanciesPane.vue:275](../../frontend/src/components/editor/DiscrepanciesPane.vue#L275)).
- **Source Files:** frontend/src/components/editor/DiscrepanciesPane.vue
- **API References:** GET /v1/sessions/{id}/discrepancies
- **Database References:** transcription_discrepancies

### Q: What do the three filter buttons (All / Flagged / Meaningful) do?
- **Verified Answer:** "All" shows every segment, "Flagged" shows segments with at least one detected diff, and "Meaningful" shows only segments where the AI classifier judged at least one diff as a substantive mistranscription.
- **Supporting Evidence:** `visibleSegments` filters on `mode`; meaningful set keeps segments with `is_meaningful === true` ([../../frontend/src/components/editor/DiscrepanciesPane.vue:140](../../frontend/src/components/editor/DiscrepanciesPane.vue#L140), [DiscrepanciesPane.vue:127](../../frontend/src/components/editor/DiscrepanciesPane.vue#L127)).
- **Source Files:** frontend/src/components/editor/DiscrepanciesPane.vue
- **API References:** GET /v1/sessions/{id}/discrepancies
- **Database References:** transcription_discrepancies (is_meaningful)

### Q: What happens when I click "Mark OK" or "Dismiss"?
- **Verified Answer:** Both record a `mark_ok` correction against that segment, which closes the discrepancy. The row disappears from the list and a success toast appears.
- **Supporting Evidence:** `onMarkOk` POSTs `mark_ok`; the backend marks the matching discrepancy resolved because `mark_ok ∈ CLOSES_DISCREPANCY_TYPES` ([../../frontend/src/components/editor/DiscrepanciesPane.vue:62](../../frontend/src/components/editor/DiscrepanciesPane.vue#L62); [../../app/api/corrections.py:63](../../app/api/corrections.py#L63), [corrections.py:602](../../app/api/corrections.py#L602)).
- **Source Files:** frontend/src/components/editor/DiscrepanciesPane.vue, app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections
- **Database References:** transcription_discrepancies (resolved), correction_ledger

### Q: If I just fix the text, do I still need to clear the flag separately?
- **Verified Answer:** No. A text edit on the flagged segment auto-closes the discrepancy in the same action — `text_edit` is one of the two auto-closing correction types.
- **Supporting Evidence:** `CLOSES_DISCREPANCY_TYPES = {"text_edit", "mark_ok"}` and the resolve UPDATE runs for those types ([../../app/api/corrections.py:63](../../app/api/corrections.py#L63), [corrections.py:602](../../app/api/corrections.py#L602)).
- **Source Files:** app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections
- **Database References:** transcription_discrepancies, correction_ledger

### Q: Do I have to clear every single flag?
- **Verified Answer:** No. The list is filterable and the count distinguishes "flagged for review" from total raw diffs, so you can focus on the meaningful ones and leave noise alone.
- **Supporting Evidence:** Toolbar shows `<meaningfulCount> flagged for review · <totalDiffs> raw diffs` ([../../frontend/src/components/editor/DiscrepanciesPane.vue:252](../../frontend/src/components/editor/DiscrepanciesPane.vue#L252)).
- **Source Files:** frontend/src/components/editor/DiscrepanciesPane.vue
- **API References:** GET /v1/sessions/{id}/discrepancies
- **Database References:** transcription_discrepancies

---

## Executive

### Q: What does this module actually guarantee about transcript quality?
- **Verified Answer:** It guarantees a clinical-safety floor: if the AI normalization drops a content word or domain term and can't repair it in two deterministic attempts, the segment ships the raw transcript verbatim rather than a silently-broken sentence. It does not guarantee perfect accuracy — it surfaces likely errors for a human.
- **Supporting Evidence:** RULE 4 raw-text fallback after `MAX_REPAIR_ATTEMPTS = 2` ([../../app/iil/validation.py:61](../../app/iil/validation.py#L61), [validation.py:286](../../app/iil/validation.py#L286)).
- **Source Files:** app/iil/validation.py
- **API References:** none
- **Database References:** normalization_results (validation_results blob)

### Q: How does the AI decide what's worth a reviewer's time versus noise?
- **Verified Answer:** Each word-level diff is classified by Gemini into meaningful categories (medication, number, name, date, terminology, other) or noise categories (filler, punctuation, style). The prompt instructs the model to lean meaningful when unsure between style and terminology.
- **Supporting Evidence:** Classification prompt taxonomy and the "lean MEANINGFUL" rule ([../../app/prompts.py:29](../../app/prompts.py#L29)).
- **Source Files:** app/prompts.py, app/engines/llm_client.py
- **API References:** none (background classify)
- **Database References:** transcription_discrepancies (category, is_meaningful)

### Q: Is the system biased toward over-flagging or under-flagging?
- **Verified Answer:** Toward over-flagging. The classification prompt explicitly says "better to over-flag than miss a mistranscription," and any medication/number/name/date/clinical term is meaningful "even if small."
- **Supporting Evidence:** Prompt rules 4 and 5 ([../../app/prompts.py:46](../../app/prompts.py#L46)).
- **Source Files:** app/prompts.py
- **API References:** none
- **Database References:** transcription_discrepancies

### Q: Can a transcript fail to publish because the AI accuracy step broke?
- **Verified Answer:** No. The classification step is explicitly non-critical — a failure logs and emits an event but never marks the session failed; the LCS diff step is also non-fatal ("an editor convenience, not a gate").
- **Supporting Evidence:** `_ClassifyTask.on_failure` doesn't change session status; LCS terminal failure returns non-fatally ([../../app/tasks/classify_task.py:30](../../app/tasks/classify_task.py#L30); [../../app/tasks/lcs_discrepancies.py:199](../../app/tasks/lcs_discrepancies.py#L199)).
- **Source Files:** app/tasks/classify_task.py, app/tasks/lcs_discrepancies.py
- **API References:** none
- **Database References:** transcription_discrepancies

---

## Operations

### Q: What's the pipeline that produces the discrepancies?
- **Verified Answer:** `normalize_task` → `lcs_discrepancies_task` (LCS-diffs STT vs normalized text, writes one discrepancy per word divergence and populates word_alignment) → `classify_discrepancies_task` (Gemini labels each as meaningful/noise).
- **Supporting Evidence:** LCS task inserts diffs and enqueues classify ([../../app/tasks/lcs_discrepancies.py:118](../../app/tasks/lcs_discrepancies.py#L118), [lcs_discrepancies.py:182](../../app/tasks/lcs_discrepancies.py#L182)).
- **Source Files:** app/tasks/lcs_discrepancies.py, app/tasks/classify_task.py
- **API References:** none
- **Database References:** transcription_discrepancies, word_alignment, segments, words, normalization_results

### Q: A session shows discrepancies but none are classified. How do I re-run classification?
- **Verified Answer:** Re-run the alignment/discrepancy task via the operator endpoint `POST /v1/diag/realign/<SESSION_ID>` (re-triggers `lcs_discrepancies_task`, which re-enqueues classify). Classification is idempotent — already-classified rows are skipped, only `is_meaningful IS NULL` rows are re-picked.
- **Supporting Evidence:** Classify separates already-done ids and skips them; partial runs retry only remaining rows ([../../app/tasks/classify_task.py:113](../../app/tasks/classify_task.py#L113), [classify_task.py:230](../../app/tasks/classify_task.py#L230)). Diag realign route documented in CLAUDE.md. **(The `/v1/diag/realign` route's exact handler was not opened in this pass — the re-run behavior is verified from the classify task's idempotency.)**
- **Source Files:** app/tasks/classify_task.py
- **API References:** POST /v1/diag/realign/{session_id} (operator), GET /v1/sessions/{id}/discrepancies
- **Database References:** transcription_discrepancies (partial index on is_meaningful IS NULL)

### Q: Classification keeps failing for a session — what does the system do?
- **Verified Answer:** It retries (max 3, with backoff) on partial/transient failures, but if the very first probe batch hits a terminal category (e.g. the configured model was deprecated, a config/auth error, or context overflow) it aborts the whole run rather than burning the retry budget across thousands of batches.
- **Supporting Evidence:** Pre-flight probe + terminal-category abort; `max_retries=3` ([../../app/tasks/classify_task.py:131](../../app/tasks/classify_task.py#L131), [classify_task.py:54](../../app/tasks/classify_task.py#L54); terminal set [../../app/engines/llm_client.py:42](../../app/engines/llm_client.py#L42)).
- **Source Files:** app/tasks/classify_task.py, app/engines/llm_client.py
- **API References:** none
- **Database References:** org_settings (classify_model)

### Q: How is the classification engine chosen (Gemini vs Vertex)?
- **Verified Answer:** It reads `org_settings.classify_backend` (default `gemini-dev`) and `org_settings.classify_model` (default `gemini-2.5-flash-lite`). Vertex AI is used only when `classify_backend = 'vertex'`; the env flag `VERTEX_AI_CLASSIFY_ENABLED` defaults to false.
- **Supporting Evidence:** Backend/model read + `use_vertex` switch ([../../app/tasks/classify_task.py:90](../../app/tasks/classify_task.py#L90), [classify_task.py:109](../../app/tasks/classify_task.py#L109)); defaults ([../../app/config.py:85](../../app/config.py#L85)).
- **Source Files:** app/tasks/classify_task.py, app/config.py
- **API References:** GET /v1/diag/classify-route (operator probe, per CLAUDE.md)
- **Database References:** org_settings

### Q: What's the batch size, and why does classification sometimes leave a few items unclassified?
- **Verified Answer:** 15 items per Gemini call. If Gemini truncates and returns fewer items, the batch retries the missing ids once; anything still missing stays `is_meaningful IS NULL` and is re-picked on the next Celery retry.
- **Supporting Evidence:** `DISCREPANCY_BATCH_SIZE = 15`; per-batch missing-id retry ([../../app/engines/llm_client.py:308](../../app/engines/llm_client.py#L308), [llm_client.py:383](../../app/engines/llm_client.py#L383)).
- **Source Files:** app/engines/llm_client.py
- **API References:** none
- **Database References:** transcription_discrepancies

---

## Compliance

### Q: Is there an audit trail of who resolved each flagged discrepancy?
- **Verified Answer:** Yes, two-fold. Every resolution writes an append-only `correction_ledger` row with `applied_by` (the user's email), `action_id`, and `sequence_number`; the discrepancy itself records `resolution_correction_id` and `resolved_at` as a back-reference.
- **Supporting Evidence:** Ledger insert with `applied_by` and the discrepancy resolve UPDATE ([../../app/api/corrections.py:531](../../app/api/corrections.py#L531), [corrections.py:607](../../app/api/corrections.py#L607)).
- **Source Files:** app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections, GET /v1/sessions/{id}/corrections
- **Database References:** correction_ledger, transcription_discrepancies

### Q: Can resolution history be altered or deleted after the fact?
- **Verified Answer:** No. The corrections ledger is append-only by design — UPDATE/DELETE is forbidden; undo/redo only move a pointer, the rows are never mutated.
- **Supporting Evidence:** Append-only invariant documented and enforced by pointer-based undo/redo ([../../app/api/corrections.py:9](../../app/api/corrections.py#L9)).
- **Source Files:** app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections/undo, /redo
- **Database References:** correction_ledger, ledger_pointers

### Q: Do you record which model classified each discrepancy?
- **Verified Answer:** Yes. Each classified row stores `classifier_model` and `classified_at`.
- **Supporting Evidence:** Classify UPDATE sets both columns ([../../app/tasks/classify_task.py:172](../../app/tasks/classify_task.py#L172); column defs [../../migrations/017_discrepancies_full.sql:17](../../migrations/017_discrepancies_full.sql#L17)).
- **Source Files:** app/tasks/classify_task.py, migrations/017_discrepancies_full.sql
- **API References:** GET /v1/sessions/{id}/discrepancies (returns classifier_model, classified_at)
- **Database References:** transcription_discrepancies

### Q: How do you ensure a critical term (like a drug name) is never silently dropped?
- **Verified Answer:** The IIL validation loop checks content words and domain terms are preserved; on failure it restores missing words from the immutable source `words[]`. If repair still fails after two attempts, the segment falls back to raw STT verbatim — the documented clinical-safety invariant.
- **Supporting Evidence:** check1/check2 + `_repair_restore_words` + raw fallback ([../../app/iil/validation.py:104](../../app/iil/validation.py#L104), [validation.py:173](../../app/iil/validation.py#L173), [validation.py:286](../../app/iil/validation.py#L286)).
- **Source Files:** app/iil/validation.py, app/iil/normalization.py
- **API References:** none
- **Database References:** normalization_results

---

## Administrator

### Q: Who is allowed to view and resolve discrepancies?
- **Verified Answer:** Any authenticated user. The discrepancies, review-queue, and corrections endpoints require only a valid JWT — there is no role check on any of them. There is no per-role restriction for this module.
- **Supporting Evidence:** All three endpoints use `CurrentUser` (JWT) with no role gate ([../../app/api/discrepancies.py:53](../../app/api/discrepancies.py#L53); [../../app/api/corrections.py:333](../../app/api/corrections.py#L333), [corrections.py:979](../../app/api/corrections.py#L979)).
- **Source Files:** app/api/discrepancies.py, app/api/corrections.py
- **API References:** GET /v1/sessions/{id}/discrepancies, /review-queue; POST /v1/sessions/{id}/corrections
- **Database References:** none (auth via JWT)

### Q: Are any Quality/AI features admin-only?
- **Verified Answer:** No. The only admin gate in the product is a hardcoded `email == 'johndean@vin.com'` check plus one client-side route guard (`adminOnly`). None of the Quality/AI routes or views are behind that guard.
- **Supporting Evidence:** The client-side guard `to.meta.adminOnly && auth.email !== LEGACY_ADMIN_EMAIL` is not applied to discrepancies/review-queue ([../../frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63), [index.ts:51](../../frontend/src/router/index.ts#L51)).
- **Source Files:** frontend/src/router/index.ts
- **API References:** none
- **Database References:** none

### Q: How do I switch the classifier to Vertex AI?
- **Verified Answer:** Set `org_settings.classify_backend = 'vertex'` (and optionally `classify_model`). The task reads these on each run; `use_vertex` becomes true and routes through `call_vertex_ai_text` using `GCP_PROJECT_ID` and `VERTEX_AI_LOCATION` (default `us-central1`).
- **Supporting Evidence:** Backend read + Vertex client construction ([../../app/tasks/classify_task.py:90](../../app/tasks/classify_task.py#L90); [../../app/engines/llm_client.py:269](../../app/engines/llm_client.py#L269); config [../../app/config.py:86](../../app/config.py#L86)).
- **Source Files:** app/tasks/classify_task.py, app/engines/llm_client.py, app/config.py
- **API References:** GET /v1/diag/classify-route (operator)
- **Database References:** org_settings

### Q: The Dismiss button says it sends a note — is that note stored?
- **Verified Answer:** No. The UI adds `note: 'dismissed'` to the request, but the backend's `CorrectionRequest` model has no `note` field, so FastAPI ignores it. "Mark OK" and "Dismiss" are stored identically as `mark_ok` corrections.
- **Supporting Evidence:** UI sends `note` ([../../frontend/src/components/editor/DiscrepanciesPane.vue:71](../../frontend/src/components/editor/DiscrepanciesPane.vue#L71)); model has no `note` field ([../../app/api/corrections.py:90](../../app/api/corrections.py#L90)).
- **Source Files:** frontend/src/components/editor/DiscrepanciesPane.vue, app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections
- **Database References:** correction_ledger

---

## Power User

### Q: How does the review queue decide what's most urgent?
- **Verified Answer:** It scores each `uncertain`/`review` alignment row additively: drift + no slide = +100; uncertain + no slide = +90; confidence < 0.4 = +70; drift = +50; status `review` = +40; confidence < 0.6 = +20. Bonuses stack (a sub-0.4 row gets both confidence bonuses), then rows are sorted descending.
- **Supporting Evidence:** `priority()` function (BR-006) ([../../app/api/corrections.py:1005](../../app/api/corrections.py#L1005)).
- **Source Files:** app/api/corrections.py
- **API References:** GET /v1/sessions/{id}/review-queue
- **Database References:** alignments

### Q: What's the difference between the "Discrepancies" tab and the review queue?
- **Verified Answer:** Different signals, different tables. Discrepancies are per-word AI-vs-STT text diffs in `transcription_discrepancies`, shown in the editor pane. The review queue is segment-to-slide alignment uncertainty in `alignments`, served by a separate endpoint. The review-queue endpoint currently has no consuming UI.
- **Supporting Evidence:** Discrepancy endpoint reads `transcription_discrepancies` ([../../app/api/discrepancies.py:72](../../app/api/discrepancies.py#L72)); review-queue reads `alignments` ([../../app/api/corrections.py:986](../../app/api/corrections.py#L986)); no `reviewQueue` call exists in EditorView (verified by grep).
- **Source Files:** app/api/discrepancies.py, app/api/corrections.py, frontend/src/views/EditorView.vue
- **API References:** GET /v1/sessions/{id}/discrepancies, GET /v1/sessions/{id}/review-queue
- **Database References:** transcription_discrepancies, alignments

### Q: How are diffs categorized before Gemini even runs?
- **Verified Answer:** The LCS diff engine assigns a cheap heuristic category at insert time: pure inserts/deletes of filler words → `filler`; punctuation tokens → `punctuation`; capitalized tokens → `terminology`; tokens with digits → `medication`; otherwise `drift`/`other`. Gemini then refines `is_meaningful` and re-labels `category`.
- **Supporting Evidence:** `_classify_heuristic` ([../../app/engines/diff.py:45](../../app/engines/diff.py#L45)); classify overwrites category ([../../app/tasks/classify_task.py:176](../../app/tasks/classify_task.py#L176)).
- **Source Files:** app/engines/diff.py, app/tasks/classify_task.py
- **API References:** none
- **Database References:** transcription_discrepancies (category)

### Q: How does the STT-column word highlighting line up with audio timing?
- **Verified Answer:** `lcs_discrepancies_task` also builds a `word_alignment` row per Gemini word, pairing it (when matched) to the exact STT word's start/end ms. The frontend uses these denormalized timestamps for per-word highlight; unmatched Gemini words get nulls and are skipped.
- **Supporting Evidence:** `align_words` + `word_alignment` UPSERT ([../../app/engines/diff.py:125](../../app/engines/diff.py#L125); [../../app/tasks/lcs_discrepancies.py:144](../../app/tasks/lcs_discrepancies.py#L144)); table ([../../migrations/036_word_alignment.sql:23](../../migrations/036_word_alignment.sql#L23)).
- **Source Files:** app/engines/diff.py, app/tasks/lcs_discrepancies.py, migrations/036_word_alignment.sql
- **API References:** GET /v1/sessions/{id}/words, word-alignment endpoint
- **Database References:** word_alignment, words

### Q: Do my edits retrain the AI?
- **Verified Answer:** No. Editor corrections are captured for the audit trail and discrepancy resolution, but they do not feed back into the transcription engine. IIL adaptive learning updates *instructor profiles* (rolling filler rate, compression ratio, discovered filler words from a >3% frequency rule) from normalization stats — not from your corrections.
- **Supporting Evidence:** Adaptive learning works on `session_patterns`/`normalization_stats`, with a 3% discovery threshold; no correction input ([../../app/iil/adaptive_learning.py:28](../../app/iil/adaptive_learning.py#L28), [adaptive_learning.py:63](../../app/iil/adaptive_learning.py#L63)).
- **Source Files:** app/iil/adaptive_learning.py
- **API References:** none
- **Database References:** instructor_profiles, session_patterns

### Q: Why do some segments show the raw STT as the AI text?
- **Verified Answer:** When IIL normalization can't safely repair a segment within two attempts, it deliberately ships raw STT as the normalized text (clinical-safety fallback). The LCS task also falls back to `segments.text` when there's no `normalization_results` row (direct Gemini pipeline).
- **Supporting Evidence:** RULE 4 fallback ([../../app/iil/validation.py:286](../../app/iil/validation.py#L286)); AI-side fallback to `segments.text` ([../../app/tasks/lcs_discrepancies.py:113](../../app/tasks/lcs_discrepancies.py#L113)).
- **Source Files:** app/iil/validation.py, app/tasks/lcs_discrepancies.py
- **API References:** none
- **Database References:** normalization_results, segments

---

## Source Verification
- **Files Used:** app/api/discrepancies.py, app/api/corrections.py, app/tasks/classify_task.py, app/tasks/lcs_discrepancies.py, app/engines/llm_client.py, app/engines/diff.py, app/iil/validation.py, app/iil/normalization.py, app/iil/adaptive_learning.py, app/iil/key_points.py, app/prompts.py, app/config.py, migrations/017_discrepancies_full.sql, migrations/014_align.sql, migrations/036_word_alignment.sql, frontend/src/components/editor/DiscrepanciesPane.vue, frontend/src/views/EditorView.vue, frontend/src/router/index.ts, frontend/src/services/api.ts
- **Components Used:** DiscrepanciesPane.vue, EditorView.vue (host), FlagLegend.vue
- **APIs Used:** GET /v1/sessions/{id}/discrepancies, GET /v1/sessions/{id}/review-queue, POST /v1/sessions/{id}/corrections (+ undo/redo), GET /v1/sessions/{id}/corrections
- **Database Tables Used:** transcription_discrepancies, alignments, word_alignment, correction_ledger, ledger_pointers, segments, words, normalization_results, org_settings, instructor_profiles, session_patterns
- **Permission Logic Used:** JWT (CurrentUser) only; no role gate on this module. LEGACY_ADMIN_EMAIL gate exists product-wide but is not applied here.
- **Confidence Score:** High — every answer traced to a read source line. Two operator-diag routes (realign, classify-route) are referenced from CLAUDE.md and noted where their handlers were not opened in this pass.
- **Evidence Links:** [app/api/corrections.py:1005](../../app/api/corrections.py#L1005), [app/tasks/classify_task.py:30](../../app/tasks/classify_task.py#L30), [app/prompts.py:29](../../app/prompts.py#L29), [app/iil/validation.py:286](../../app/iil/validation.py#L286), [frontend/src/components/editor/DiscrepanciesPane.vue:62](../../frontend/src/components/editor/DiscrepanciesPane.vue#L62)
