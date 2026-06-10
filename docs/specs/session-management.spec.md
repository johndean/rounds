# Session Management — Technical Spec

Developer-facing twin of [../product/session-management.md](../product/session-management.md).

> References verified against `HEAD` on 2026-06-08. Route line numbers track the
> `@router` decorator.

## Overview

Session CRUD, the status FSM, soft-delete/restore/purge, distributed edit locks
(Redis), and per-user concurrency rate limiting.

## API routes

| Method | Path | File:Line |
|---|---|---|
| GET | `/v1/sessions` (list, filters) | [app/api/sessions.py:138](../../app/api/sessions.py#L138) |
| POST | `/v1/sessions` (create) | [app/api/sessions.py:178](../../app/api/sessions.py#L178) |
| GET | `/v1/sessions/deleted` | [app/api/sessions.py:266](../../app/api/sessions.py#L266) |
| GET | `/v1/sessions/{id}/audit-log` | [app/api/sessions.py:306](../../app/api/sessions.py#L306) |
| GET | `/v1/sessions/{id}/pipeline-config` | [app/api/sessions.py:323](../../app/api/sessions.py#L323) |
| GET | `/v1/sessions/{id}` | [app/api/sessions.py:547](../../app/api/sessions.py#L547) |
| PATCH | `/v1/sessions/{id}` | [app/api/sessions.py:569](../../app/api/sessions.py#L569) |
| DELETE | `/v1/sessions/{id}` (soft) | [app/api/sessions.py:621](../../app/api/sessions.py#L621) |
| POST | `/v1/sessions/{id}/restore` | [app/api/sessions.py:668](../../app/api/sessions.py#L668) |
| DELETE | `/v1/sessions/{id}/permanent` (purge) | [app/api/sessions.py:697](../../app/api/sessions.py#L697) |
| POST | `/v1/sessions/{id}/locks/acquire` | [app/api/locks.py:99](../../app/api/locks.py#L99) |
| POST | `/v1/sessions/{id}/locks/heartbeat` | [app/api/locks.py:142](../../app/api/locks.py#L142) |
| POST | `/v1/sessions/{id}/locks/release` | [app/api/locks.py:188](../../app/api/locks.py#L188) |
| GET | `/v1/sessions/{id}/locks/holder` | [app/api/locks.py:204](../../app/api/locks.py#L204) |
| POST | `/v1/sessions/{id}/locks/force-take` | [app/api/locks.py:218](../../app/api/locks.py#L218) |

## Services & engines

| Concern | Module |
|---|---|
| Status FSM (`ALLOWED_TRANSITIONS`, `transition_session_sync`) | [app/engines/state_machine.py](../../app/engines/state_machine.py) |
| Distributed edit locks (Redis, heartbeat TTL) | [app/services/db_locks.py](../../app/services/db_locks.py) |
| Per-user concurrency rate limit | [app/middleware/rate_limit.py](../../app/middleware/rate_limit.py) |
| Session init / stage seeding | [app/services/session_init.py](../../app/services/session_init.py) |
| Role gates (`LEGACY_ADMIN_EMAIL`) | [app/security/roles.py](../../app/security/roles.py) |

## Data model

| Table | Migration |
|---|---|
| `sessions` (status, `deleted_at`) | [migrations/001_init.sql](../../migrations/001_init.sql) |
| state-machine columns | [migrations/010_state_machine.sql](../../migrations/010_state_machine.sql) |
| session locks | [migrations/057_session_locks.sql](../../migrations/057_session_locks.sql) |
| migrations ledger | [migrations/000_fix_corrections_collision.sql](../../migrations/000_fix_corrections_collision.sql) and ordered `NNN_*.sql` |

## Key constants & invariants

| Constant | Value | Source |
|---|---|---|
| `MAX_CONCURRENT_SESSIONS` | 3 | [app/config.py:46](../../app/config.py#L46) |
| `MAX_QUEUE_LENGTH` | 10 | [app/config.py:47](../../app/config.py#L47) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 480 | [app/config.py:43](../../app/config.py#L43) |
| `LEGACY_ADMIN_EMAIL` | `johndean@vin.com` (BR-001) | [app/security/roles.py](../../app/security/roles.py) |
| `SESSION_TRASH_ALLOWED` | `{LEGACY_ADMIN_EMAIL, "carlab@vin.com"}` (BR-002) | [app/api/sessions.py:52](../../app/api/sessions.py#L52) |

- **FSM (BR-007):** the legal path is
  `uploading → transcribing → normalizing → fusing → aligning → ready → complete`
  (`uploading → ready` is the AI-mode direct path; `failed` reachable from any
  non-terminal status; `failed`/`complete` are terminal). Transitions are enforced
  in `app/engines/state_machine.py:40`; valid *values* are additionally enforced by
  the `sessions_status_check` CHECK (migration 010).
- **Soft-delete carve-out (BR-002):** soft-delete/restore is gated to admins and
  one external partner account.
- **Rate-limit slots** are released on task failure; `/v1/diag/clear-rate-limit-slots`
  sweeps orphaned slots that cause spurious `429 RATE_LIMIT_USER`.

## Frontend

`SessionsView.vue` (list) + `SessionDetailView.vue` (detail). Layout SSOT:
`docs/port-source/sessions.jsx`, `docs/port-source/session-detail.jsx`.
