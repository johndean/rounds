# Quality & AI Accuracy — Product Spec

> Module key: `quality-discrepancies`. This document describes only what is implemented in this repository. Every claim is tied to a source file and line.

## Overview

The Quality & AI Accuracy module surfaces where the AI-produced transcript diverges from the raw speech-to-text (STT) output, so an operator can spend review time on the parts most likely to be wrong. It has two distinct, independently-stored signals:

1. **Transcription discrepancies** — per-word LCS diffs between the AI/normalized text and the raw Google STT text, classified by Gemini as *meaningful* (worth a human look) or *noise* (the AI correctly cleaned it up). Stored in `transcription_discrepancies` ([migrations/017_discrepancies_full.sql:9](../../migrations/017_discrepancies_full.sql#L9)).
2. **Alignment review queue** — segment-to-slide alignment rows in `uncertain` or `review` status, ordered by a fixed priority-scoring rule. Stored in `alignments` ([migrations/014_align.sql:6](../../migrations/014_align.sql#L6)) and served by `GET /v1/sessions/{id}/review-queue` ([app/api/corrections.py:978](../../app/api/corrections.py#L978)).

These two signals are produced and stored separately and are surfaced through different endpoints. The editor's **Discrepancies** pane consumes the first; the review-queue endpoint exposes the second.

A third, upstream component — the **IIL (Intelligent Instruction Loop) normalization + validation engine** — is what *creates* the "AI text" side of every discrepancy. Its validation loop (`validate_and_repair`) guarantees a clinical-safety fallback to raw STT when normalization cannot be safely repaired ([app/iil/validation.py:212](../../app/iil/validation.py#L212)).

## Purpose

Reduce the human effort needed to finish a transcript by directing the reviewer to the highest-risk segments first, while never silently shipping a broken or dropped clinical term. The classify step exists to separate substantive mistranscriptions (drug names, dosages, names, dates, clinical terms) from cosmetic cleanup (filler removal, punctuation, restyling) so a reviewer is not buried in noise ([app/prompts.py:24](../../app/prompts.py#L24)).

## User Value

- **Triage, not exhaustive review.** The Discrepancies pane defaults to the "Flagged" filter and shows a meaningful-vs-raw count so the reviewer knows how much actually needs attention ([frontend/src/components/editor/DiscrepanciesPane.vue:83](../../frontend/src/components/editor/DiscrepanciesPane.vue#L83), [DiscrepanciesPane.vue:252](../../frontend/src/components/editor/DiscrepanciesPane.vue#L252)).
- **Side-by-side comparison.** AI Transcript on the left, raw STT on the right, with the diverging fragments highlighted in both columns ([DiscrepanciesPane.vue:275](../../frontend/src/components/editor/DiscrepanciesPane.vue#L275)).
- **One-click resolution.** "Mark OK" and "Dismiss" both write a `mark_ok` correction that auto-closes the discrepancy ([DiscrepanciesPane.vue:62](../../frontend/src/components/editor/DiscrepanciesPane.vue#L62); auto-close logic [app/api/corrections.py:602](../../app/api/corrections.py#L602)).
- **Clinical-safety guarantee.** If IIL normalization drops a content word or domain term and cannot repair it within two deterministic attempts, the segment ships the raw STT verbatim instead of a broken sentence ([app/iil/validation.py:286](../../app/iil/validation.py#L286)).

## Navigation

- The **Discrepancies** view is a tab inside the **Editor** screen, rendered by `DiscrepanciesPane.vue` and mounted in `EditorView.vue` ([frontend/src/views/EditorView.vue:40](../../frontend/src/views/EditorView.vue#L40), [EditorView.vue:1381](../../frontend/src/views/EditorView.vue#L1381)). There is no standalone top-level "Quality" route.
- The **review-queue** endpoint (`GET /v1/sessions/{id}/review-queue`) has a typed frontend client (`sessions.reviewQueue`, [frontend/src/services/api.ts:547](../../frontend/src/services/api.ts#L547)). **PARTIALLY IMPLEMENTED:** the editor (`EditorView.vue`) does not invoke `reviewQueue` — the review-queue endpoint is exposed and typed but no view component calls it. (Verified by grep over `EditorView.vue`: only `DiscrepanciesPane` references were found.)
- The **FlagLegend** component (a three-chip legend: drift / uncertain / low confidence) is a static visual legend with no data binding ([frontend/src/components/editor/FlagLegend.vue:9](../../frontend/src/components/editor/FlagLegend.vue#L9)).

## Screens

### Discrepancies pane (`DiscrepanciesPane.vue`)

- **Live-data banner** stating the count of LCS-detected diffs sourced from `transcription_discrepancies` ([DiscrepanciesPane.vue:235](../../frontend/src/components/editor/DiscrepanciesPane.vue#L235)).
- **Toolbar** with a count summary (`<meaningfulCount> flagged for review · <totalDiffs> raw diffs`) and a three-button filter radio group: **All**, **Flagged**, **Meaningful** ([DiscrepanciesPane.vue:252](../../frontend/src/components/editor/DiscrepanciesPane.vue#L252)).
- **Split comparison** with two columns: "AI Transcript" and "STT Raw" (marked `read-only`) ([DiscrepanciesPane.vue:275](../../frontend/src/components/editor/DiscrepanciesPane.vue#L275)).
- **Per-segment row actions:** Edit, Reassign, and (when flagged) Mark OK / Dismiss ([DiscrepanciesPane.vue:295](../../frontend/src/components/editor/DiscrepanciesPane.vue#L295)).
- **Diff count chip** per flagged segment showing the number of diffs attached ([DiscrepanciesPane.vue:296](../../frontend/src/components/editor/DiscrepanciesPane.vue#L296)).
- **Empty state:** "All clean — no discrepancies matching this filter." ([DiscrepanciesPane.vue:354](../../frontend/src/components/editor/DiscrepanciesPane.vue#L354)).

### FlagLegend (`FlagLegend.vue`)

Static legend with three labels — `drift`, `uncertain`, `low confidence` — styled via CSS classes `flag-drift`, `flag-uncertain`, `flag-low_confidence`. No props, no data ([FlagLegend.vue:9](../../frontend/src/components/editor/FlagLegend.vue#L9)).

## User Flows

### 1. Review and resolve discrepancies

1. Session reaches `ready`; classify runs in the background ([app/tasks/classify_task.py:60](../../app/tasks/classify_task.py#L60)).
2. Operator opens the Editor → Discrepancies tab. The pane loads `liveDiscrepancies` (from `GET /v1/sessions/{id}/discrepancies`) and groups them by `segment_id` ([DiscrepanciesPane.vue:109](../../frontend/src/components/editor/DiscrepanciesPane.vue#L109)).
3. Operator reviews flagged segments (default filter = "Flagged"), comparing the AI column with the highlighted STT column ([DiscrepanciesPane.vue:157](../../frontend/src/components/editor/DiscrepanciesPane.vue#L157)).
4. Operator either:
   - **Edits** the text (pivots to the AI tab via `requestEdit`) ([DiscrepanciesPane.vue:207](../../frontend/src/components/editor/DiscrepanciesPane.vue#L207)) — a `text_edit` correction auto-closes the discrepancy ([app/api/corrections.py:602](../../app/api/corrections.py#L602)); or
   - **Marks OK / Dismisses** — both POST a `mark_ok` correction, which auto-closes the discrepancy ([DiscrepanciesPane.vue:62](../../frontend/src/components/editor/DiscrepanciesPane.vue#L62)).
5. On success, the pane optimistically emits `discrepancyResolved` so the parent removes the row; a WebSocket `discrepancy_resolved` event triggers a quiet refresh ([app/api/corrections.py:630](../../app/api/corrections.py#L630); [EditorView.vue:442](../../frontend/src/views/EditorView.vue#L442)).

### 2. Live classification update

1. `classify_discrepancies_task` writes verdicts and emits a `classification_complete` or `classification_partial` WS event ([app/tasks/classify_task.py:207](../../app/tasks/classify_task.py#L207)).
2. The editor's WS subscriber calls `scheduleQuietRefresh`, re-fetching discrepancies so the "Meaningful" count updates without a manual reload ([EditorView.vue:447](../../frontend/src/views/EditorView.vue#L447)).

## Business Rules

- **BR-006 — Review-queue priority scoring.** Alignment rows are ordered by an additive score: drift + no slide = +100; uncertain + no slide = +90; confidence < 0.4 = +70; drift = +50; status `review` = +40; confidence < 0.6 = +20. Multiple bonuses stack (a sub-0.4 row earns both the <0.4 and <0.6 bonuses) ([app/api/corrections.py:1005](../../app/api/corrections.py#L1005)).
- **BR-018 — Correction types that auto-close discrepancies.** Only `text_edit` and `mark_ok` auto-close an unresolved discrepancy on the same segment. Other types (find/replace, chat edits, speaker reassignment) deliberately do not ([app/api/corrections.py:63](../../app/api/corrections.py#L63), [corrections.py:602](../../app/api/corrections.py#L602)).
- **Classification meaningful/noise taxonomy.** Meaningful categories: `medication`, `number`, `name`, `date`, `terminology`, `other`. Noise categories: `filler`, `punctuation`, `style`. When unsure between style and terminology, the prompt instructs the model to lean meaningful ([app/prompts.py:29](../../app/prompts.py#L29)). The engine forces any out-of-set category to `other` ([app/engines/llm_client.py:377](../../app/engines/llm_client.py#L377)).
- **Classification is non-critical.** A failed classify never marks the session `failed`; it logs and emits a WS event only ([app/tasks/classify_task.py:30](../../app/tasks/classify_task.py#L30)).
- **IIL clinical-safety fallback (RULE 4).** After two failed repair attempts, `normalized_text` is set to raw STT and all four validation checks marked `fail` ([app/iil/validation.py:286](../../app/iil/validation.py#L286)).
- **IIL TIER-1 always-remove fillers.** `um, uh, er, ah, umm, uhh, hmm` are always removed when tier-1 normalization is enabled ([app/iil/normalization.py:40](../../app/iil/normalization.py#L40), [normalization.py:191](../../app/iil/normalization.py#L191)).
- **IIL TIER-2 conditional keep.** Discourse markers (`basically, right, you know, like, okay, so, well, i mean, sort of, kind of`) are kept by default and only removed when not first-word, not a domain term, not context-dependent, and removal confidence exceeds the policy threshold (0.70 default / 0.85 moderate) ([app/iil/normalization.py:42](../../app/iil/normalization.py#L42), [normalization.py:219](../../app/iil/normalization.py#L219)).
- **No-hallucination rule (RULE 2).** Normalized output contains only words present in the source `words[]`; restoration repair splices missing words back from that source-of-truth ([app/iil/normalization.py](../../app/iil/normalization.py); repair at [app/iil/validation.py:173](../../app/iil/validation.py#L173)).
- **Key Points gating (KP-02/KP-03).** Key points are unavailable for segments with no slide or `uncertain` status, and are never part of the transcript text ([app/iil/key_points.py:42](../../app/iil/key_points.py#L42)).

## Validation Rules

- **IIL four checks** run after normalization ([app/iil/validation.py:242](../../app/iil/validation.py#L242)):
  - `check1` — content words (>3 chars, non-TIER1) from `words[]` preserved.
  - `check2` — domain terms (>3 chars from slide context) preserved if they were in raw.
  - `check3` — no TIER1 words remain in normalized text.
  - `check4` — when `structure_extraction=False`, `key_points` must be empty.
- **Repair routing:** `check1`/`check2` failures trigger word-restoration; `check3`/`check4` failures trigger a re-normalize. Maximum 2 repair attempts ([app/iil/validation.py:61](../../app/iil/validation.py#L61), [validation.py:259](../../app/iil/validation.py#L259)).
- **Classification verdict validation:** each verdict must have an `id` and a boolean `is_meaningful`; the task validates each `id` is a UUID before writing and skips malformed ones ([app/engines/llm_client.py:369](../../app/engines/llm_client.py#L369); [app/tasks/classify_task.py:166](../../app/tasks/classify_task.py#L166)).
- **Discrepancy query filters:** `category` (one of the documented categories) and `meaningful_only` (excludes rows where `is_meaningful = false`) ([app/api/discrepancies.py:54](../../app/api/discrepancies.py#L54)).

## States

### Discrepancy row states (`transcription_discrepancies`)

- **Unclassified** — `is_meaningful IS NULL` (set at insert by `lcs_discrepancies_task`) ([migrations/017_discrepancies_full.sql:16](../../migrations/017_discrepancies_full.sql#L16)).
- **Classified meaningful** — `is_meaningful = TRUE`, with `category`, `classifier_model`, `classified_at` set ([app/tasks/classify_task.py:172](../../app/tasks/classify_task.py#L172)).
- **Classified noise** — `is_meaningful = FALSE`.
- **Resolved** — `resolved = TRUE` with `resolution_correction_id` and `resolved_at` (set when a `text_edit`/`mark_ok` correction lands) ([app/api/corrections.py:607](../../app/api/corrections.py#L607)).

### Session-level classification status (computed in the list endpoint)

- `complete` — zero discrepancies, or all classified.
- `partial` — some classified.
- `pending` — none classified ([app/api/discrepancies.py:96](../../app/api/discrepancies.py#L96)).

### Alignment statuses (`alignments.status`)

`assigned`, `uncertain`, `review` — constrained by a CHECK ([migrations/014_align.sql:17](../../migrations/014_align.sql#L17)). The review-queue endpoint returns only `uncertain` and `review` ([app/api/corrections.py:991](../../app/api/corrections.py#L991)).

## Dependencies

- **Upstream:** `normalize_task` (produces `normalization_results`) → `lcs_discrepancies_task` (LCS diff + word alignment) → `classify_discrepancies_task` (Gemini verdicts) ([app/tasks/lcs_discrepancies.py:182](../../app/tasks/lcs_discrepancies.py#L182)).
- **Tables read:** `segments`, `words`, `normalization_results` (for the AI/STT pairing) ([app/tasks/lcs_discrepancies.py:68](../../app/tasks/lcs_discrepancies.py#L68)).
- **External:** Gemini API (developer key) or Vertex AI Gemini, routed by `org_settings.classify_backend` ([app/tasks/classify_task.py:90](../../app/tasks/classify_task.py#L90); [app/engines/llm_client.py:422](../../app/engines/llm_client.py#L422)).
- **Frontend:** `DiscrepanciesPane` depends on `liveSegments`, `liveSlides`, `liveDiscrepancies`, and `liveWords` passed from `EditorView` ([DiscrepanciesPane.vue:36](../../frontend/src/components/editor/DiscrepanciesPane.vue#L36)).

## Error Handling

- **Classification failures are swallowed:** `_ClassifyTask.on_failure` logs and emits `classification_failed`; the session status is unchanged ([app/tasks/classify_task.py:36](../../app/tasks/classify_task.py#L36)). The editor shows an info toast prefixed "Background:" ([EditorView.vue:453](../../frontend/src/views/EditorView.vue#L453)).
- **Terminal model state abort:** if a single pre-flight probe batch fails with a terminal category (deprecated model, config error, context overflow, validation), the task aborts the whole run instead of looping every batch ([app/tasks/classify_task.py:131](../../app/tasks/classify_task.py#L131); terminal set [app/engines/llm_client.py:42](../../app/engines/llm_client.py#L42)).
- **Partial classification:** if some rows remain `NULL`, the task raises `LLMError` to trigger Celery's retry backoff, re-loading and skipping already-done rows ([app/tasks/classify_task.py:230](../../app/tasks/classify_task.py#L230)).
- **LCS task failure is non-fatal:** discrepancies are an "editor convenience, not a gate"; terminal failure logs and returns an error dict ([app/tasks/lcs_discrepancies.py:199](../../app/tasks/lcs_discrepancies.py#L199)).
- **Mark OK / Dismiss UI errors** surface as an error toast with the HTTP status ([DiscrepanciesPane.vue:75](../../frontend/src/components/editor/DiscrepanciesPane.vue#L75)).
- **IIL normalization exception:** RULE 4 returns raw text unchanged on any exception ([app/iil/normalization.py:126](../../app/iil/normalization.py#L126)).

## Permissions

**Role-based authorization is not active in this module.** Every endpoint requires only a valid JWT via `CurrentUser` ([app/api/discrepancies.py:53](../../app/api/discrepancies.py#L53); [app/api/corrections.py:333](../../app/api/corrections.py#L333), [corrections.py:979](../../app/api/corrections.py#L979)). There is no role check, no `require_admin`, and no `auth_users.role` read on any discrepancy or correction route.

- The only admin gate in the wider product is a hardcoded `email == 'johndean@vin.com'` comparison used in a handful of places and a single client-side route guard `to.meta.adminOnly && auth.email !== LEGACY_ADMIN_EMAIL` ([frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63), [index.ts:51](../../frontend/src/router/index.ts#L51)). **None of the Quality & AI routes are behind that guard.**
- `applied_by` on corrections is taken from `user.email` for the audit trail, not for authorization ([app/api/corrections.py:531](../../app/api/corrections.py#L531)).

## Reporting Impacts

- **No accuracy reporting/dashboard exists.** There is no endpoint or view aggregating discrepancy counts across sessions, per-category statistics, or accuracy trends. Verified: the discrepancies router exposes only a single per-session `GET` list endpoint ([app/api/discrepancies.py:49](../../app/api/discrepancies.py#L49)).
- The list endpoint returns per-session counts (`count`, `classified_count`, `classification_status`) — these are point-in-time, single-session figures, not historical metrics ([app/api/discrepancies.py:105](../../app/api/discrepancies.py#L105)).
- The Discrepancies pane shows session-local counts only (flagged-for-review and raw-diff totals) ([DiscrepanciesPane.vue:135](../../frontend/src/components/editor/DiscrepanciesPane.vue#L135)).

## Audit Requirements

- **Resolutions are recorded twice:** as an append-only `correction_ledger` row (with `applied_by`, `action_id`, `sequence_number`) ([app/api/corrections.py:537](../../app/api/corrections.py#L537)) and as a back-reference on the discrepancy (`resolution_correction_id`, `resolved_at`) ([app/api/corrections.py:607](../../app/api/corrections.py#L607)).
- **Corrections are append-only** — UPDATE/DELETE on the ledger is forbidden; undo/redo moves a pointer rather than mutating rows ([app/api/corrections.py:9](../../app/api/corrections.py#L9)).
- **Classifier provenance:** each classified discrepancy stores `classifier_model` and `classified_at` ([app/tasks/classify_task.py:178](../../app/tasks/classify_task.py#L178); [migrations/017_discrepancies_full.sql:17](../../migrations/017_discrepancies_full.sql#L17)).
- **IIL validation audit trail:** normalization stores the per-tier removed/kept lists and `validation_checks` in `NormalizedResult`, intended for the `normalization_results.validation_results` JSONB blob ([app/iil/normalization.py:20](../../app/iil/normalization.py#L20)).

## Data Relationships

- `sessions` 1—N `transcription_discrepancies` (FK `session_id`, cascade delete) ([migrations/017_discrepancies_full.sql:11](../../migrations/017_discrepancies_full.sql#L11)).
- `segments` 1—N `transcription_discrepancies` (FK `segment_id`, cascade delete) ([migrations/017_discrepancies_full.sql:12](../../migrations/017_discrepancies_full.sql#L12)).
- `correction_ledger` row ← referenced by `transcription_discrepancies.resolution_correction_id` (the close back-reference) ([app/api/corrections.py:609](../../app/api/corrections.py#L609)).
- `segments` 1—1 `alignments` (UNIQUE `session_id, segment_id`); `alignments` → `slides` (nullable FK) ([migrations/014_align.sql:9](../../migrations/014_align.sql#L9)).
- `alignments` 1—N `validation_results` (verdict APPROVE/REVIEW/ESCALATE) ([migrations/014_align.sql:27](../../migrations/014_align.sql#L27)).
- `segments` 1—N `word_alignment` (per-Gemini-word STT timestamp pairing, populated by the same LCS task) ([migrations/036_word_alignment.sql:23](../../migrations/036_word_alignment.sql#L23)).
- IIL learning: `instructor_profiles` carries rolling `avg_filler_rate`, `avg_compression_ratio`, `filler_words` ([migrations/019_iil_learning.sql:5](../../migrations/019_iil_learning.sql#L5), [migrations/021_iil_features.sql:6](../../migrations/021_iil_features.sql#L6)); `session_instructor_map`, `session_patterns`, `key_points_annotations` ([migrations/019_iil_learning.sql:19](../../migrations/019_iil_learning.sql#L19)).

> **Two discrepancy tables exist.** The legacy `discrepancies` table (`kind`/`severity`/`classification` JSONB, [migrations/002_discrepancies.sql:3](../../migrations/002_discrepancies.sql#L3)) is **not** read by the live discrepancies endpoint — the endpoint reads `transcription_discrepancies`. The header comment in [app/api/discrepancies.py:7](../../app/api/discrepancies.py#L7) explicitly notes the endpoint was re-pointed away from the unused `discrepancies` table. **IMPLEMENTATION NOT FOUND:** no live route reads the `discrepancies` table (or its `corrections` companion table from migration 002).

## Known Constraints

- **You cannot manually set a segment's confidence score.** Confidence is the AI/alignment value; the UI offers confirm/edit/dismiss, not a numeric override. (No write path for `alignments.confidence` exists in this module.)
- **No cross-session accuracy trends or per-flag statistics** (see Reporting Impacts).
- **Corrections do not retrain the transcription engine.** IIL adaptive learning updates *instructor profiles* (filler rate, compression ratio, discovered fillers) from normalization stats — it does not feed editor corrections back into Gemini ([app/iil/adaptive_learning.py:28](../../app/iil/adaptive_learning.py#L28)).
- **The review-queue endpoint has no consuming UI** (PARTIALLY IMPLEMENTED — see Navigation).
- **The `note` field shown sent by the Dismiss action is not modeled by the backend.** `DiscrepanciesPane` adds `note: 'dismissed'` to the request body ([DiscrepanciesPane.vue:71](../../frontend/src/components/editor/DiscrepanciesPane.vue#L71)), but `CorrectionRequest` has no `note` field ([app/api/corrections.py:90](../../app/api/corrections.py#L90)), so FastAPI ignores it. "Mark OK" and "Dismiss" are therefore stored identically as `mark_ok` corrections.
- **Vertex AI classification is off by default** (`VERTEX_AI_CLASSIFY_ENABLED=false`); routing to Vertex requires `org_settings.classify_backend = 'vertex'` ([app/config.py:86](../../app/config.py#L86); [app/tasks/classify_task.py:109](../../app/tasks/classify_task.py#L109)).
- **FlagLegend is static.** Its drift/uncertain/low-confidence chips are a visual legend, not bound to any flag data ([FlagLegend.vue:9](../../frontend/src/components/editor/FlagLegend.vue#L9)).

## Source Verification
- **Files Used:** app/api/discrepancies.py, app/api/corrections.py, app/tasks/classify_task.py, app/tasks/lcs_discrepancies.py, app/engines/llm_client.py, app/engines/diff.py, app/iil/validation.py, app/iil/adaptive_learning.py, app/iil/normalization.py, app/iil/key_points.py, app/prompts.py, app/config.py, app/main.py, migrations/002_discrepancies.sql, migrations/014_align.sql, migrations/017_discrepancies_full.sql, migrations/019_iil_learning.sql, migrations/021_iil_features.sql, migrations/036_word_alignment.sql, frontend/src/components/editor/DiscrepanciesPane.vue, frontend/src/components/editor/FlagLegend.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts, docs/product/quality-ai.md (seed)
- **Components Used:** DiscrepanciesPane.vue, FlagLegend.vue, EditorView.vue (host)
- **APIs Used:** GET /v1/sessions/{id}/discrepancies, GET /v1/sessions/{id}/review-queue, POST /v1/sessions/{id}/corrections (mark_ok/text_edit auto-close)
- **Database Tables Used:** transcription_discrepancies, alignments, validation_results, word_alignment, correction_ledger, ledger_pointers, segments, words, normalization_results, instructor_profiles, session_instructor_map, session_patterns, key_points_annotations; legacy (unused) discrepancies + corrections from migration 002
- **Permission Logic Used:** JWT presence only (CurrentUser). No role gate on any Quality/AI route. LEGACY_ADMIN_EMAIL gate documented but not applied here.
- **Confidence Score:** High — every claim traced to a read source line; the one race-condition area (note field) was verified against the Pydantic model.
- **Evidence Links:** [app/api/discrepancies.py:49](../../app/api/discrepancies.py#L49), [app/api/corrections.py:1005](../../app/api/corrections.py#L1005), [app/tasks/classify_task.py:30](../../app/tasks/classify_task.py#L30), [app/iil/validation.py:286](../../app/iil/validation.py#L286), [migrations/017_discrepancies_full.sql:9](../../migrations/017_discrepancies_full.sql#L9), [frontend/src/components/editor/DiscrepanciesPane.vue:62](../../frontend/src/components/editor/DiscrepanciesPane.vue#L62)
