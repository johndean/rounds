# 2026-06-12-001 — Segment drag-drop vertical reorder (zero-risk, surgical)

**Status:** Proposed (the deferred bonus from 2026-06-11-001). **Not implemented.**
**Constraint:** zero production risk; no change to timing, alignment, text, the corrections ledger, or processing weights. Flag-gated, snapshot-undoable, off by default.

## Context

Users want to multi-select segments and drag them to a new vertical position in the transcript. This mutates `segments.seq` — which drives **export order**, **transcript display order**, and is read by the processing pipeline. This plan contains that blast radius to exactly one column (`seq`) for one set of rows, with a self-contained snapshot undo, reusing the bulk-reassign machinery just shipped.

## Verified code facts (these make it safe)

- **`segments.seq` is NOT unique.** Migration 022 dropped `UNIQUE(session_id, seq)` (was [001_init.sql:98](../../migrations/001_init.sql#L98)) and replaced it with a plain index ([022_segment_seq_index.sql:12-14](../../migrations/022_segment_seq_index.sql#L12)). Uniqueness lives on `content_hash`. **So we can rewrite seq values in any order with zero collision risk.**
- **Order-by-seq consumers:** export ([artifact_transformer.py:620](../../app/engines/artifact_transformer.py#L620) `ORDER BY seg.seq ASC`) and the segment list ([segments.py:108](../../app/api/segments.py#L108) `ORDER BY seq`). Reorder ⇒ both reflect the new order automatically (that is the feature).
- **Word-highlight is time-keyed, not seq-keyed.** Word alignment orders by `start_ms` ([session_resources.py:673](../../app/api/session_resources.py#L673)); per-word highlighting is internal to a segment. **Reorder does not touch word alignment.**
- **Pipeline tasks order by seq but run pre-`ready`** (align/kp/normalize/anchor/ai_process: e.g. [align.py:66](../../app/tasks/align.py#L66)). Reorder happens in the editor post-`ready`, so they are not affected. Re-ingest regenerates seq from scratch (so manual order is intentionally discarded on a full reprocess — documented, expected).
- **Precedent for safe seq rewrites:** split/merge already renumber seq ([segment_split.py:102](../../app/services/segment_split.py#L102), [segment_merge.py:46-55](../../app/services/segment_merge.py#L46)).
- **Ledger undo never reverts seq.** `_materialize_segments_for_session` replays text only ([corrections.py:211](../../app/api/corrections.py#L211)); reassign/seq write the canonical column via their own endpoints ([corrections.py:579](../../app/api/corrections.py#L579)). ⇒ reorder must NOT ride the ledger undo; it uses the self-contained snapshot undo (same decision as bulk reassign).

## What reorder changes — and what it must NOT

| Touches | How |
|---|---|
| `segments.seq` (only) | Rewritten for the affected rows in one transaction |
| Export order, transcript display order | Follow seq automatically — the intended effect |

| **Must NOT touch** | Why |
|---|---|
| `start_ms` / `end_ms` | Timing drives video sync + captions; reorder is position-only |
| `slide_id` / `speaker_id` | Slide/speaker attribution is separate (use bulk-reassign for that) |
| `text` / `content_hash` | No content change ⇒ no idempotency/discrepancy impact |
| `correction_ledger` | Decoupled — zero risk to text/split-merge undo |
| word alignment, fusion/align weights | Unaffected (time-keyed / pre-ready) |

## Design

### Backend (additive, flag-gated)

1. **Flag** `SEGMENT_REORDER_ENABLED` in `app/config.py` (default `False`; surfaced via `/v1/version` like `BULK_REASSIGN_ENABLED`). Off ⇒ endpoint returns `503 SEGMENT_REORDER_DISABLED`.
2. **Endpoint** `POST /v1/sessions/{id}/segments/reorder` with body `{ ordered_segment_ids: UUID[] }` — the **full new order** of the session's segments.
   - Validate the submitted list is an **exact permutation** of the session's current segment IDs (same set, no missing/extra/dupes). Mismatch ⇒ `409 REORDER_STALE` (client reloads). This guarantees no segment is ever lost or duplicated — the core safety property.
   - Snapshot prior `(segment_id, seq)` for every row whose seq changes.
   - One set-based rewrite in a transaction: `UPDATE segments SET seq = v.new_seq FROM (VALUES …) v(id, new_seq) WHERE segments.id = v.id AND session_id = …`. Deterministic, collision-free (no UNIQUE), all-or-nothing.
   - Serialize against concurrent edits with the existing session edit-lock / a short advisory lock (mirror split/merge's `try_advisory_lock_async`).
   - Record a batch for undo + an `audit_events` row.
3. **Undo:** reuse the `bulk_reassign_batches` table + undo path from migration 059 / [session_resources.py](../../app/api/session_resources.py), generalized:
   - `kind = 'reorder'`; `prior_values` entries carry `prior_seq` (alongside the existing `prior_speaker_id`/`prior_slide_id` shape).
   - The undo endpoint restores whichever prior columns are present (add `seq` to the per-row restore — a small additive change).
   - **Undo cap — DECIDED (2026-06-12): reorder is ALWAYS undoable, no cap.** seq snapshots are cheap integers, so every reorder snapshots prior seq and is fully reversible (the bulk-reassign ≤10 cap does NOT apply here — a single drag can shift many rows' seq, so a "selected count" cap is meaningless for reorder). No ">10 cannot be undone" warning for reorder.

### Frontend (net-new, gated, reuses the multi-select just built)

- In `TranscriptPane.vue` (already owns selection + `sessionId` + emits `segmentsChanged`), gated by `featureFlags.segmentReorderEnabled`:
  - A **drag handle** on each segment row (only when the flag is on). Dragging a row — or, when a multi-selection exists, dragging the **selected group** — shows a drop-between indicator.
  - On drop: compute the new `ordered_segment_ids` locally (the moved item(s) repositioned, preserving their relative order), call `segments.reorder(sessionId, orderedIds)`, then `emit('segmentsChanged')` so EditorView reloads in the new order. Show a toast with **Undo** → `segments.reorderUndo(batchId)`.
  - Reuses the existing drag plumbing pattern (`onDragOver`/`onDrop` already exist for chat/poll anchors — use a distinct dataTransfer type so the two don't collide).
- `api.ts`: `segments.reorder` + `segments.reorderUndo`. `featureFlags` + `AppHeader` gate (mirror the bulk-reassign wiring).

### Known consequences (documented, not bugs)

- **Display + export order follow seq** — the point of the feature.
- **After a manual reorder, seq order can diverge from playback time order.** The playhead still finds the active segment by time, so follow-mode auto-scroll may jump to a non-adjacent row. This is inherent to manual reordering; it is a UX note, not a correctness issue. Mitigation: keep it flag-gated and position-only (timing untouched), and document that reorder is for fixing local mis-orderings.
- **A full re-ingest regenerates seq** and discards manual order (expected; same as any re-derived field).

## Risk & rollback

| Change | Risk | Rollback |
|---|---|---|
| `reorder` endpoint (seq-only, permutation-validated, tx) | Low — one column, all-or-nothing, no UNIQUE to violate | Flip `SEGMENT_REORDER_ENABLED` off → 503 |
| Undo generalization (restore seq too) | Low — additive branch in existing undo | Same flag |
| Frontend drag UI | Low — gated; existing drag plumbing | Flag off hides handles |
| Schema | **None** — reuses `bulk_reassign_batches` (059); `prior_values` is JSONB | n/a |

No new migration required (JSONB `prior_values` already flexible). Nothing destructive; ships dark.

## Verification

- **Unit (no DB):** pure `reorder_seq_map(current_ids, ordered_ids)` → returns the `(id, new_seq)` rewrite + the changed-rows snapshot; assert permutation-rejection on a non-matching list.
- **Integration:** reorder a session's segments → `GET /segments` and `to_cms_html` both reflect the new order; `start_ms`/`slide_id`/`text` unchanged; undo restores exact prior seq; a stale/short list → `409 REORDER_STALE`.
- **Export order test:** snapshot `to_cms_html` before/after a reorder shows only paragraph order changed (no content/slide-marker drift beyond the moved rows).
- **Flag-off:** endpoint 503; no UI handles; zero behaviour change.
- `npm run build` clean; locked weights + existing text/split-merge undo untouched.

## Files (when implemented)

- `app/config.py` (flag), `app/main.py` (`/v1/version`), `app/api/session_resources.py` (reorder + undo generalization), `app/api/segments.py` (or session_resources — keep with the bulk endpoints).
- `frontend/src/services/api.ts`, `stores/featureFlags.ts`, `components/AppHeader.vue`, `components/editor/TranscriptPane.vue`.
- `tests/test_segment_reorder.py` (+ a pure-function unit).
- No migration.

## Out of scope

- Reassigning slide/speaker (already shipped — bulk-reassign). Reorder is position-only.
- Re-timing segments (`start_ms`). Reorder never edits timing.
