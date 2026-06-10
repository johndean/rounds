# Corrections & Audit — Demo Questions

> Every answer below is verified against current code in this repo. Paths are
> relative to this file (`ai-demo-knowledge/demo-questions/`). Personas with no
> code-true question are omitted.

---

## User

### Q: How do I undo and redo my edits in a session?
- **Verified Answer:** Undo and redo call `POST /v1/sessions/{id}/corrections/undo`
  and `.../redo`. Each moves a single per-session pointer (`current_pointer`)
  rather than deleting your edit history. Undo decrements the pointer (and inverts
  any split/merge in that range); redo increments it. Undo at the start returns
  `nothing_to_undo`; redo at the tip returns `nothing_to_redo`.
- **Supporting Evidence:** [app/api/corrections.py:883-924](../../app/api/corrections.py#L883-L924) (undo),
  [app/api/corrections.py:928-974](../../app/api/corrections.py#L928-L974) (redo).
- **Source Files:** app/api/corrections.py, frontend/src/services/api.ts
- **API References:** POST /v1/sessions/{id}/corrections/undo, POST /v1/sessions/{id}/corrections/redo
- **Database References:** ledger_pointers, correction_ledger

### Q: If I edit a segment that had a flagged discrepancy, do I have to resolve it separately?
- **Verified Answer:** No. A `text_edit` or `mark_ok` correction automatically marks
  the segment's unresolved `transcription_discrepancies` row resolved, with a
  back-reference to the correction that closed it. Other correction types do not
  auto-close.
- **Supporting Evidence:** [app/api/corrections.py:55-63](../../app/api/corrections.py#L55-L63) (CLOSES_DISCREPANCY_TYPES),
  [app/api/corrections.py:601-620](../../app/api/corrections.py#L601-L620).
- **Source Files:** app/api/corrections.py, migrations/029_corrections.sql
- **API References:** POST /v1/sessions/{id}/corrections
- **Database References:** transcription_discrepancies, correction_ledger

### Q: How does Find/Replace preview work before I commit?
- **Verified Answer:** Post to `/v1/sessions/{id}/find-replace` with `dry_run: true`.
  It returns the matched segments, per-segment match counts, and total matches with
  `applied: false` — no writes. Running it without `dry_run` writes one `text_edit`
  per affected segment.
- **Supporting Evidence:** [app/api/corrections.py:742-754](../../app/api/corrections.py#L742-L754) (dry_run preview),
  [app/api/corrections.py:759-799](../../app/api/corrections.py#L759-L799) (apply).
- **Source Files:** app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/find-replace
- **Database References:** correction_ledger, segments, normalization_results

### Q: If I undo, then a find/replace, can I still redo my old changes?
- **Verified Answer:** No. Recording any new correction abandons the redo branch:
  rows with `sequence_number > current_pointer` are deleted. After a new write,
  there is nothing to redo forward into.
- **Supporting Evidence:** [app/api/corrections.py:188-198](../../app/api/corrections.py#L188-L198) (`_truncate_redo_tail`),
  invoked at [app/api/corrections.py:527](../../app/api/corrections.py#L527) and [app/api/corrections.py:757](../../app/api/corrections.py#L757).
- **Source Files:** app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections, POST /v1/sessions/{id}/find-replace
- **Database References:** correction_ledger, ledger_pointers

### Q: How do I split or merge segments, and why might the option be missing?
- **Verified Answer:** In the editor, right-click (or Ctrl/Cmd+Shift+S to split,
  Ctrl/Cmd+Shift+M to merge). The UI is hidden unless the backend feature flag
  `split_merge_enabled` is on (read at app mount). If you call the API while it is
  off, you get `503 SPLIT_MERGE_DISABLED`.
- **Supporting Evidence:** [frontend/src/components/editor/SegmentText.vue:96-97](../../frontend/src/components/editor/SegmentText.vue#L96-L97),
  [app/config.py:134](../../app/config.py#L134), [app/api/corrections.py:360-363](../../app/api/corrections.py#L360-L363).
- **Source Files:** frontend/src/components/editor/SegmentText.vue, app/config.py, app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections (correction_type split/merge)
- **Database References:** segments, word_alignment

---

## Operations

### Q: Why would a segment split fail with a 422?
- **Verified Answer:** A split returns `422 SPLIT_NO_WORD_ALIGNMENT` when the
  segment has no `word_alignment` rows — split needs word-level timing to compute
  the cut point. Re-running the alignment backfill (operator `/v1/diag/realign`)
  populates `word_alignment` for legacy sessions.
- **Supporting Evidence:** [app/services/segment_split.py:48-55](../../app/services/segment_split.py#L48-L55).
- **Source Files:** app/services/segment_split.py
- **API References:** POST /v1/sessions/{id}/corrections (split)
- **Database References:** word_alignment, segments

### Q: What does SPLIT_MERGE_BUSY mean and is it safe to retry?
- **Verified Answer:** It is a `409` returned when another split/merge/undo/redo for
  the same session already holds the `split_merge` advisory lock. The frontend
  retries the operation once after 1 second. It is safe because identical requests
  carrying the same `action_id` are deduped inside the lock and replay the cached
  result rather than executing twice.
- **Supporting Evidence:** [app/api/corrections.py:365-371](../../app/api/corrections.py#L365-L371),
  [frontend/src/components/editor/SegmentText.vue:318-321](../../frontend/src/components/editor/SegmentText.vue#L318-L321),
  [app/services/db_locks.py:94-149](../../app/services/db_locks.py#L94-L149).
- **Source Files:** app/api/corrections.py, app/services/db_locks.py, frontend/src/components/editor/SegmentText.vue
- **API References:** POST /v1/sessions/{id}/corrections
- **Database References:** correction_ledger

### Q: A split/merge is 500-ing in production. Where do I look?
- **Verified Answer:** The dispatch wraps the executor + ledger write so any
  unhandled exception is logged with a full traceback via `_log.exception` (so it
  surfaces in `railway logs --service api --deployment`) and returned as a structured
  `500 SPLIT_MERGE_EXEC_ERROR` carrying `error_class` and a truncated `error_message`.
  Read the toast / DevTools body for the class+message, then grep the deploy log.
- **Supporting Evidence:** [app/api/corrections.py:417-437](../../app/api/corrections.py#L417-L437).
- **Source Files:** app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections
- **Database References:** correction_ledger

### Q: How is the review queue ordered so reviewers see the worst problems first?
- **Verified Answer:** `GET /v1/sessions/{id}/review-queue` returns `alignments` rows
  in `uncertain` or `review` status, sorted by a fixed additive priority score:
  drift + no slide = +100, uncertain + no slide = +90, confidence < 0.4 = +70,
  drift = +50, status `review` = +40, confidence < 0.6 = +20. Bonuses stack.
- **Supporting Evidence:** [app/api/corrections.py:978-1033](../../app/api/corrections.py#L978-L1033) (scoring at 1005-1013).
- **Source Files:** app/api/corrections.py
- **API References:** GET /v1/sessions/{id}/review-queue
- **Database References:** alignments

### Q: Can I filter the global audit feed to one session or actor?
- **Verified Answer:** Yes. `GET /v1/audit` accepts `session_id`, `actor`, and `kind`
  query params plus `limit` (capped at 500) and `offset`, ordered by `occurred_at`
  descending. `actor` is lowercased before matching.
- **Supporting Evidence:** [app/api/audit.py:18-42](../../app/api/audit.py#L18-L42).
- **Source Files:** app/api/audit.py
- **API References:** GET /v1/audit
- **Database References:** audit_events

### Q: Does enabling split/merge require a code deploy?
- **Verified Answer:** No code change — flip `SPLIT_MERGE_ENABLED=true` in the
  Railway `api` and `worker` env vars. It defaults to `False`. The frontend reads
  the flag from `/v1/version` at mount and reveals the split/merge UI accordingly.
- **Supporting Evidence:** [app/config.py:125-134](../../app/config.py#L125-L134),
  [frontend/src/components/AppHeader.vue:53-62](../../frontend/src/components/AppHeader.vue#L53-L62).
- **Source Files:** app/config.py, frontend/src/components/AppHeader.vue, frontend/src/stores/featureFlags.ts
- **API References:** GET /v1/version (consumed; defined outside this module)
- **Database References:** none

---

## Compliance

### Q: Is the correction history truly immutable / append-only?
- **Verified Answer:** It is append-only by application invariant: corrections are
  inserted, never UPDATEd or DELETEd in place, and undo/redo only move a pointer.
  One qualification: recording a new correction physically deletes any abandoned
  redo-branch rows (those past the pointer), so "never deleted" holds only for rows
  at or before the pointer. There is no database trigger enforcing immutability —
  it is enforced in code.
- **Supporting Evidence:** [app/api/corrections.py:9-11](../../app/api/corrections.py#L9-L11) (invariant statement),
  [app/api/corrections.py:188-198](../../app/api/corrections.py#L188-L198) (redo-tail delete).
- **Source Files:** app/api/corrections.py, migrations/029_corrections.sql
- **API References:** POST /v1/sessions/{id}/corrections
- **Database References:** correction_ledger, ledger_pointers

### Q: How do you know who made each correction?
- **Verified Answer:** Every ledger row stores `applied_by`, set from the
  authenticated JWT user's email (defaulting to `"(unknown)"` if absent), plus an
  `applied_at` timestamp. Global `audit_events` rows store `actor_email` and
  `occurred_at`.
- **Supporting Evidence:** [app/api/corrections.py:531](../../app/api/corrections.py#L531),
  [migrations/029_corrections.sql:97-98](../../migrations/029_corrections.sql#L97-L98), [migrations/004_audit.sql:7-10](../../migrations/004_audit.sql#L7-L10).
- **Source Files:** app/api/corrections.py, migrations/029_corrections.sql, migrations/004_audit.sql
- **API References:** GET /v1/sessions/{id}/corrections, GET /v1/audit
- **Database References:** correction_ledger, audit_events

### Q: When a discrepancy is closed, is there a traceable link to what fixed it?
- **Verified Answer:** Yes. Closing a discrepancy sets `resolved = TRUE`,
  `resolved_at = now()`, and `resolution_correction_id` to the closing correction's
  id (a FK into `correction_ledger`). That gives a direct lineage from the flagged
  discrepancy to the edit that resolved it.
- **Supporting Evidence:** [app/api/corrections.py:602-620](../../app/api/corrections.py#L602-L620),
  [migrations/029_corrections.sql:143-149](../../migrations/029_corrections.sql#L143-L149).
- **Source Files:** app/api/corrections.py, migrations/029_corrections.sql
- **API References:** POST /v1/sessions/{id}/corrections
- **Database References:** transcription_discrepancies, correction_ledger

### Q: Are merges across a slide boundary recorded?
- **Verified Answer:** Yes. Merging two segments assigned to different slides is
  allowed (the left segment's slide wins), but it writes a `merge.slide_mismatch`
  row into `audit_events` recording both slide ids and the actor — so the boundary
  crossing is captured in the audit feed.
- **Supporting Evidence:** [app/services/segment_merge.py:74-88](../../app/services/segment_merge.py#L74-L88).
- **Source Files:** app/services/segment_merge.py
- **API References:** POST /v1/sessions/{id}/corrections (merge)
- **Database References:** audit_events, segments

### Q: Can correction records be exported for an audit?
- **Verified Answer:** Yes, from the browser. The per-session Word Track Changes
  screen exports the corrections as JSONL (`audit.jsonl`); the global feed exports as
  `audit-events.jsonl`; the editor Audit tab exports CSV (`audit.csv`). These are
  client-side serializations of the loaded data; there is no separate server report
  endpoint.
- **Supporting Evidence:** [frontend/src/views/AuditView.vue:125-137](../../frontend/src/views/AuditView.vue#L125-L137),
  [frontend/src/components/editor/AuditTabInline.vue:48-60](../../frontend/src/components/editor/AuditTabInline.vue#L48-L60).
- **Source Files:** frontend/src/views/AuditView.vue, frontend/src/components/editor/AuditTabInline.vue
- **API References:** GET /v1/audit/sessions/{id}/corrections, GET /v1/audit
- **Database References:** correction_ledger, audit_events

---

## Administrator

### Q: Do you need admin rights to apply corrections or view the audit log?
- **Verified Answer:** No. Every Corrections & Audit endpoint requires only a valid
  JWT (`CurrentUser`). Neither `app/api/corrections.py` nor `app/api/audit.py`
  contains any `require_admin` / `is_admin` / admin-email check. Role-based auth is
  scaffold-only repo-wide and is not wired into these endpoints.
- **Supporting Evidence:** dependency `CurrentUser` on every route
  ([app/api/corrections.py:337](../../app/api/corrections.py#L337), [app/api/audit.py:20](../../app/api/audit.py#L20));
  scaffold note [app/security/roles.py:10-19](../../app/security/roles.py#L10-L19); `get_current_user` does not read
  `role` [app/auth.py:172-205](../../app/auth.py#L172-L205).
- **Source Files:** app/api/corrections.py, app/api/audit.py, app/security/roles.py, app/auth.py
- **API References:** all /v1/sessions/{id}/corrections*, /v1/sessions/{id}/find-replace, /v1/sessions/{id}/review-queue, /v1/audit*
- **Database References:** auth_users (role column present, unused), correction_ledger, audit_events

### Q: How is duplicate-application of a split/merge prevented (e.g. a retried request)?
- **Verified Answer:** Each structural request can carry an `action_id`. Inside the
  `split_merge` advisory lock, the handler checks for an existing ledger row with
  that `action_id` and, if found, returns the original response shape (reconstructed
  from the stored invert payload) marked `deduped: true` — without re-executing.
- **Supporting Evidence:** [app/api/corrections.py:368-371](../../app/api/corrections.py#L368-L371) (dedup in lock),
  [app/api/corrections.py:262-328](../../app/api/corrections.py#L262-L328) (`_replay_existing`).
- **Source Files:** app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections
- **Database References:** correction_ledger

### Q: Why are there two correction tables in the schema?
- **Verified Answer:** A legacy `corrections` table (migration 002:
  `actor_email/kind/was/now_/occurred_at`) predates the Phase 4 MIC-parity
  `correction_ledger` + `ledger_pointers` (migration 029). An earlier 029 collided
  on the `corrections` name; `000_fix_corrections_collision.sql` (sorts before 001)
  cleans the partial state so both schemas coexist. The audit API now reads
  `correction_ledger`, not the legacy table.
- **Supporting Evidence:** [migrations/029_corrections.sql:1-20](../../migrations/029_corrections.sql#L1-L20),
  [migrations/000_fix_corrections_collision.sql:1-48](../../migrations/000_fix_corrections_collision.sql#L1-L48),
  [migrations/002_discrepancies.sql:26-39](../../migrations/002_discrepancies.sql#L26-L39), [app/api/audit.py:45-53](../../app/api/audit.py#L45-L53).
- **Source Files:** migrations/029_corrections.sql, migrations/000_fix_corrections_collision.sql, migrations/002_discrepancies.sql, app/api/audit.py
- **API References:** GET /v1/audit/sessions/{id}/corrections
- **Database References:** corrections (legacy), correction_ledger, ledger_pointers

### Q: How is the append-only ledger protected from sequence_number collisions under concurrency?
- **Verified Answer:** Before computing `MAX(sequence_number)+1`, `_next_seq` takes a
  row-level `FOR UPDATE` lock on the session's `ledger_pointers` row, serializing all
  ledger writes for that session through one row. The independent `split_merge`
  advisory lock guards structural ops separately.
- **Supporting Evidence:** [app/api/corrections.py:153-185](../../app/api/corrections.py#L153-L185).
- **Source Files:** app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections, POST /v1/sessions/{id}/find-replace
- **Database References:** ledger_pointers, correction_ledger

---

## Power User

### Q: How does undo correctly reverse a split or merge, not just text?
- **Verified Answer:** Structural ops persist a JSON invert payload in the ledger
  row's `new_text`. On undo, the handler walks `split`/`merge` rows in the undone
  range newest-first and calls `apply_inverse_for_correction`, which runs
  `invert_split` (re-merge the two halves) or `invert_merge` (re-insert the deleted
  right segment + roll left back). Redo replays oldest-first via the forward
  functions. Word alignment and key-points are reparented symmetrically.
- **Supporting Evidence:** [app/api/corrections.py:890-921](../../app/api/corrections.py#L890-L921) (undo replay),
  [app/services/segment_inverse.py:46-73](../../app/services/segment_inverse.py#L46-L73), [app/services/segment_split.py:219-261](../../app/services/segment_split.py#L219-L261).
- **Source Files:** app/api/corrections.py, app/services/segment_inverse.py, app/services/segment_split.py, app/services/segment_merge.py
- **API References:** POST /v1/sessions/{id}/corrections/undo, .../redo
- **Database References:** correction_ledger, segments, word_alignment, key_points_annotations

### Q: How does Find/Replace decide what text it is actually replacing in a segment?
- **Verified Answer:** Effective text is a 3-layer precedence: the most recent
  `text_edit` correction at-or-before the pointer, else the segment's
  `normalized_text` (from `normalization_results`, tolerated if absent), else the raw
  `segments.text`. A compiled regex of the escaped `find` term (case-insensitive
  unless `case_sensitive`) replaces all occurrences in that effective text.
- **Supporting Evidence:** [app/api/corrections.py:676-738](../../app/api/corrections.py#L676-L738) (precedence at 726,
  regex at 720-732).
- **Source Files:** app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/find-replace
- **Database References:** correction_ledger, normalization_results, segments

### Q: What is expected_content_hash and when should a client send it?
- **Verified Answer:** It is an optional optimistic-concurrency token on a
  `text_edit`. When provided, the segment write is conditional on
  `content_hash = :expected_hash`; if a split (or other op) changed the segment
  server-side, the conditional UPDATE affects 0 rows and the autosave is dropped as
  stale (returns `stale: true`, no ledger row, no redo-tail truncation). Callers that
  omit it get the legacy unconditional write. The editor autosave does not yet send
  it (noted as out of scope).
- **Supporting Evidence:** [app/api/corrections.py:102-112](../../app/api/corrections.py#L102-L112) (field + TODO),
  [app/api/corrections.py:482-525](../../app/api/corrections.py#L482-L525) (stale-drop logic).
- **Source Files:** app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections (text_edit)
- **Database References:** segments, correction_ledger

### Q: How is the new content_hash generated on a split, and why mix in the UUID?
- **Verified Answer:** The new right-half segment's `content_hash` is
  `encode(sha256((session_id || split_ms || new_id)::bytea), 'hex')`. The original
  recipe keyed only on `(session_id, split_ms)` could collide with an existing
  segment's `start_ms` and violate the `UNIQUE(session_id, content_hash)` constraint;
  mixing in the to-be-generated UUID makes collisions impossible by construction while
  staying deterministic per row.
- **Supporting Evidence:** [app/services/segment_split.py:108-116](../../app/services/segment_split.py#L108-L116) (rationale),
  [app/services/segment_split.py:147](../../app/services/segment_split.py#L147) (recipe).
- **Source Files:** app/services/segment_split.py
- **API References:** POST /v1/sessions/{id}/corrections (split)
- **Database References:** segments

### Q: How does merge find the right neighbor after a split that duplicated a seq value?
- **Verified Answer:** Migration 022 dropped the `UNIQUE(session_id, seq)` constraint,
  so two segments can share a `seq`. Merge therefore finds the neighbor by row-value
  comparison `(seq, start_ms) > (left_seq, left_start_ms) ORDER BY seq, start_ms
  LIMIT 1`, breaking ties on `start_ms`. The found neighbor must equal the caller's
  `expected_right_segment_id` or the merge returns `409 MERGE_NEIGHBOR_CHANGED`.
- **Supporting Evidence:** [app/services/segment_merge.py:44-66](../../app/services/segment_merge.py#L44-L66).
- **Source Files:** app/services/segment_merge.py
- **API References:** POST /v1/sessions/{id}/corrections (merge)
- **Database References:** segments

### Q: How do edits make it into the exported transcript?
- **Verified Answer:** On a `text_edit` apply, `segments.text` is materialized in the
  same transaction so the export pipeline (which reads `segments.text` directly) sees
  the corrected text. Undo/redo re-materialize all segments to the pointer via a
  single `DISTINCT ON` CTE so exports always match the current pointer state.
- **Supporting Evidence:** [app/api/corrections.py:573-596](../../app/api/corrections.py#L573-L596) (apply-side),
  [app/api/corrections.py:211-245](../../app/api/corrections.py#L211-L245) + [app/api/corrections.py:919-921](../../app/api/corrections.py#L919-L921) (undo/redo).
- **Source Files:** app/api/corrections.py
- **API References:** POST /v1/sessions/{id}/corrections, .../undo, .../redo
- **Database References:** segments, correction_ledger

---

## Source Verification
- **Files Used:** app/api/corrections.py, app/api/audit.py, app/services/segment_split.py, app/services/segment_merge.py, app/services/segment_inverse.py, app/services/db_locks.py, app/config.py, app/auth.py, app/security/roles.py, migrations/029_corrections.sql, migrations/000_fix_corrections_collision.sql, migrations/004_audit.sql, migrations/002_discrepancies.sql, frontend/src/views/AuditView.vue, frontend/src/components/editor/AuditTabInline.vue, frontend/src/components/editor/SegmentText.vue, frontend/src/components/AppHeader.vue, frontend/src/stores/featureFlags.ts, frontend/src/services/api.ts
- **Components Used:** AuditView.vue, AuditTabInline.vue, SegmentText.vue, AppHeader.vue
- **APIs Used:** POST /v1/sessions/{id}/corrections, POST /v1/sessions/{id}/find-replace, GET /v1/sessions/{id}/corrections, POST /v1/sessions/{id}/corrections/undo, POST /v1/sessions/{id}/corrections/redo, GET /v1/sessions/{id}/review-queue, GET /v1/audit, GET /v1/audit/sessions/{id}/corrections
- **Database References:** correction_ledger, ledger_pointers, audit_events, transcription_discrepancies, segments, word_alignment, key_points_annotations, alignments, normalization_results, corrections (legacy), auth_users
- **Permission Logic Used:** JWT presence only (CurrentUser); no admin/role gate in this module
- **Confidence Score:** High — each answer traced to specific verified lines; uncertain/UI-only items excluded from this set.
- **Evidence Links:** [corrections.py:332-1033](../../app/api/corrections.py#L332-L1033), [audit.py:18-83](../../app/api/audit.py#L18-L83), [segment_merge.py:44-88](../../app/services/segment_merge.py#L44-L88), [segment_inverse.py:46-73](../../app/services/segment_inverse.py#L46-L73), [029_corrections.sql:88-152](../../migrations/029_corrections.sql#L88-L152), [config.py:134](../../app/config.py#L134)
