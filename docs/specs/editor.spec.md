# Editor — Technical Spec

Developer-facing twin of [../product/editor.md](../product/editor.md).

> References verified against `HEAD` on 2026-06-08. Route line numbers track the
> `@router` decorator.

## Overview

The Editor reads segments + corrections + slides + chat + polls + discrepancies +
audit, and writes through an **append-only corrections ledger**. Undo/redo move a
`sequence_number` pointer rather than mutating rows. Final segment text is
recomputed by replaying the ledger up to the current pointer.

## API routes

| Method | Path | File:Line |
|---|---|---|
| GET | `/v1/segments` | [app/api/segments.py:70](../../app/api/segments.py#L70) |
| PATCH | `/v1/segments/{id}` | [app/api/segments.py:120](../../app/api/segments.py#L120) |
| POST | `/v1/segments/{id}/reassign` | [app/api/segments.py:224](../../app/api/segments.py#L224) |
| POST | `/v1/sessions/{id}/corrections` | [app/api/corrections.py:332](../../app/api/corrections.py#L332) |
| POST | `/v1/sessions/{id}/find-replace` | [app/api/corrections.py:653](../../app/api/corrections.py#L653) |
| GET | `/v1/sessions/{id}/corrections` | [app/api/corrections.py:832](../../app/api/corrections.py#L832) |
| POST | `/v1/sessions/{id}/corrections/undo` | [app/api/corrections.py:883](../../app/api/corrections.py#L883) |
| POST | `/v1/sessions/{id}/corrections/redo` | [app/api/corrections.py:928](../../app/api/corrections.py#L928) |
| GET | `/v1/sessions/{id}/review-queue` | [app/api/corrections.py:978](../../app/api/corrections.py#L978) |
| GET | `/v1/sessions/{id}/words` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| GET | `/v1/sessions/{id}/word-alignment` | [app/api/word_alignment.py:54](../../app/api/word_alignment.py#L54) |

## Correction kinds

`text_edit`, `mark_ok`, `chat_edit`, `speaker_edit`, `find_replace`, `split`,
`merge` — dispatched in `POST /v1/sessions/{id}/corrections`
([app/api/corrections.py:332](../../app/api/corrections.py#L332)).

## Services & engines

| Concern | Module |
|---|---|
| Replay ledger → final text; priority scoring | [app/api/corrections.py](../../app/api/corrections.py) (`_compute_priority_score` ~line 577) |
| Split executor | [app/services/segment_split.py](../../app/services/segment_split.py) |
| Merge executor | [app/services/segment_merge.py](../../app/services/segment_merge.py) |
| Reconstruct pre-correction text | [app/services/segment_inverse.py](../../app/services/segment_inverse.py) |
| Text diffing | [app/engines/diff.py](../../app/engines/diff.py) |
| Caption regen on edit | [app/tasks/burn_captions.py](../../app/tasks/burn_captions.py) |

## Data model

| Table | Migration |
|---|---|
| `segments` (+ seq index, content hash) | [migrations/001_init.sql](../../migrations/001_init.sql), [migrations/020_segment_content_hash.sql](../../migrations/020_segment_content_hash.sql), [migrations/022_segment_seq_index.sql](../../migrations/022_segment_seq_index.sql) |
| `corrections` (append-only ledger) | [migrations/029_corrections.sql](../../migrations/029_corrections.sql), [migrations/000_fix_corrections_collision.sql](../../migrations/000_fix_corrections_collision.sql) |
| `audit_events` | [migrations/004_audit.sql](../../migrations/004_audit.sql) |
| `discrepancies` | [migrations/002_discrepancies.sql](../../migrations/002_discrepancies.sql), [migrations/017_discrepancies_full.sql](../../migrations/017_discrepancies_full.sql) |

## Key constants & invariants

- **Append-only ledger (ADR-005):** corrections are never deleted; undo/redo move
  a pointer.
- **Discrepancy auto-close (BR-018):** only `text_edit` and `mark_ok` close a
  discrepancy (`CLOSES_DISCREPANCY_TYPES` in `app/api/corrections.py`).
- **Split/merge kill-switch:** `SPLIT_MERGE_ENABLED`
  ([app/config.py:134](../../app/config.py#L134), default `False`). When off, the
  executor returns **503 `SPLIT_MERGE_DISABLED`** so a stale UI cannot silently
  no-op.
- **IIL tier gates (BR-010):** `IIL_TIER2_DEFAULT_THRESHOLD` 0.7 /
  `IIL_TIER2_MODERATE_THRESHOLD` 0.85
  ([app/config.py:71-72](../../app/config.py#L71-L72)).

## Frontend

`frontend/src/views/EditorView.vue` orchestrates the panes; corrections wire
through `frontend/src/services/api.ts`. Source of truth for layout/DOM is
`docs/port-source/editor.jsx` (React SSOT).
