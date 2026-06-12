# 2026-06-11-001 — Polls CMS publish fix + bulk speaker/moderator reassignment

**Status:** Proposed (investigation complete; **NOT implemented**)
**Author:** johndean@vin.com (with Claude, via `/gstack-investigate`)
**Constraint:** zero-risk — no regression to speed, performance, or stability. Both changes are additive and feature-flagged.

## Context

Two user-reported needs:
1. **Bug:** polls don't publish to the CMS — the published document has a large empty gap where the poll should be.
2. **Feature:** reassigning a speaker/moderator is per-segment today; users want a bulk action across many segments.

Investigation followed the "no fix without root cause" rule. Root cause for (1) is confirmed structural (below). For (2), the design preserves the append-only corrections ledger (ADR-005 / BR-018) and the user's explicit undo rule.

---

## ITEM 1 — Polls not publishing to CMS (root cause + fix)

### Root cause (confirmed by code trace)

The CMS publish path is **decoupled from the poll state the editor manages.**

- `to_cms_html` → `apply_cms_transform` injects polls **only** from `session.polls`, which `load_session_for_export` populates **exclusively from `sessions.polls_parsed`** (a manifest JSONB blob) — [artifact_transformer.py:601](../../app/engines/artifact_transformer.py#L601), [:650-656](../../app/engines/artifact_transformer.py#L650).
- Injection is by **slide-marker string match**: `t.replace("++{slide_n}*+", marker+block, 1)` — [artifact_transformer.py:311-315](../../app/engines/artifact_transformer.py#L311). No segment/anchor awareness.
- `sessions.polls_parsed` is written **only at manifest ingest** ([gcs_upload.py:261](../../app/api/gcs_upload.py#L261), [add_to_session.py:775](../../app/api/add_to_session.py#L775)). At ingest it is *also* bridged into the `polls` + `poll_options` tables with `placed=FALSE` ([gcs_upload.py:306-339](../../app/api/gcs_upload.py#L306)).
- The **editor** reads/writes the `polls` table (place, reorder, re-anchor via `anchor_segment_id`, autoplace). **None of that writes back to `sessions.polls_parsed`.** So what the user places/edits in the editor never reaches the export.
- The timestamp placeholder `[pq][t]` (the "chat/poll injection" marker, [artifact_transformer.py:216](../../app/engines/artifact_transformer.py#L216)) is resolved **to chat only** ([:320-329](../../app/engines/artifact_transformer.py#L320)); any leftover `[pq]` is stripped ([:332](../../app/engines/artifact_transformer.py#L332)). A poll sitting at a placeholder position is therefore **blanked** → the reserved space renders empty = the large gap.

**Ruled out:** option shape is *not* the bug — the parser emits `{count, percent, label}` ([extras2_parser.py:228-231](../../app/services/extras2_parser.py#L228)) exactly as `_format_poll_block` expects ([:431-435](../../app/engines/artifact_transformer.py#L431)).

**Net:** a poll the user manages in the editor publishes only if (a) it still exists verbatim in `polls_parsed` AND (b) its `slide_n` maps to a slide that has a `++N*+` marker in the transcript. Editor-placed/anchored polls, or sessions whose `polls_parsed` is empty/mismatched, produce an empty slot.

### Confirm on the failing session before coding (one verification step)

Pick the session that showed the gap and compare the two sources:
```sql
SELECT polls_parsed FROM sessions WHERE id = '<SID>';                          -- export source
SELECT id, question, placed, anchor_segment_id, total_votes FROM polls
  WHERE session_id = '<SID>';                                                  -- editor source
```
Then generate `to_cms_html` for that session and locate the gap. Expected: `polls_parsed` is empty or its `slide_n` doesn't match a rendered slide marker, while the `polls` table has the poll the user sees. This confirms the decoupling is what produces the gap (vs. a missing marker).

### Zero-risk fix (design — implement after confirmation)

Re-couple the export to the editor's source of truth, additively:

1. In `load_session_for_export`, build `session.polls` from the **`polls` + `poll_options` tables** (the editor's data: `question`, options, `anchor_segment_id`, `placed`, `slide` via the anchored segment), **falling back** to `sessions.polls_parsed` when the tables have no rows (legacy sessions). Pure additive read change — no existing behavior removed.
2. Inject a placed poll at its **anchored segment position** (resolve `anchor_segment_id` → the segment's slide/marker), keeping the slide-marker path as the fallback for unanchored/legacy polls. Mirrors how the editor shows it.
3. Add a **publish-time guard**: if a poll resolves to no render position, surface it (log + optional `CMSValidationError` in `strict` mode) so a gap is caught at publish, never shipped silently. Reuses the existing validation gate ([artifact_transformer.py:387](../../app/engines/artifact_transformer.py#L387)).
4. Gate the new render path behind a flag (e.g. `CMS_POLLS_FROM_TABLE`, default the safe/legacy behavior until verified in staging), matching the repo's kill-switch convention.

**Why zero-risk:** read-only change to the export model; fallback chain means sessions that publish correctly today are byte-identical; new behavior is flag-gated; no schema change; no write-path change.

---

## ITEM 2 — Bulk speaker/moderator reassignment

### Today

Speaker reassignment is one `speaker_reassignment` correction per segment in the append-only `correction_ledger` ([corrections.py:52](../../app/api/corrections.py#L52)); undo/redo move a per-session `sequence_number` pointer ([corrections.py:884](../../app/api/corrections.py#L884)). (Note: `segments.py:224` `/reassign` is **slide** reassignment via the legacy `corrections` table — a different path; leave it untouched.)

### Design

New additive endpoint — one transaction, set-based, no N round-trips:

`POST /v1/sessions/{id}/segments/bulk-speaker-reassign`
```
{ "segment_ids": ["…"],   // 1–500, hard cap 500
  "speaker_id": "…" }      // target speaker/moderator
```
Behavior:
1. Validate: `speaker_id` belongs to the session; `len(segment_ids)` between 1 and **500** (reject >500). De-dupe ids.
2. One DB transaction:
   - `UPDATE segments SET speaker_id = :sp WHERE session_id = :s AND id = ANY(:ids)` — single set-based statement.
   - Allocate one contiguous `sequence_number` range and batch-insert N `speaker_reassignment` rows into `correction_ledger` (one `executemany` / `INSERT … SELECT unnest(...)`), all sharing one **`batch_id`** (UUID).
   - Stamp `batch_undoable = (N <= 10)` on those rows.
   - One `audit_events` summary row for the batch.
3. Emit a single WS event for the batch so the editor refreshes once.

### Undo rule (user's hard constraint)

- **≤10 segments → undoable.** The batch's `sequence_number` range is contiguous; undo reverts the whole batch atomically (pointer moves back across the range).
- **>10 segments → NOT undoable.** Backend sets an **undo floor** at the batch's max `sequence_number`; the undo endpoint refuses to move the pointer across a `batch_undoable = false` batch and returns a clear error. Frontend must show a blocking confirm **before** firing: *"This reassigns N segments and cannot be undone. Continue?"* when `N > 10`.
- Append-only invariant preserved: nothing is deleted; "not undoable" is a pointer-floor, not a row removal (keeps ADR-005 / BR-018 intact).

### Performance / stability

- 500 segments = 1 `UPDATE` + 1 batched `INSERT` + 1 audit row in a single transaction. No per-segment HTTP, no N+1. Wrap in a tx → atomic (all-or-nothing); on error, rollback, zero partial state.
- Existing per-segment reassign + undo/redo are untouched (new endpoint is additive).
- Flag-gate (e.g. `BULK_REASSIGN_ENABLED`, default off) for instant disable, matching `SPLIT_MERGE_ENABLED` precedent.

### Schema (additive, zero-risk)

Forward-only migration `0NN_correction_ledger_batch.sql`: add nullable `batch_id UUID` and `batch_undoable BOOLEAN` to `correction_ledger`. Nullable adds = no rewrite, no default backfill, no lock of consequence (matches ADR-011 forward-only).

### Frontend

- `SegmentText.vue` / transcript pane: multi-select (checkbox or shift-range), cap 500.
- `SpeakerEditPanel.vue`: "Reassign N selected to <speaker>" action → calls the bulk endpoint.
- Confirm dialog when selection > 10 (the non-undoable warning). Reuse the existing confirm composable.

---

## Risk & rollback

| Change | Risk | Rollback |
|---|---|---|
| Item 1 export read from `polls` table (fallback to `polls_parsed`) | Low — read-only, fallback chain, flag-gated | Flip flag → legacy behavior |
| Item 1 publish-time poll guard | Low — only adds a validation signal | Flag / remove guard |
| Item 2 bulk endpoint | Low — additive route, single tx, set-based | Flip `BULK_REASSIGN_ENABLED` off |
| Item 2 migration (2 nullable cols) | Minimal — additive, no backfill | Columns are nullable + unused if flag off |

No existing endpoint, render path, or undo behavior is modified destructively. Both features ship dark (flag off) and are enabled per environment after verification.

## Verification

- **Item 1:** unit-test `to_cms_html` for a session with an editor-placed/anchored poll → poll appears at the anchored position, no empty gap; legacy session with only `polls_parsed` still renders identically (snapshot diff). Manually publish the originally-failing session and confirm the gap is filled.
- **Item 2:** integration test — bulk reassign 500 segments in one call completes in one transaction (<1s target), all `segments.speaker_id` updated, N ledger rows share one `batch_id`; undo of a ≤10 batch reverts all; undo across a >10 batch is rejected with the expected error; per-segment reassign + undo still pass. Frontend: >10 selection shows the non-undoable confirm.
- No change to locked weights, FSM, or auth surfaces.

## Implementation status (2026-06-12)

**Backend + API contract: implemented, tested, shipped dark (flags default OFF — zero behaviour change until flipped in Railway env).**

- `app/config.py` — `BULK_REASSIGN_ENABLED`, `CMS_POLLS_FROM_TABLE` (both default False), `BULK_REASSIGN_MAX_SEGMENTS=500`, `BULK_REASSIGN_UNDO_MAX_SEGMENTS=10`.
- `migrations/059_bulk_reassign_batches.sql` — additive snapshot table (forward-only).
- `app/api/session_resources.py` — `POST /v1/sessions/{id}/segments/bulk-reassign` (speaker and/or slide; set-based UPDATE; snapshots prior speaker_id+slide_id when ≤10; >10 not undoable) + `POST .../bulk-reassign/{batch_id}/undo`. Decoupled from the ledger pointer-undo, so zero risk to existing text/undo.
- `app/engines/artifact_transformer.py` — `_polls_from_table()` + flag-gated load branch: read polls from the editor-owned `polls`/`poll_options` tables (anchored slide), fall back to `polls_parsed`. Injection mechanism unchanged.
- Contract: `app/main.py` `/v1/version` exposes `bulk_reassign_enabled`; `frontend/src/services/api.ts` `segments.bulkReassign` / `bulkReassignUndo`; `stores/featureFlags.ts` + `AppHeader.vue` gate the UI.
- **Verified:** `tests/test_export_polls.py` 4/4 pass; all backend files byte-compile; `npm run build` clean; locked weights intact; flags confirmed default-off.

**Remaining — editor multi-select UI (net-new, not in the React SSOT):** segment multi-select in the transcript (checkbox + shift-range), a "Reassign selected → speaker / slide" bar gated by `featureFlags.bulkReassignEnabled`, a blocking ">10 cannot be undone" confirm, and an Undo affordance for ≤10 batches (toast → `segments.bulkReassignUndo`). Verify with `npm run build` + the browser.

## Bonus (deferred): multi-select drag-drop vertical reorder

Out of scope here. Vertical reordering changes `segments.seq` (and which slide a segment belongs to), which interacts with export ordering, word/slide alignment, and the corrections ledger — its own invariants and likely its own migration. Tracked as a future enhancement per the user's "bonus if eventually" note; not built in this change.

## Files (when implemented)

- Item 1: `app/engines/artifact_transformer.py` (`load_session_for_export`, poll injection), `app/config.py` (flag).
- Item 2: new `app/api/segments.py` (or `session_resources.py`) bulk route; `app/api/corrections.py` (undo-floor check); `migrations/0NN_correction_ledger_batch.sql`; `app/config.py` (flag); frontend `components/editor/SpeakerEditPanel.vue`, `SegmentText.vue`, transcript pane selection.
