# Video & Synchronization — Technical Spec

Developer-facing twin of [../product/video-sync.md](../product/video-sync.md).

> References verified against `HEAD` on 2026-06-08. `app/config.py` alignment
> constants are pinned by `tests/test_health.py::test_locked_weights_match_audit`.

## Overview

Playback uses a signed GCS media URL. Sync is driven by three precomputed
artifacts: **slides** (scene boundaries), **alignments** (segment→slide), and
**word alignment** (per-word timings for karaoke highlighting). Captions are
served as WebVTT with an ETag keyed on the correction sequence so they invalidate
on every edit.

## API routes

| Method | Path | File:Line |
|---|---|---|
| GET | `/v1/sessions/{id}/media-url` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| GET | `/v1/sessions/{id}/slides` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| POST | `/v1/sessions/{id}/slides/re-extract` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| GET | `/v1/sessions/{id}/sources` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| GET | `/v1/sessions/{id}/word-alignment` | [app/api/word_alignment.py:54](../../app/api/word_alignment.py#L54) |
| GET | `/v1/sessions/{id}/captions.vtt` | [app/api/exports.py:120](../../app/api/exports.py#L120) (`captions_router`) |
| POST | `/v1/diag/realign/{session_id}` | [app/api/diagnostics.py](../../app/api/diagnostics.py) |

## Services, engines & tasks

| Concern | Module |
|---|---|
| Slide extraction | [app/tasks/slide_extract.py](../../app/tasks/slide_extract.py) |
| Frame sampling / visual-change scoring | [app/tasks/frame_task.py](../../app/tasks/frame_task.py) |
| Anchor cross-validation | [app/engines/anchor.py](../../app/engines/anchor.py), [app/tasks/anchor_task.py](../../app/tasks/anchor_task.py) |
| Segment→slide alignment (4-factor weighted) | [app/engines/alignment.py](../../app/engines/alignment.py), [app/tasks/align.py](../../app/tasks/align.py) |
| Signed media URL | [app/services/gcs.py](../../app/services/gcs.py) |
| Caption regen on edit | [app/tasks/burn_captions.py](../../app/tasks/burn_captions.py) |

## Data model

| Table | Migration |
|---|---|
| `slides` / slide time ranges | [migrations/001_init.sql](../../migrations/001_init.sql) |
| `words` (per-word timings) | [migrations/015_words.sql](../../migrations/015_words.sql) |
| word alignment | [migrations/036_word_alignment.sql](../../migrations/036_word_alignment.sql) |
| `alignments` | [migrations/014_align.sql](../../migrations/014_align.sql) |
| `frames` / fusion boundaries | [migrations/013_fusion.sql](../../migrations/013_fusion.sql) |

## Key constants & invariants

| Constant | Value | Source |
|---|---|---|
| `FRAME_SAMPLE_FPS` | 2 | [app/config.py:52](../../app/config.py#L52) |
| `VISUAL_CHANGE_THRESHOLD` | 8.0 | [app/config.py:53](../../app/config.py#L53) |
| `ANCHOR_CROSS_VALIDATE_WINDOW` | 5.0 | [app/config.py:54](../../app/config.py#L54) |
| `SOFT_WINDOW_EXPANSION` | 5.0 | [app/config.py:55](../../app/config.py#L55) |
| `BOUNDARY_MERGE_WINDOW` | 3.0 | [app/config.py:56](../../app/config.py#L56) |
| `ALIGN_WEIGHT_*` (semantic .35 / coverage .25 / temporal .25 / sequential .15) | locked | [app/config.py:63-66](../../app/config.py#L63-L66) |
| `ALIGN_SEQUENTIAL_PENALTY` | 0.8 | [app/config.py:67](../../app/config.py#L67) |

- **Caption ETag invalidation:** the VTT response carries an ETag derived from
  `(session_id, max_correction_seq)`; editing a segment bumps the sequence and the
  player re-fetches. Fillers are preserved in captions (BR-016).

## Frontend

The video player + scrubber live in the Editor left pane
(`frontend/src/views/EditorView.vue` and its video components); layout SSOT is
`docs/port-source/editor.jsx`.
