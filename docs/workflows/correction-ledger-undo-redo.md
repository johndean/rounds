# Workflow: Correction Ledger + Undo/Redo

The editor's edits are recorded in an **append-only** correction ledger (`correction_ledger`) with a per-session pointer (`ledger_pointers.current_pointer`). Undo/redo move the pointer; rows are never mutated or deleted. Structural ops (split / merge) additionally replay inverse / forward DB mutations as the pointer moves.

> INVARIANT (from the module docstring): "corrections are APPEND-ONLY. UPDATE / DELETE on corrections is forbidden. Undo/redo moves `correction_pointers.current_pointer`; the rows themselves are never mutated." ([app/api/corrections.py:9](../../app/api/corrections.py#L9))

---

## Trigger

- **Apply correction:** `POST /v1/sessions/{id}/corrections` ([app/api/corrections.py:332](../../app/api/corrections.py#L332)).
- **Undo:** `POST /v1/sessions/{id}/corrections/undo` ([app/api/corrections.py:883](../../app/api/corrections.py#L883)).
- **Redo:** `POST /v1/sessions/{id}/corrections/redo` ([app/api/corrections.py:928](../../app/api/corrections.py#L928)).
- Related (same router): `POST /find-replace`, `GET /corrections`, `GET /review-queue`.

## Inputs

- **Apply** (`CorrectionRequest`): `segment_id`, `correction_type`, plus type-specific fields — `old_text`/`new_text` (text_edit), `old_slide_id`/`new_slide_id` (slide_reassignment), `after_word_index` (split), `expected_right_segment_id` (merge), `expected_content_hash` (optimistic-lock for text_edit), `action_id` (idempotency key).
- Allowed `correction_type` values ([app/api/corrections.py:49](../../app/api/corrections.py#L49)): `slide_reassignment`, `text_edit`, `split`, `merge`, `mark_ok`, `chat_insert`, `chat_edit`, `chat_remove`, `poll_insert`, `poll_remove`, `speaker_reassignment`.
- **Undo / Redo**: `session_id` only (path param); no body.

## Validations

### Apply

- **Type allowlist:** unknown `correction_type` → 400 ([app/api/corrections.py:345](../../app/api/corrections.py#L345)).
- **Existence:** session must exist (404) and segment must belong to the session (404) ([app/api/corrections.py:350](../../app/api/corrections.py#L350)).
- **No-op guard (anti-redo-tail-destruction):** `_is_noop_correction` returns true for a `text_edit` whose `old_text == new_text` or a `slide_reassignment` whose old==new; such requests return `{noop: True}` without appending a ledger row or truncating the redo tail ([app/api/corrections.py:74](../../app/api/corrections.py#L74), handled at [app/api/corrections.py:460](../../app/api/corrections.py#L460)).
- **Optimistic lock (text_edit):** when `expected_content_hash` is supplied, the segment UPDATE is conditional on `content_hash` still matching. On mismatch the autosave is dropped as stale (`{stale: True}`) — no ledger row, no redo-tail truncation, no WS ([app/api/corrections.py:482](../../app/api/corrections.py#L482)).

### Split / merge (gated pre-branch)

- **Feature flag:** split/merge require `SPLIT_MERGE_ENABLED`; otherwise 503 `SPLIT_MERGE_DISABLED` ([app/api/corrections.py:362](../../app/api/corrections.py#L362)). Default is `False` ([app/config.py:134](../../app/config.py#L134)).
- **Concurrency:** serialized on a `(session_id, "split_merge")` advisory lock; if not acquired → 409 `SPLIT_MERGE_BUSY` ([app/api/corrections.py:365](../../app/api/corrections.py#L365)).
- **Idempotency:** inside the lock, a matching `action_id` replays the cached result via `_replay_existing` ([app/api/corrections.py:368](../../app/api/corrections.py#L368)).
- **Split executor checks** ([app/services/segment_split.py:22](../../app/services/segment_split.py#L22)): `SPLIT_INVALID_WORD_INDEX` (null/negative, or `>= n_words-1`); `SPLIT_SEGMENT_NOT_FOUND` (404); `SPLIT_ANCHOR_SEGMENT` (anchor segments cannot split); `SPLIT_NO_WORD_ALIGNMENT` (422, no `word_alignment` rows). Row is `SELECT ... FOR UPDATE` locked.
- **Merge executor checks** ([app/services/segment_merge.py:23](../../app/services/segment_merge.py#L23)): `MERGE_NO_NEIGHBOR` (missing `expected_right_segment_id` or no right neighbor); `MERGE_LEFT_NOT_FOUND` (404); `MERGE_ANCHOR_SEGMENT` / `MERGE_ANCHOR_NEIGHBOR`; `MERGE_NEIGHBOR_CHANGED` (409, actual neighbor ≠ expected); `MERGE_SPEAKER_MISMATCH` (left/right speaker differ). Both rows `FOR UPDATE` locked.

### Undo / Redo

- **Undo bounds:** if `current_pointer < 0`, returns `{action: "nothing_to_undo"}` ([app/api/corrections.py:887](../../app/api/corrections.py#L887)).
- **Redo bounds:** if `current_pointer >= MAX(sequence_number)`, returns `{action: "nothing_to_redo"}` ([app/api/corrections.py:940](../../app/api/corrections.py#L940)).
- Both hold the `(session_id, "split_merge")` advisory lock; failure to acquire → 409 `SPLIT_MERGE_BUSY` ([app/api/corrections.py:897](../../app/api/corrections.py#L897), [app/api/corrections.py:947](../../app/api/corrections.py#L947)).

## Approvals

None. Corrections, undo, and redo are applied directly by any authenticated user.

## Notifications

WebSocket via `_emit_ws(sid, {...})`:

- `correction_applied` after a successful apply (with `action_id`, `segment_ids`, `correction_type`) — both the split/merge branch ([app/api/corrections.py:438](../../app/api/corrections.py#L438)) and the standard branch ([app/api/corrections.py:624](../../app/api/corrections.py#L624)).
- `discrepancy_resolved` when a `text_edit`/`mark_ok` auto-closes a discrepancy ([app/api/corrections.py:631](../../app/api/corrections.py#L631)).
- `correction_applied` with `action_id: "undo"` / `"redo"` on pointer moves ([app/api/corrections.py:923](../../app/api/corrections.py#L923), [app/api/corrections.py:973](../../app/api/corrections.py#L973)).

No email notifications.

## Outputs

### Apply

- One `correction_ledger` row at `sequence_number = next_seq`, with `ledger_pointers.current_pointer` advanced to it ([app/api/corrections.py:533](../../app/api/corrections.py#L533), [app/api/corrections.py:565](../../app/api/corrections.py#L565)). The redo tail (rows after the current pointer) is truncated first via `_truncate_redo_tail` ([app/api/corrections.py:527](../../app/api/corrections.py#L527)).
- **text_edit** also materializes into `segments.text` in the same transaction (conditional path when `expected_content_hash` set; unconditional legacy path otherwise) so exports read current text without ledger replay ([app/api/corrections.py:488](../../app/api/corrections.py#L488), [app/api/corrections.py:584](../../app/api/corrections.py#L584)).
- **split/merge** store the `invert_payload` JSON in `correction_ledger.new_text` (the column doubles as the structural-op payload carrier) ([app/api/corrections.py:399](../../app/api/corrections.py#L399)). `execute_split` mutates `segments` (UPDATE left half + INSERT right half + shift later `seq`) and reparents `word_alignment` rows; `execute_merge` mutates `segments` (UPDATE left, DELETE right) and reparents `word_alignment` + `key_points_annotations`.
- **text_edit / mark_ok** (BR-018) resolve a matching unresolved `transcription_discrepancies` row, setting `resolved`, `resolution_correction_id`, `resolved_at` ([app/api/corrections.py:602](../../app/api/corrections.py#L602)).

### Undo / Redo

- `ledger_pointers.current_pointer` updated (`-1` for undo, `+1` for redo) ([app/api/corrections.py:912](../../app/api/corrections.py#L912), [app/api/corrections.py:962](../../app/api/corrections.py#L962)).
- For any split/merge rows crossed, the structural DB mutation is inverted (undo) or re-applied (redo) via `segment_inverse`:
  - **Undo** walks crossed split/merge rows newest-to-oldest (`ORDER BY sequence_number DESC`) and calls `apply_inverse_for_correction` ([app/api/corrections.py:900](../../app/api/corrections.py#L900)).
  - **Redo** walks them oldest-first (`ORDER BY sequence_number ASC`) and calls `apply_forward_for_correction` ([app/api/corrections.py:950](../../app/api/corrections.py#L950)).
  - `apply_inverse_for_correction` dispatches `split_invert → segment_split.invert_split`, `merge_invert → segment_merge.invert_merge` ([app/services/segment_inverse.py:46](../../app/services/segment_inverse.py#L46)).
  - `apply_forward_for_correction` dispatches to local `_redo_split` / `_redo_merge`, which replay the original mutation from the saved payload **without** re-calling the executor (to avoid re-validating against a now-mutated DB and writing a fresh ledger row) ([app/services/segment_inverse.py:61](../../app/services/segment_inverse.py#L61), rationale at [app/services/segment_inverse.py:5](../../app/services/segment_inverse.py#L5)).
- After the pointer moves, `_materialize_segments_for_session(..., up_to_pointer=new_ptr)` re-syncs `segments.text` so downstream exports reflect the post-undo/redo state ([app/api/corrections.py:921](../../app/api/corrections.py#L921), [app/api/corrections.py:971](../../app/api/corrections.py#L971)).

### Inverse / forward mutation detail (segment_inverse.py)

- **invert_split** (undo a split): restore original `segments.text` + `end_ms`; move right-half `word_alignment` rows back to the original (shift `gemini_idx` by remaining left-count); delete cloned `key_points_annotations`; delete the new right segment ([app/services/segment_inverse.py:46](../../app/services/segment_inverse.py#L46) → `segment_split.invert_split` at [app/services/segment_split.py:219](../../app/services/segment_split.py#L219)).
- **_redo_split** (redo a split): recompute `text_a`/`text_b` from saved pre-split text; UPDATE original to left half; shift later `seq` by 1; re-INSERT the right segment under the saved `new_segment_id` with a UUID-mixed `content_hash`; reparent `word_alignment` by `split_at_word_index + 1`; re-clone `key_points_annotations` if originally cloned ([app/services/segment_inverse.py:76](../../app/services/segment_inverse.py#L76)).
- **invert_merge / _redo_merge** mirror this for merge: undo re-inserts the right segment and rolls back left; redo re-applies the UPDATE-left + reparent `word_alignment` + DELETE-right ([app/services/segment_inverse.py:167](../../app/services/segment_inverse.py#L167)).

## Status Changes

None at the `sessions.status` level — applying/undoing/redoing a correction does not transition the session lifecycle. The only "status" mutated is `ledger_pointers.current_pointer` and (for the discrepancy auto-close) `transcription_discrepancies.resolved`.

## Audit Events

- The `correction_ledger` rows ARE the audit trail for editor edits (append-only, with `applied_by`, `applied_at`, `action_id`, `sequence_number`).
- No `audit_events` table rows are written by `apply_correction`, `undo_correction`, or `redo_correction` in the listed code. (A `merge.slide_mismatch` `audit_events` row is written inside the merge executor on cross-slide merges — [app/services/segment_merge.py:76](../../app/services/segment_merge.py#L76).)

## Exception Handling

- **Split/merge dispatch wrapper:** the executor + ledger write are wrapped; `HTTPException` (4xx) propagates unchanged, any other exception is logged with full traceback (`_log.exception`), the transaction is rolled back, and a structured 500 `SPLIT_MERGE_EXEC_ERROR` (with `operation`, `error_class`, `error_message`) is returned ([app/api/corrections.py:417](../../app/api/corrections.py#L417)).
- **Stale autosave:** content_hash mismatch is treated as best-effort no-op (logged warning, `{stale: True}`, transaction committed clean) ([app/api/corrections.py:506](../../app/api/corrections.py#L506)).
- **Concurrency:** 409 `SPLIT_MERGE_BUSY` is returned when the advisory lock can't be acquired (apply, undo, redo).
- Undo/redo at the ends of the ledger return informational payloads (`nothing_to_undo` / `nothing_to_redo`) rather than errors.

### Feature flag

- `SPLIT_MERGE_ENABLED` — default `False` ([app/config.py:134](../../app/config.py#L134)). While off, `text_edit`, `slide_reassignment`, `speaker_reassignment`, `mark_ok`, chat_*, and poll_* corrections still work; only `split` and `merge` apply paths are blocked with 503. Undo/redo still acquire the `split_merge` lock regardless of the flag, but only act on split/merge rows that exist in the ledger.

---

## Source Verification
- **Files Used:** app/api/corrections.py (create 332, undo 883, redo 928, no-op guard 74, allowlist 49), app/services/segment_inverse.py, app/services/segment_split.py (execute_split 22, invert_split 219), app/services/segment_merge.py (execute_merge 23), app/config.py
- **Components Used:** none (backend; editor Undo/Redo UI referenced in docstring but frontend not read for this workflow)
- **APIs Used:** POST `/v1/sessions/{id}/corrections`, POST `/v1/sessions/{id}/corrections/undo`, POST `/v1/sessions/{id}/corrections/redo`, POST `/v1/sessions/{id}/find-replace`, GET `/v1/sessions/{id}/corrections`, GET `/v1/sessions/{id}/review-queue`
- **Database Tables Used:** correction_ledger, ledger_pointers, segments, word_alignment, key_points_annotations, transcription_discrepancies, audit_events (merge.slide_mismatch only)
- **Permission Logic Used:** JWT presence via `CurrentUser` / `_u: CurrentUser` dependency on every route. No role tiers and no `johndean@vin.com` gate in these handlers.
- **Confidence Score:** High — apply/undo/redo control flow, validations, and inverse/forward dispatch all verified against source lines.
- **Evidence Links:** [app/api/corrections.py:332](../../app/api/corrections.py#L332), [app/api/corrections.py:883](../../app/api/corrections.py#L883), [app/api/corrections.py:928](../../app/api/corrections.py#L928), [app/services/segment_inverse.py:46](../../app/services/segment_inverse.py#L46), [app/config.py:134](../../app/config.py#L134)
