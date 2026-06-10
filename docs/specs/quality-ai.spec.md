# Quality & AI Accuracy — Technical Spec

Developer-facing twin of [../product/quality-ai.md](../product/quality-ai.md).

> References verified against `HEAD` on 2026-06-08. `app/config.py` constants are
> pinned by `tests/test_health.py::test_locked_weights_match_audit`.

## Overview

"Quality" is the union of three signals: per-segment **confidence**, **alignment
discrepancies** (segment↔slide), and **classification flags** (medication, name,
drift, etc.). The review queue ranks discrepancies by a deterministic priority
score so reviewers hit the riskiest segments first.

## API routes

| Method | Path | File:Line |
|---|---|---|
| GET | `/v1/discrepancies` | [app/api/discrepancies.py:49](../../app/api/discrepancies.py#L49) |
| GET | `/v1/sessions/{id}/review-queue` | [app/api/corrections.py:978](../../app/api/corrections.py#L978) |
| GET | `/v1/sessions/{id}/failure-reason` | [app/api/sessions.py:753](../../app/api/sessions.py#L753) |
| GET | `/v1/diag/classify-route` | [app/api/diagnostics.py](../../app/api/diagnostics.py) |
| POST | `/v1/diag/sop-check` | [app/api/diagnostics.py](../../app/api/diagnostics.py) |
| POST | `/v1/sop/checks/resolve` | [app/api/sop.py:250](../../app/api/sop.py#L250) |

## Services, engines & tasks

| Concern | Module |
|---|---|
| Priority scoring (`_compute_priority_score`) | [app/api/corrections.py](../../app/api/corrections.py) (~line 577) |
| LLM routing (Gemini vs Vertex) | [app/engines/llm_client.py](../../app/engines/llm_client.py) |
| Classification | [app/tasks/classify_task.py](../../app/tasks/classify_task.py) |
| Alignment confidence | [app/engines/alignment.py](../../app/engines/alignment.py) |
| Discrepancy generation (LCS) | [app/tasks/lcs_discrepancies.py](../../app/tasks/lcs_discrepancies.py), [app/engines/diff.py](../../app/engines/diff.py) |
| IIL validation / adaptive learning | [app/iil/validation.py](../../app/iil/validation.py), [app/iil/adaptive_learning.py](../../app/iil/adaptive_learning.py) |
| SOP deadline checks | [app/tasks/sop_tasks.py](../../app/tasks/sop_tasks.py) (`sop_check_deadlines_task`) |

## Data model

| Table | Migration |
|---|---|
| `discrepancies` | [migrations/002_discrepancies.sql](../../migrations/002_discrepancies.sql), [migrations/017_discrepancies_full.sql](../../migrations/017_discrepancies_full.sql) |
| `alignments` (confidence, drift/uncertain flags) | [migrations/014_align.sql](../../migrations/014_align.sql) |
| `segments` (confidence, flags) | [migrations/001_init.sql](../../migrations/001_init.sql) |
| IIL learning / features | [migrations/019_iil_learning.sql](../../migrations/019_iil_learning.sql), [migrations/021_iil_features.sql](../../migrations/021_iil_features.sql) |

## Key constants & invariants

| Constant | Value | Source |
|---|---|---|
| Priority score (BR-006): confidence <0.4 → +70, <0.6 → +20; drift/uncertain boosts | — | [app/api/corrections.py](../../app/api/corrections.py) (`_compute_priority_score`) |
| `IIL_TIER2_DEFAULT_THRESHOLD` | 0.7 | [app/config.py:71](../../app/config.py#L71) |
| `IIL_TIER2_MODERATE_THRESHOLD` | 0.85 | [app/config.py:72](../../app/config.py#L72) |
| `IIL_DRIFT_CONFIDENCE_PENALTY` | 0.3 | [app/config.py:69](../../app/config.py#L69) |
| `GEMINI_CLASSIFY_MODEL` | `gemini-2.5-flash-lite` | [app/config.py:85](../../app/config.py#L85) |
| `VERTEX_AI_CLASSIFY_ENABLED` | `False` | [app/config.py:86](../../app/config.py#L86) |
| Gemini hallucination guard | `MIN_BLOCK=80, MIN_REPS=3` (BR-015) | [app/tasks/ai_process.py](../../app/tasks/ai_process.py) |

- **Discrepancy auto-close (BR-018):** only `text_edit` / `mark_ok` corrections
  close a discrepancy.
- **Classification routing** is read-only-observable via `/v1/diag/classify-route`.
