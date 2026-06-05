# ADR-002 — Session lifecycle: soft-delete + status FSM

- **Status:** Accepted
- **Date:** 2026-05-17 (bootstrap), refined 2026-06-05
- **Deciders:** johndean@vin.com
- **Related:** [BR-002](../BUSINESS_RULES.md#br-002), [BR-007](../BUSINESS_RULES.md#br-007), [ADR-003](./ADR-003-fsm-python-only.md), [ADR-005](./ADR-005-corrections-ledger.md)

## Context

A Rounds session is the central domain object — a recorded round + slides + transcript + corrections + exports. The lifecycle has hard requirements:

1. **Audit retention.** A deleted session must remain forensically recoverable for some period (deletes from clinical-adjacent systems are notoriously regretted).
2. **Single source of truth for state.** A session can be `uploading`, `ingesting`, `processing`, `ready`, `published`, `archived`, or `failed`. Tasks across Celery workers + the API + the editor all need to agree on the current state.
3. **Operator escape hatch.** An operator must be able to push a failed session back into the pipeline (`/v1/diag/reingest/*`) without bypassing every safety check downstream.

## Decision

**Soft-delete + an explicit state machine; `sessions.deleted_at` and `sessions.status` are the two lifecycle columns.**

- `sessions.deleted_at` is `NULL` for live rows. A soft-delete sets it to `now()`. A purge `DELETE`s the row.
- Restore clears `deleted_at` back to `NULL`.
- Soft-delete + restore + purge are gated to the [BR-002](../BUSINESS_RULES.md#br-002) allow-list (`SESSION_TRASH_ALLOWED`).
- `sessions.status` is a text column constrained at the application level by `ALLOWED_TRANSITIONS` in `app/engines/state_machine.py` — see [BR-007](../BUSINESS_RULES.md#br-007).
- Every state move flows through `ensure_can_transition(current, target)` which raises `MICException(STATE_ILLEGAL_TRANSITION)` on a bad move.
- The `failed → ingesting | processing` escape hatch exists only for the diag routes (operator rescue).

## Consequences

- **Positive.**
  - A user-mistake delete is reversible without restoring from backup.
  - Every state move has one chokepoint — easier to audit, easier to extend.
  - Operators can rescue stuck sessions without bypassing alignment / fusion.
- **Negative.**
  - `sessions.status` has no DB CHECK constraint, so a hand-written SQL update can land an invalid state (see [ADR-003](./ADR-003-fsm-python-only.md) for why and what would be required to harden).
  - `deleted_at` filters add a `WHERE deleted_at IS NULL` to every list query — easy to forget. We have one canonical helper but it is a discipline pattern, not a schema-enforced constraint.
- **Risks.**
  - Long-retained soft-deleted rows accumulate storage. No retention sweeper exists yet.
  - The escape-hatch transitions out of `failed` are powerful — a misuse could re-run a task that has already partially populated downstream tables.

## Code locations

- `app/engines/state_machine.py` — `ALLOWED_TRANSITIONS`, `ensure_can_transition`, `current_state`
- `app/api/sessions.py:611` — soft-delete endpoint, gates on `SESSION_TRASH_ALLOWED`
- `app/api/sessions.py:36` — `SESSION_TRASH_ALLOWED` definition ([BR-002](../BUSINESS_RULES.md#br-002))
- `app/api/diagnostics.py:435` — `/v1/diag/reingest/<id>` uses the escape-hatch transition
- `migrations/` — schema (no CHECK constraint on `sessions.status`; see [ADR-003](./ADR-003-fsm-python-only.md))

## Alternatives considered

1. **Hard-delete only** — rejected because user-error deletes happen and restore-from-backup is a multi-hour ops task per row.
2. **Soft-delete with a separate `sessions_trash` table** — rejected because the same row continues to be referenced by `segments`, `slides`, `corrections`, `discrepancies`, etc. Moving it would require either FK rewrites or shadow tables for every child.
3. **`sessions.status` as a Postgres ENUM** — considered. Rejected at bootstrap because adding a value to a Postgres ENUM is non-trivial (requires `ALTER TYPE ... ADD VALUE` outside a transaction). The TEXT-with-FSM approach trades schema enforcement for migration agility. See [ADR-003](./ADR-003-fsm-python-only.md) for the trade-off review.
4. **State stored as a join to a `session_state_events` log** — rejected as over-engineered for the current scale. We get auditability from `audit_events` instead.

## When this ADR should be revisited

- If a state-corruption bug ships and the absence of a CHECK constraint enables it — then [ADR-003](./ADR-003-fsm-python-only.md) is the candidate for supersession.
- If a retention policy is established (HIPAA / GDPR / clinical-archive) — a deletion sweeper for soft-deleted rows becomes a follow-on.
