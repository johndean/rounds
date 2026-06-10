# Corrections & Audit — Product Spec

> Module key: `corrections-audit`. Scope: the append-only correction ledger that
> backs the editor's edit / split / merge / find-replace / undo-redo flows, and
> the audit surfaces (per-session Word Track Changes + global system event feed)
> that render those records.

## Overview

Corrections & Audit is the system of record for **what changed in a transcript and
who changed it**. Every edit an operator makes in the editor — a text edit, a
slide reassignment, a segment split or merge, a bulk find/replace — is written as
an immutable row in a ledger. The ledger is **append-only**: rows are never updated
or deleted in place. Undo and redo move a per-session pointer rather than mutating
history.

Two distinct tables and two distinct UI surfaces exist:

1. **Per-session correction ledger** (`correction_ledger` + `ledger_pointers`) —
   the Phase 4 MIC-parity ledger written by [app/api/corrections.py](../../app/api/corrections.py).
   Surfaced as "Word Track Changes" at `#/e/:id/audit` and inside the editor's
   Audit tab.
2. **Global audit event log** (`audit_events`) — a system-wide activity feed
   written by many subsystems (SOP transitions, settings changes, improvements,
   alignment gates, merge slide-mismatch warnings). Surfaced at `#/audit`.

Both surfaces are read through the same `AuditLedger.vue` component, which adapts
either feed into a common row shape.

## Purpose

- Provide a tamper-evident, append-only history of every transcript correction so
  reviewers and operators can see the full lineage of any segment.
- Power editor Undo/Redo by moving a single integer pointer over the ledger
  instead of mutating segment text destructively.
