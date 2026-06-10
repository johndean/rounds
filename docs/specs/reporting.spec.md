# Reporting & Analytics — Technical Spec

Developer-facing twin of [../product/reporting.md](../product/reporting.md).

> References verified against `HEAD` on 2026-06-08.

## Overview

Reporting is pull-based: the Dashboard aggregates over the session list and SOP
state on read; there is no time-series store. The **audit trail** is an
append-only event ledger, and the **Improvements** board is a lightweight
suggestion tracker with its own status workflow.

## API routes

| Method | Path | File:Line |
|---|---|---|
| GET | `/v1/audit` | [app/api/audit.py:18](../../app/api/audit.py#L18) |
| GET | `/v1/audit/sessions/{session_id}/corrections` | [app/api/audit.py:45](../../app/api/audit.py#L45) |
| GET | `/v1/sessions/{id}/audit-log` | [app/api/sessions.py:306](../../app/api/sessions.py#L306) |
| GET | `/v1/queue/mine` (Your Queue) | [app/api/queue.py](../../app/api/queue.py) |
| GET | `/v1/improvements` | [app/api/improvements.py:76](../../app/api/improvements.py#L76) |
| POST | `/v1/improvements` | [app/api/improvements.py:93](../../app/api/improvements.py#L93) |
| GET | `/v1/improvements/{id}` | [app/api/improvements.py:114](../../app/api/improvements.py#L114) |
| PUT | `/v1/improvements/{id}` (wizard step) | [app/api/improvements.py:144](../../app/api/improvements.py#L144) |
| PATCH | `/v1/improvements/{id}` | [app/api/improvements.py:163](../../app/api/improvements.py#L163) |
| DELETE | `/v1/improvements/{id}` | [app/api/improvements.py:179](../../app/api/improvements.py#L179) |
| GET | `/v1/settings/export/macro` (export usage) | [app/api/settings.py:680](../../app/api/settings.py#L680) |

Dashboard KPIs are computed from `/v1/sessions` aggregates + SOP summary; there is
no dedicated metrics endpoint.

## Services & engines

| Concern | Module |
|---|---|
| Audit event recording (append-only) | [app/api/audit.py](../../app/api/audit.py) |
| Improvements / adaptive learning source | [app/iil/adaptive_learning.py](../../app/iil/adaptive_learning.py) |
| SOP summary / deadlines | [app/tasks/sop_tasks.py](../../app/tasks/sop_tasks.py) |

## Data model

| Table | Migration |
|---|---|
| `audit_events` (append-only) | [migrations/004_audit.sql](../../migrations/004_audit.sql), [migrations/024_session_audit_finalized.sql](../../migrations/024_session_audit_finalized.sql) |
| `improvements` | [migrations/005_improvements.sql](../../migrations/005_improvements.sql) |
| `artifacts` (export provenance) | [migrations/018_artifacts.sql](../../migrations/018_artifacts.sql) |

## Key constants & invariants

- **Append-only audit:** `audit_events` rows are never updated or deleted — the
  ledger is the complete history and the source for undo/redo provenance.
- **Pull-based metrics:** counts are current-state aggregates; sparkline visuals
  in the Dashboard are not yet backed by a time-series (documented gap).
- **Improvements status workflow:** `proposed → in_review → approved → completed`,
  simpler than the session FSM.

## Frontend

`DashboardView.vue` (KPI cards, pipeline + SOP stage rows, Your Queue),
`ImprovementsView.vue`, and the Editor's Audit tab. Layout SSOT:
`docs/port-source/dashboard.jsx`.
