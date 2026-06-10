# Workflow & Export — Technical Spec

Developer-facing twin of [../product/workflow-and-export.md](../product/workflow-and-export.md).

> References verified against `HEAD` on 2026-06-08. Route line numbers track the
> `@router` decorator. `app/config.py` constants are pinned by
> `tests/test_health.py::test_locked_weights_match_audit` — do not edit without a
> coordinated config + test + plan update.

## Overview

Two concerns live here: the **SOP stage machine** (Prep → Copy Draft → Medical →
Copy Final → CMS → Captions → QA → Complete) and **artifact export** (docx / srt /
vtt / txt / html / zip). The session-level status FSM
(`uploading → transcribing → normalizing → fusing → aligning → ready → complete`;
`failed` reachable from any non-terminal status; `failed`/`complete` terminal) gates both.

## API routes

| Method | Path | File:Line |
|---|---|---|
| GET | `/v1/sop` | [app/api/sop.py:93](../../app/api/sop.py#L93) |
| POST | `/v1/sop/advance` | [app/api/sop.py:113](../../app/api/sop.py#L113) |
| POST | `/v1/sop/assign` | [app/api/sop.py:145](../../app/api/sop.py#L145) |
| PATCH | `/v1/sop/annotations` | [app/api/sop.py:196](../../app/api/sop.py#L196) |
| POST | `/v1/sop/checks/resolve` | [app/api/sop.py:250](../../app/api/sop.py#L250) |
| GET | `/v1/sessions/{id}/stage-assignees` | [app/api/sessions.py:345](../../app/api/sessions.py#L345) |
| PUT | `/v1/sessions/{id}/stage-assignees/{stage}` | [app/api/sessions.py:379](../../app/api/sessions.py#L379) |
| POST | `/v1/sessions/{id}/stage-assignees/apply-type-defaults` | [app/api/sessions.py:498](../../app/api/sessions.py#L498) |
| GET | `/v1/sessions/{id}/exports/{format}` | [app/api/exports.py:41](../../app/api/exports.py#L41) |
| GET | `/v1/sessions/{id}/captions.vtt` | [app/api/exports.py:120](../../app/api/exports.py#L120) (`captions_router`) |

## Services, engines & tasks

| Concern | Module |
|---|---|
| Status FSM (`ALLOWED_TRANSITIONS`, `transition_session_sync`) | [app/engines/state_machine.py](../../app/engines/state_machine.py) |
| Export rendering (`to_docx` / `to_srt` / `to_vtt` / `to_txt` / `to_cms_html` / `to_zip`, `load_session_for_export`) | [app/engines/artifact_transformer.py](../../app/engines/artifact_transformer.py) |
| Filler-word tiers used by docx/txt stripping | [app/iil/normalization.py](../../app/iil/normalization.py) |
| SOP auto-init on finalize | [app/tasks/sop_tasks.py](../../app/tasks/sop_tasks.py) (`sop_auto_init_task`) |
| Hourly deadline scan + email | [app/tasks/sop_tasks.py](../../app/tasks/sop_tasks.py) (`sop_check_deadlines_task`) |

## Data model

| Table | Migration |
|---|---|
| `sessions` (status FSM, `deleted_at`) | [migrations/001_init.sql](../../migrations/001_init.sql) |
| `sop_state` | [migrations/003_sop.sql](../../migrations/003_sop.sql) |
| state-machine columns | [migrations/010_state_machine.sql](../../migrations/010_state_machine.sql) |
| `session_stage_assignees` | [migrations/042_session_stage_assignees.sql](../../migrations/042_session_stage_assignees.sql) |
| `artifacts` / artifact versions | [migrations/018_artifacts.sql](../../migrations/018_artifacts.sql), [migrations/023_artifact_versions.sql](../../migrations/023_artifact_versions.sql) |
| session-type assignee matrix | [migrations/039_seed_session_types.sql](../../migrations/039_seed_session_types.sql), [migrations/040_stage_assignees_typed_fk.sql](../../migrations/040_stage_assignees_typed_fk.sql) |

## Key constants & invariants

- **Legal status transitions (BR-007):** enforced in
  `app/engines/state_machine.py` — the FSM module is the single gate for legal
  *moves*. Valid *values* are separately guarded by the `sessions_status_check`
  CHECK (migration 010).
- **Deadline email throttle (BR-004):** one email per session+stage per ~23h
  window, deduped via `audit_events`; gated by `SOP_DEADLINE_EMAIL_ENABLED`
  ([app/config.py:110](../../app/config.py#L110), default `False`).
- **Filler stripping by format (BR-016):** docx/txt/html strip TIER-1 fillers;
  srt/vtt preserve them for audio alignment.
- **Unknown speaker fallback (BR-017):** `(Unknown)` in every export schema.
- **204 endpoints** must use `response_class=Response` + `Response(status_code=204)`
  (FastAPI 0.115 rejects `-> None` with 204).

## How this maps to the UI

The SOP page consumes `/v1/sop` + `/v1/sop/advance`; per-session stage assignment
on Session Detail uses the `stage-assignees` routes; the Editor's Export menu hits
`/v1/sessions/{id}/exports/{format}`; the player's caption track loads
`/v1/sessions/{id}/captions.vtt` (ETag-cached on correction sequence — see
[video-sync.spec.md](video-sync.spec.md)).