- Auto-close transcription discrepancies when an operator fixes them inline,
  removing a separate "resolve" step ([app/api/corrections.py:601-620](../../app/api/corrections.py#L601-L620)).
- Order the reviewer's work via a confidence-priority "review queue" so the worst
  alignment problems surface first ([app/api/corrections.py:978-1033](../../app/api/corrections.py#L978-L1033)).
- Give operators a system-wide event feed for non-segment activity (SOP deadlines,
  settings, improvements) via `audit_events`.

## User Value

- **Reviewers** can replay the edit history of a session and jump from any
  correction row back to the segment in the editor.
- **Operators** get a single confidence-priority queue of alignment rows that need
  attention rather than scanning the whole transcript.
- **Editors** get Undo/Redo that is correct across structural edits (split/merge)
  because undo/redo replay structural inverses, not just text rollbacks.
- **Anyone** can export the per-session ledger as JSONL or CSV, and the global feed
  as JSONL, directly from the browser.

## Navigation

| Hash route | View | Source |
|---|---|---|
| `#/audit` | Global system audit log | [frontend/src/router/index.ts:41](../../frontend/src/router/index.ts#L41) → `AuditView.vue` |
| `#/e/:id/audit` | Per-session Word Track Changes | [frontend/src/router/index.ts:36](../../frontend/src/router/index.ts#L36) → `EditorAuditView.vue` → `AuditView.vue` |
| Editor Audit tab | Decisions / Ledger toggle inside the editor | `AuditTabInline.vue` (linked to full WTC via `#/e/:id/audit`) |

`EditorAuditView.vue` is a thin wrapper that passes the `id` prop into `AuditView.vue`
([frontend/src/views/EditorAuditView.vue:7-14](../../frontend/src/views/EditorAuditView.vue#L7-L14)).
`AuditView.vue` decides global-vs-session mode purely on whether the `id` prop is
present ([frontend/src/views/AuditView.vue:46](../../frontend/src/views/AuditView.vue#L46)).

There is no global navigation entry verified in the assigned source; routes are
reached by hash URL and from the editor's "Full WTC" link
([frontend/src/components/editor/AuditTabInline.vue:88-90](../../frontend/src/components/editor/AuditTabInline.vue#L88-L90)).

## Screens

### 1. Word Track Changes (per-session) — `#/e/:id/audit`

`AuditView.vue` in session mode ([frontend/src/views/AuditView.vue:55-62](../../frontend/src/views/AuditView.vue#L55-L62)):

- Breadcrumb: Sessions / `{session.code || id}` / "Audit · Word Track Changes (v7)".
- KPI row: Total Corrections; "Text Edits (dirty)" count (`stats.text_edit`);
  "Non-dirty Corrections" (total minus text_edit); Distinct Actors.
- Filter chips for a fixed correction-type set: `all`, `text_edit`, `chat_insert`,
  `chat_edit`, `poll_insert`, `slide_reassignment`, `speaker_reassignment`,
  `mark_reviewed`, `annotation_add` ([frontend/src/views/AuditView.vue:99-110](../../frontend/src/views/AuditView.vue#L99-L110)).
- "Export JSONL" button (`data-test-id="audit-wtc-export-jsonl"`).
- `AuditLedger.vue` table: Time (UTC) / Type / Segment / Actor / Delta / Note.
- An informational card: "L1 — has_user_override Invariant" listing all 12 type
  labels and which flips `has_user_override` (only `text_edit`)
  ([frontend/src/views/AuditView.vue:223-248](../../frontend/src/views/AuditView.vue#L223-L248)).

  > NOT VERIFIED IN CODE: the "11/11 types pass" chip and "has_user_override
  > invariant" copy are static descriptive text in the Vue template; no
  > `has_user_override` column or snapshot test is referenced from the assigned
  > corrections/audit source files.

### 2. Global System Audit Log — `#/audit`

`AuditView.vue` in global mode ([frontend/src/views/AuditView.vue:63-80](../../frontend/src/views/AuditView.vue#L63-L80)):

- Eyebrow: "System audit · audit_events".
- KPI row: Total Events; Distinct Kinds; "SOP Deadline Warnings"
  (`stats['sop.deadline_warning']`); Distinct Actors.
- Filter chips derived dynamically from the `kind` values actually present in the
  data ([frontend/src/views/AuditView.vue:112-118](../../frontend/src/views/AuditView.vue#L112-L118)).
- `audit_events` rows are adapted into the `Correction` shape: `seg` becomes the
  first 8 chars of `session_id`, `note` becomes the event `summary`, `type` becomes
  `kind` ([frontend/src/views/AuditView.vue:70-79](../../frontend/src/views/AuditView.vue#L70-L79)).
- "Export JSONL" produces `audit-events.jsonl`.

### 3. Editor Audit Tab (inline) — `AuditTabInline.vue`

- Toggle between "Decisions" (card view, default) and "Ledger" (table view)
  ([frontend/src/components/editor/AuditTabInline.vue:75-86](../../frontend/src/components/editor/AuditTabInline.vue#L75-L86)).
- Decisions view filters corrections to a "decision" subset:
  `text_edit, chat_insert, chat_edit, chat_remove, slide_reassignment,
  speaker_reassignment, annotation_add, mark_ok`
  ([frontend/src/components/editor/AuditTabInline.vue:45-46](../../frontend/src/components/editor/AuditTabInline.vue#L45-L46)).
- Each decision renders as a `DecisionCard.vue` WAS/NOW two-panel card; for
  `text_edit`/`chat_edit` it computes a token-level word diff for inline
  strikethrough/highlight ([frontend/src/components/editor/DecisionCard.vue:54-94](../../frontend/src/components/editor/DecisionCard.vue#L54-L94)).
- "Full WTC" link to `#/e/:id/audit`; "Export" produces `audit.csv`.

  > NOT VERIFIED IN CODE: the flag counters in the toolbar ("Drift (0)",
  > "Uncertain (0)", "Low conf (0)") are hardcoded `0` in the template
  > ([frontend/src/components/editor/AuditTabInline.vue:71-73](../../frontend/src/components/editor/AuditTabInline.vue#L71-L73)).

## User Flows

### Apply a single correction
1. Editor posts to `POST /v1/sessions/{id}/corrections` with `segment_id`,
   `correction_type`, and type-specific fields.
2. Backend validates the type, that the session exists, and that the segment
   belongs to the session ([app/api/corrections.py:345-353](../../app/api/corrections.py#L345-L353)).
3. No-op corrections (text/slide unchanged) return early with `noop: true` and do
   not advance the pointer or truncate the redo tail
   ([app/api/corrections.py:460-469](../../app/api/corrections.py#L460-L469)).
4. The redo tail is truncated, a ledger row is appended at the next
   `sequence_number`, and the pointer is advanced to it
   ([app/api/corrections.py:527-571](../../app/api/corrections.py#L527-L571)).
5. For `text_edit` the segment's canonical `segments.text` is materialized in the
   same transaction ([app/api/corrections.py:584-596](../../app/api/corrections.py#L584-L596)).
6. A `correction_applied` WS event is emitted ([app/api/corrections.py:624-629](../../app/api/corrections.py#L624-L629)).

### Find / Replace (bulk)
1. Editor posts `POST /v1/sessions/{id}/find-replace` with `find`, `replace`,
   `case_sensitive`, `dry_run`.
2. Effective per-segment text is computed as `(latest text_edit ≤ pointer) ||
   normalized_text || segments.text` ([app/api/corrections.py:660-726](../../app/api/corrections.py#L660-L726)).
3. `dry_run=true` (or no matches) returns the preview with `applied: false`
   ([app/api/corrections.py:742-754](../../app/api/corrections.py#L742-L754)).
4. On apply, one `text_edit` ledger row is written per matched segment, all sharing
   a single `action_id` so undo reverses them as one batch
   ([app/api/corrections.py:759-799](../../app/api/corrections.py#L759-L799)).

### Split a segment
1. Editor right-click or Ctrl/Cmd+Shift+S calls `splitSegment(...)` →
   `POST /v1/sessions/{id}/corrections` with `correction_type: "split"` and
   `after_word_index` ([frontend/src/services/api.ts:564-581](../../frontend/src/services/api.ts#L564-L581)).
2. Gated by `SPLIT_MERGE_ENABLED`; disabled → `503 SPLIT_MERGE_DISABLED`
   ([app/api/corrections.py:360-363](../../app/api/corrections.py#L360-L363)).
3. Acquired under a `split_merge` advisory lock; contention → `409 SPLIT_MERGE_BUSY`
   ([app/api/corrections.py:365-367](../../app/api/corrections.py#L365-L367)).
4. `execute_split` splits the `segments` row in two at the word boundary, reparents
   `word_alignment`, clones `key_points_annotations`, and returns an invert payload
   ([app/services/segment_split.py:22-216](../../app/services/segment_split.py#L22-L216)).
5. A `split` ledger row is written carrying the invert payload (JSON) in `new_text`
   ([app/api/corrections.py:397-411](../../app/api/corrections.py#L397-L411)).

### Merge two segments
1. Editor calls `mergeSegment(...)` with the left `segment_id` and the
   `expected_right_segment_id` ([frontend/src/services/api.ts:582-599](../../frontend/src/services/api.ts#L582-L599)).
2. `execute_merge` locks left, finds the right neighbor by `(seq, start_ms)`,
   validates it matches the expected id and same speaker, then collapses right into
   left and DELETEs right ([app/services/segment_merge.py:23-279](../../app/services/segment_merge.py#L23-L279)).

### Undo / Redo
1. `POST /v1/sessions/{id}/corrections/undo` decrements the pointer; structural
   ops between the old and new pointer are inverted newest-first under the
   `split_merge` lock, then `segments.text` is re-materialized
   ([app/api/corrections.py:883-924](../../app/api/corrections.py#L883-L924)).
2. `POST /v1/sessions/{id}/corrections/redo` increments the pointer; structural ops
   are re-applied oldest-first ([app/api/corrections.py:928-974](../../app/api/corrections.py#L928-L974)).

### Review queue
1. `GET /v1/sessions/{id}/review-queue` returns `alignments` rows in `uncertain` or
   `review` status, sorted by a fixed priority score
   ([app/api/corrections.py:978-1033](../../app/api/corrections.py#L978-L1033)).

## Business Rules

- **Append-only ledger.** `correction_ledger` rows are never UPDATEd or DELETEd in
  place except for redo-tail truncation; undo/redo move `ledger_pointers.current_pointer`
  ([app/api/corrections.py:9-11](../../app/api/corrections.py#L9-L11)).
- **Redo-tail abandonment.** Recording any new correction deletes ledger rows with
  `sequence_number > current_pointer` ([app/api/corrections.py:188-198](../../app/api/corrections.py#L188-L198)).
- **Discrepancy auto-close (BR-018).** Only `text_edit` and `mark_ok` close an
  unresolved `transcription_discrepancies` row for the segment; other types do not
  ([app/api/corrections.py:55-63](../../app/api/corrections.py#L55-L63), [app/api/corrections.py:601-620](../../app/api/corrections.py#L601-L620)).
- **Allowed correction types.** Exactly 11 types are accepted: `slide_reassignment,
  text_edit, split, merge, mark_ok, chat_insert, chat_edit, chat_remove,
  poll_insert, poll_remove, speaker_reassignment`
  ([app/api/corrections.py:49-53](../../app/api/corrections.py#L49-L53)); enforced again by the DB CHECK
  constraint ([migrations/029_corrections.sql:109-122](../../migrations/029_corrections.sql#L109-L122)).
- **Find/replace batching.** One shared `action_id` across all per-segment
  `text_edit` rows so undo reverses the whole replace as a unit
  ([app/api/corrections.py:759-761](../../app/api/corrections.py#L759-L761)).
- **Merge requires same speaker.** Merge across a speaker boundary is rejected with
  `400 MERGE_SPEAKER_MISMATCH` ([app/services/segment_merge.py:67-68](../../app/services/segment_merge.py#L67-L68)).
- **Merge across a slide boundary** is allowed but logs a `merge.slide_mismatch`
  `audit_events` row (left's slide wins) ([app/services/segment_merge.py:74-88](../../app/services/segment_merge.py#L74-L88)).
- **Anchor segments cannot be split or merged**
  ([app/services/segment_split.py:44-45](../../app/services/segment_split.py#L44-L45),
  [app/services/segment_merge.py:41-42](../../app/services/segment_merge.py#L41-L42), [app/services/segment_merge.py:69-70](../../app/services/segment_merge.py#L69-L70)).
- **Review-queue priority scoring (BR-006).** Drift + no slide = +100; uncertain +
  no slide = +90; confidence < 0.4 = +70; drift = +50; status `review` = +40;
  confidence < 0.6 = +20 (bonuses stack) ([app/api/corrections.py:1005-1013](../../app/api/corrections.py#L1005-L1013)).
- **Key-points merge cap.** On merge, merged `key_points` are deduped and capped at
  5; left's explanation wins; `extraction_confidence` is the max of both
  ([app/services/segment_merge.py:208-230](../../app/services/segment_merge.py#L208-L230)).

## Validation Rules

- `correction_type` must be in the allowed set or `400` ([app/api/corrections.py:345-346](../../app/api/corrections.py#L345-L346)).
- Session must exist (`404`) and segment must belong to it (`404`)
  ([app/api/corrections.py:350-353](../../app/api/corrections.py#L350-L353)).
- Find/Replace: `find` is `min_length=1, max_length=512`; `replace` is
  `max_length=512` ([app/api/corrections.py:115-119](../../app/api/corrections.py#L115-L119)).
- Split: `after_word_index` must be present, non-negative, and strictly less than
  `n_words - 1` (else `400 SPLIT_INVALID_WORD_INDEX`)
  ([app/services/segment_split.py:25-29](../../app/services/segment_split.py#L25-L29), [app/services/segment_split.py:58-59](../../app/services/segment_split.py#L58-L59)).
- Split: the segment must have `word_alignment` rows or `422 SPLIT_NO_WORD_ALIGNMENT`
  ([app/services/segment_split.py:54-55](../../app/services/segment_split.py#L54-L55)).
- Merge: `expected_right_segment_id` required (`400 MERGE_NO_NEIGHBOR`); the actual
  right neighbor must equal it (`409 MERGE_NEIGHBOR_CHANGED`)
  ([app/services/segment_merge.py:26-27](../../app/services/segment_merge.py#L26-L27), [app/services/segment_merge.py:65-66](../../app/services/segment_merge.py#L65-L66)).
- Optional `expected_content_hash` on a `text_edit`: if the segment's
  `content_hash` no longer matches, the autosave is dropped as stale (returns
  `stale: true`, no ledger row) ([app/api/corrections.py:482-525](../../app/api/corrections.py#L482-L525)).

## States

- **Ledger pointer (`current_pointer`)**: `-1` = empty / before first correction;
  otherwise the `sequence_number` of the currently-active tip
  ([migrations/029_corrections.sql:132-136](../../migrations/029_corrections.sql#L132-L136)).
- **Correction `active` flag** (list response): a row is `active` when its
  `sequence_number <= current_pointer` ([app/api/corrections.py:875](../../app/api/corrections.py#L875)).
- **Undo at floor**: pointer `< 0` returns `action: "nothing_to_undo"`
  ([app/api/corrections.py:887-888](../../app/api/corrections.py#L887-L888)).
- **Redo at ceiling**: pointer `>= max sequence_number` returns
  `action: "nothing_to_redo"` ([app/api/corrections.py:940-941](../../app/api/corrections.py#L940-L941)).
- **Discrepancy resolution state**: `transcription_discrepancies.resolved`
  (+ `resolved_at`, `resolution_correction_id`) flips when a closing correction is
  applied ([migrations/029_corrections.sql:143-149](../../migrations/029_corrections.sql#L143-L149)).
- **Feature-flag state**: `SPLIT_MERGE_ENABLED` (default `False`) controls whether
  split/merge are executable ([app/config.py:134](../../app/config.py#L134)).

## Dependencies

- **`segments`** table — the canonical transcript rows that corrections mutate
  (text, end_ms, seq, content_hash).
- **`word_alignment`** — reparented on split/merge.
- **`key_points_annotations`** — cloned (split) / merged (merge).
- **`alignments`** — read by the review queue.
- **`transcription_discrepancies`** — auto-closed by `text_edit`/`mark_ok`.
- **`slides`** — referenced by `old_slide_id`/`new_slide_id` FKs.
- **WS bridge** (`app/engines/ws_bridge.publish_ws_event_sync`) — best-effort
  `correction_applied` / `discrepancy_resolved` events
  ([app/api/corrections.py:123-129](../../app/api/corrections.py#L123-L129)).
- **Advisory locks** (`app/services/db_locks.try_advisory_lock_async`) — serializes
  split/merge/undo/redo per session.
- **`app/engines/diff.py`** — LCS word diff used by ingest (`lcs_discrepancies_task`)
  to populate discrepancies/word alignment that this module later resolves.

## Error Handling

| Condition | Status | Code / detail | Source |
|---|---|---|---|
| Unknown correction_type | 400 | `Invalid correction_type: ...` | [corrections.py:345-346](../../app/api/corrections.py#L345-L346) |
| Session not found | 404 | `Session {id} not found` | [corrections.py:350-351](../../app/api/corrections.py#L350-L351) |
| Segment not in session | 404 | `Segment {id} not in session ...` | [corrections.py:352-353](../../app/api/corrections.py#L352-L353) |
| Split/merge disabled | 503 | `SPLIT_MERGE_DISABLED` | [corrections.py:362-363](../../app/api/corrections.py#L362-L363) |
| Split/merge lock busy | 409 | `SPLIT_MERGE_BUSY` | [corrections.py:366-367](../../app/api/corrections.py#L366-L367) |
| Split invalid word index | 400 | `SPLIT_INVALID_WORD_INDEX` | [segment_split.py:26-29](../../app/services/segment_split.py#L26-L29) |
| Split: no word alignment | 422 | `SPLIT_NO_WORD_ALIGNMENT` | [segment_split.py:54-55](../../app/services/segment_split.py#L54-L55) |
| Split: anchor segment | 400 | `SPLIT_ANCHOR_SEGMENT` | [segment_split.py:44-45](../../app/services/segment_split.py#L44-L45) |
| Merge: missing/absent neighbor | 400 | `MERGE_NO_NEIGHBOR` | [segment_merge.py:26-27](../../app/services/segment_merge.py#L26-L27), [segment_merge.py:63-64](../../app/services/segment_merge.py#L63-L64) |
| Merge: neighbor changed | 409 | `MERGE_NEIGHBOR_CHANGED` | [segment_merge.py:65-66](../../app/services/segment_merge.py#L65-L66) |
| Merge: speaker mismatch | 400 | `MERGE_SPEAKER_MISMATCH` | [segment_merge.py:67-68](../../app/services/segment_merge.py#L67-L68) |
| Merge: anchor (either side) | 400 | `MERGE_ANCHOR_SEGMENT` / `MERGE_ANCHOR_NEIGHBOR` | [segment_merge.py:41-42](../../app/services/segment_merge.py#L41-L42), [segment_merge.py:69-70](../../app/services/segment_merge.py#L69-L70) |
| Unhandled exec error | 500 | `SPLIT_MERGE_EXEC_ERROR` (with error_class/message) | [corrections.py:429-437](../../app/api/corrections.py#L429-L437) |

The frontend `SegmentText.vue` maps these: `409 SPLIT_MERGE_BUSY` retries once
after 1s; `409 MERGE_NEIGHBOR_CHANGED` triggers a reload; `503 SPLIT_MERGE_DISABLED`
shows a warning toast ([frontend/src/components/editor/SegmentText.vue:314-333](../../frontend/src/components/editor/SegmentText.vue#L314-L333)).

## Permissions

All Corrections & Audit endpoints require **only a valid JWT** (`CurrentUser` /
`_u: CurrentUser`). There is **no role check and no admin-email gate** in
[app/api/corrections.py](../../app/api/corrections.py) or [app/api/audit.py](../../app/api/audit.py) — verified by grep
finding zero `require_admin` / `is_admin` / `LEGACY_ADMIN_EMAIL` references in
either file.

Role-based authorization is **scaffold-only** repo-wide: `app/security/roles.py`
exists but is documented as "not yet wired into any endpoint", and
`auth_users.role` (migration 045) is not read by `get_current_user`
([app/security/roles.py:10-19](../../app/security/roles.py#L10-L19), [app/auth.py:172-205](../../app/auth.py#L172-L205)).

The only audit-adjacent permission gate is **client-side**: the `#/admin/help`
route guard checks `auth.email === 'johndean@vin.com'`
([frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)) — but that guards the Help
editor, not any Corrections & Audit screen.

## Reporting Impacts

- **Per-session JSONL export** — `AuditView.vue` serializes the current
  corrections array to newline-delimited JSON (`audit.jsonl`)
  ([frontend/src/views/AuditView.vue:125-137](../../frontend/src/views/AuditView.vue#L125-L137)).
- **Global JSONL export** — same path, file named `audit-events.jsonl`.
- **Editor CSV export** — `AuditTabInline.vue` emits `t,actor,type,note` rows
  (`audit.csv`) ([frontend/src/components/editor/AuditTabInline.vue:48-60](../../frontend/src/components/editor/AuditTabInline.vue#L48-L60)).
- **Export pipeline coupling** — `text_edit` corrections are materialized into
  `segments.text` so downstream export reads the corrected text directly
  ([app/api/corrections.py:573-596](../../app/api/corrections.py#L573-L596)). Undo/redo re-materialize so exports
  always reflect the current pointer ([app/api/corrections.py:919-921](../../app/api/corrections.py#L919-L921)).

All exports are generated client-side from already-loaded data; there is no
server-side report endpoint for corrections/audit in the assigned source.

## Audit Requirements

- **Immutability**: the ledger is append-only by design and stated invariant
  ([app/api/corrections.py:9-11](../../app/api/corrections.py#L9-L11)); the DB has no UPDATE/DELETE triggers
  enforcing this — the invariant is enforced by application code only.

  > PARTIALLY IMPLEMENTED: redo-tail truncation does physically DELETE rows past
  > the pointer ([app/api/corrections.py:192-198](../../app/api/corrections.py#L192-L198)), so "never deleted" holds
  > only for rows at-or-before the pointer.
- **Actor attribution**: every ledger row records `applied_by` = the JWT user's
  email, defaulting to `"(unknown)"` ([app/api/corrections.py:531](../../app/api/corrections.py#L531)); every
  `audit_events` row records `actor_email`.
- **Timestamps**: `applied_at` (ledger) and `occurred_at` (events) default to
  `now()` ([migrations/029_corrections.sql:98](../../migrations/029_corrections.sql#L98),
  [migrations/004_audit.sql:10](../../migrations/004_audit.sql#L10)).
- **Resolution back-reference**: a closed discrepancy stores the
  `resolution_correction_id` pointing at the closing ledger row
  ([app/api/corrections.py:609-610](../../app/api/corrections.py#L609-L610)).
- **Global filterability**: `GET /v1/audit` supports filtering by `session_id`,
  `actor`, and `kind` with `limit`/`offset` paging ([app/api/audit.py:18-42](../../app/api/audit.py#L18-L42)).

## Data Relationships

```
sessions ──1:N── correction_ledger ──N:1── segments
   │                     │  (action_id groups a batch)
   │                     └── old_slide_id / new_slide_id ──> slides
   │
   ├──1:1── ledger_pointers (current_pointer)
   │
   └──1:N── audit_events (session_id NULLable for non-session events)

transcription_discrepancies ──resolution_correction_id──> correction_ledger
segments ──1:N── word_alignment        (reparented on split/merge)
segments ──1:1── key_points_annotations (cloned on split, merged on merge)
sessions ──1:N── alignments             (read by review-queue)
```

- `correction_ledger.session_id` and `.segment_id` are `ON DELETE CASCADE`;
  `old/new_slide_id` are `ON DELETE SET NULL` ([migrations/029_corrections.sql:88-101](../../migrations/029_corrections.sql#L88-L101)).
- `ledger_pointers.session_id` is the PK and CASCADEs on session delete
  ([migrations/029_corrections.sql:132-136](../../migrations/029_corrections.sql#L132-L136)).
- `audit_events.session_id` is `ON DELETE SET NULL` ([migrations/004_audit.sql:5](../../migrations/004_audit.sql#L5)).

There is also a **legacy** `corrections` table (migration 002) with a different
schema (`actor_email/kind/was/now_/occurred_at`) that the Phase 4 ledger replaced;
`audit.py` reads from `correction_ledger`, not the legacy table
([app/api/audit.py:45-53](../../app/api/audit.py#L45-L53), [migrations/002_discrepancies.sql:26-39](../../migrations/002_discrepancies.sql#L26-L39)).

## Known Constraints

- **Split/merge default-off**: `SPLIT_MERGE_ENABLED=False` by default; structural
  edits require flipping the flag in both `api` and `worker` env
  ([app/config.py:125-134](../../app/config.py#L125-L134)).
- **Autosave stale-drop requires opt-in**: `expected_content_hash` is optional and
  the editor autosave is noted as not yet sending it ([app/api/corrections.py:110-112](../../app/api/corrections.py#L110-L112)).
- **Materialization only for `text_edit`**: other types write their canonical
  columns through their own endpoints; only `text_edit` is materialized here
  ([app/api/corrections.py:577-596](../../app/api/corrections.py#L577-L596)).
- **Type label mismatch**: the UI filter chips and `AuditLedger` type map include
  labels not in the backend's allowed set (e.g. `mark_reviewed`, `annotation_add`,
  `annotation_remove`, `unmark_reviewed`) — these are UI-only labels with no backend
  correction-type counterpart ([frontend/src/components/audit/AuditLedger.vue:26-39](../../frontend/src/components/audit/AuditLedger.vue#L26-L39) vs
  [app/api/corrections.py:49-53](../../app/api/corrections.py#L49-L53)).
- **Token/alignment drift**: if tokenized text count differs from `word_alignment`
  count, split proceeds using the smaller count as a soft guard
  ([app/services/segment_split.py:78-83](../../app/services/segment_split.py#L78-L83)).
- **Editor inline editing is fixture-driven for some surfaces** per the module
  docstring's "Phase 4b" note ([app/api/corrections.py:20-23](../../app/api/corrections.py#L20-L23)); `AuditTabInline.vue`
  imports a `Segment` type from `@/fixtures/transcript`
  ([frontend/src/components/editor/AuditTabInline.vue:12](../../frontend/src/components/editor/AuditTabInline.vue#L12)).

## Source Verification
- **Files Used:** app/api/corrections.py, app/api/audit.py, app/services/segment_split.py, app/services/segment_merge.py, app/services/segment_inverse.py, app/services/db_locks.py, app/engines/diff.py, app/config.py, app/auth.py, app/security/roles.py, migrations/029_corrections.sql, migrations/000_fix_corrections_collision.sql, migrations/004_audit.sql, migrations/002_discrepancies.sql, frontend/src/views/AuditView.vue, frontend/src/views/EditorAuditView.vue, frontend/src/components/audit/AuditLedger.vue, frontend/src/components/editor/AuditTabInline.vue, frontend/src/components/editor/DecisionCard.vue, frontend/src/components/editor/SegmentText.vue, frontend/src/router/index.ts, frontend/src/services/api.ts
- **Components Used:** AuditView.vue, EditorAuditView.vue, AuditLedger.vue, AuditTabInline.vue, DecisionCard.vue, SegmentText.vue
- **APIs Used:** POST /v1/sessions/{id}/corrections, POST /v1/sessions/{id}/find-replace, GET /v1/sessions/{id}/corrections, POST /v1/sessions/{id}/corrections/undo, POST /v1/sessions/{id}/corrections/redo, GET /v1/sessions/{id}/review-queue, GET /v1/audit, GET /v1/audit/sessions/{id}/corrections
- **Database Tables Used:** correction_ledger, ledger_pointers, audit_events, transcription_discrepancies, segments, word_alignment, key_points_annotations, alignments, slides, corrections (legacy)
- **Permission Logic Used:** JWT presence only (CurrentUser); no admin/role gate in this module
- **Confidence Score:** High — every claim traced to the assigned source files; UI-only static copy explicitly tagged.
- **Evidence Links:** [corrections.py:332-454](../../app/api/corrections.py#L332-L454), [audit.py:18-83](../../app/api/audit.py#L18-L83), [segment_split.py:22-216](../../app/services/segment_split.py#L22-L216), [segment_merge.py:23-279](../../app/services/segment_merge.py#L23-L279), [029_corrections.sql:88-152](../../migrations/029_corrections.sql#L88-L152), [config.py:134](../../app/config.py#L134)
