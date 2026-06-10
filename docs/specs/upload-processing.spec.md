# Upload & Processing — Technical Spec

Developer-facing twin of [../product/upload-processing.md](../product/upload-processing.md).

> References verified against `HEAD` on 2026-06-08. `app/config.py` constants are
> pinned by `tests/test_health.py::test_locked_weights_match_audit`.

## Overview

Browser → signed GCS PUT → `upload-complete` → Celery ingest DAG. The pipeline
fans out from `ingest_task` (transcribe + frame sampling) and converges on
`finalize_task`, which marks the session `ready`, kicks off key-points and SOP
auto-init.

## API routes

| Method | Path | File:Line |
|---|---|---|
| POST | `/v1/gcs/upload-url` | [app/api/gcs_upload.py:69](../../app/api/gcs_upload.py#L69) |
| POST | `/v1/gcs/upload-complete` | [app/api/gcs_upload.py:110](../../app/api/gcs_upload.py#L110) |
| POST | `/v1/sessions` (create) | [app/api/sessions.py:178](../../app/api/sessions.py#L178) |
| GET | `/v1/queue/mine` (operator pipeline view) | [app/api/queue.py](../../app/api/queue.py) |
| POST | `/v1/diag/reingest/{session_id}` | [app/api/diagnostics.py](../../app/api/diagnostics.py) |
| GET | `/v1/diag/gcs`, `/v1/diag/gcs-checks` | [app/api/diagnostics.py](../../app/api/diagnostics.py) |
| POST | add-file routes (`/v1/sessions/{id}/add/*`) | [app/api/add_to_session.py](../../app/api/add_to_session.py) |

## Pipeline (Celery DAG)

| Task | Module | Role |
|---|---|---|
| `ingest_task` | [app/tasks/ingest.py](../../app/tasks/ingest.py) | Orchestrator; fans out + chains finalize |
| `transcribe_task` | [app/tasks/transcribe.py](../../app/tasks/transcribe.py) | Chunked Google STT path |
| `ai_process_task` | [app/tasks/ai_process.py](../../app/tasks/ai_process.py) | Gemini multimodal path (AI Mode) |
| `normalize_task` | [app/tasks/normalize.py](../../app/tasks/normalize.py) | IIL filler/terminology normalization |
| `slide_extract_task` / `frame_task` | [app/tasks/slide_extract.py](../../app/tasks/slide_extract.py), [app/tasks/frame_task.py](../../app/tasks/frame_task.py) | Slide + visual-change sampling |
| `anchor_task` | [app/tasks/anchor_task.py](../../app/tasks/anchor_task.py) | Cross-validate anchor candidates |
| `fusion_task` | [app/tasks/fusion.py](../../app/tasks/fusion.py) | Boundary fusion (locked weights) |
| `align_task` | [app/tasks/align.py](../../app/tasks/align.py) | Segment→slide alignment |
| `lcs_discrepancies_task` | [app/tasks/lcs_discrepancies.py](../../app/tasks/lcs_discrepancies.py) | LCS diff → discrepancy rows |
| `finalize_task` | [app/tasks/finalize.py](../../app/tasks/finalize.py) | Mark ready, trigger KP + SOP init |
| `upload_watchdog_task` | [app/tasks/upload_watchdog.py](../../app/tasks/upload_watchdog.py) | Beat: recover stuck uploads |

Celery app + Beat schedule: [app/tasks/celery_app.py](../../app/tasks/celery_app.py).

## Services & boundaries

| Concern | Module |
|---|---|
| Signed PUT URL (`make_signed_put_url`) | [app/services/gcs.py](../../app/services/gcs.py) |
| **R7 scope invariant** (`find_out_of_scope_uri`) | [app/services/gcs.py](../../app/services/gcs.py) + [tests/test_gcs_scope.py](../../tests/test_gcs_scope.py) |
| Idempotency replay (`Idempotency-Key`) | [app/middleware/idempotency.py](../../app/middleware/idempotency.py) |
| Pre-ready gate | [app/engines/pre_ready_gate.py](../../app/engines/pre_ready_gate.py) |

## Data model

| Table | Migration |
|---|---|
| `sources` | [migrations/001_init.sql](../../migrations/001_init.sql) |
| `session_templates` (ai_pipeline, stt_backend, iil_config) | [migrations/009_session_templates.sql](../../migrations/009_session_templates.sql) |
| `segments`, `words` | [migrations/001_init.sql](../../migrations/001_init.sql), [migrations/015_words.sql](../../migrations/015_words.sql) |
| fusion / alignment columns | [migrations/013_fusion.sql](../../migrations/013_fusion.sql), [migrations/014_align.sql](../../migrations/014_align.sql) |
| manifest (extras2) | [migrations/011_manifest.sql](../../migrations/011_manifest.sql) |

## Key constants & invariants

| Constant | Value | Source |
|---|---|---|
| `MAX_UPLOAD_SIZE_MB` | 2048 | [app/config.py:48](../../app/config.py#L48) |
| `MAX_VIDEO_DURATION_MINUTES` | 180 | [app/config.py:49](../../app/config.py#L49) |
| `FRAME_SAMPLE_FPS` | 2 | [app/config.py:52](../../app/config.py#L52) |
| `VISUAL_CHANGE_THRESHOLD` | 8.0 | [app/config.py:53](../../app/config.py#L53) |
| `ANCHOR_CROSS_VALIDATE_WINDOW` | 5.0 | [app/config.py:54](../../app/config.py#L54) |
| `FUSION_WEIGHT_*` (visual .5 / anchor .3 / semantic .2), threshold .35 | locked | [app/config.py:58-61](../../app/config.py#L58-L61) |
| `TRANSCRIPTION_BACKEND` | `google_stt_chunked` | [app/config.py:80](../../app/config.py#L80) |
| `IDEMPOTENCY_KEY_TTL_SECONDS` | 86400 | [app/config.py:77](../../app/config.py#L77) |
| `UPLOAD_WATCHDOG_ENABLED` / `UPLOAD_STUCK_THRESHOLD_SEC` | `False` / 300 | [app/config.py:100-101](../../app/config.py#L100-L101) |

- **R7 (locked):** `/v1/gcs/upload-complete` rejects any `gcs_uri` outside
  `gs://<bucket>/sessions/<id>/`.
- **AI path routing:** `ingest_task` branches on `session_templates.ai_pipeline`
  (`direct` → Gemini, else chunked STT). Gemini path runs a hallucination guard
  (`MIN_BLOCK=80, MIN_REPS=3` in `app/tasks/ai_process.py`, BR-015).
