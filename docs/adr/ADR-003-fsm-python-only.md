# ADR-003 — State machine: Python-only enforcement (no DB CHECK)

- **Status:** Accepted
- **Date:** 2026-05-17 (bootstrap), refined 2026-06-05
- **Deciders:** johndean@vin.com
- **Related:** [BR-007](../BUSINESS_RULES.md#br-007), [ADR-002](./ADR-002-session-lifecycle.md), [ADR-011](./ADR-011-migrations-ledger.md)

## Context

[ADR-002](./ADR-002-session-lifecycle.md) chose a state machine for session lifecycle. The follow-on question: **enforce the FSM at the database level (CHECK constraint, Postgres ENUM) or only at the application level?**

The trade-offs:

- Database enforcement catches **every** bad write, including hand-issued SQL, future migrations that backfill data, or a downstream job that forgets to use the helper. It is the only thing that survives a buggy code path.
- Application enforcement is **cheap to evolve.** Adding `under_review` to `ALLOWED_TRANSITIONS` is a one-line code change with no migration. Adding it to a CHECK constraint requires a migration that may rewrite the entire table.

At bootstrap, the state list was actively evolving (3 stage names changed between Phase 1 and Phase 4). A CHECK constraint would have required a migration per change.

## Decision

**The FSM is enforced only in Python.** `sessions.status` is a `TEXT NOT NULL DEFAULT 'ingesting'` column with no CHECK and no ENUM type.

- Every write to `sessions.status` MUST go through `app/engines/state_machine.py::ensure_can_transition`.
- Direct SQL updates to `sessions.status` (operator rescue, migration backfills) are tolerated but each is reviewed on a case-by-case basis.
- The map `ALLOWED_TRANSITIONS` ([BR-007](../BUSINESS_RULES.md#br-007)) is the source of truth.

## Consequences

- **Positive.**
  - Adding a state is a one-line code change in `state_machine.py` — no migration, no table rewrite, no deploy ordering puzzle.
  - The escape-hatch `failed → ingesting | processing` transitions are easy to express; in a CHECK constraint they would either be missing (operator rescue breaks) or open (defeating the constraint).
- **Negative.**
  - **A hand-written SQL update can land an invalid state.** This is the most material drawback: there is no schema-level guard rail.
  - A future migration's backfill that touches `sessions.status` has no DB-level check that it stays inside the allowed set.
  - A test verifying the FSM does not implicitly verify any random database state — it only verifies that code paths going through `ensure_can_transition` behave.
- **Risks.**
  - Silent corruption: a buggy migration sets `status = 'corrupted'` and only the next API call notices because some downstream code doesn't know that status. The corruption may sit in the DB for days.
  - Future regulatory audit that asks "prove no session ever held an undocumented status" cannot be answered from the schema alone — we would need to query historical state from `audit_events`.

## Code locations

- `app/engines/state_machine.py:37–44` — `ALLOWED_TRANSITIONS` map
- `app/engines/state_machine.py` — `ensure_can_transition`, `current_state`
- `migrations/` — every `sessions.status` reference is `TEXT`, no CHECK

## Alternatives considered

1. **`sessions.status` as a Postgres ENUM** — rejected because adding a value to an ENUM is `ALTER TYPE ... ADD VALUE 'new'` outside a transaction, with the deploy ordering risk that a node running pre-migration code can't see the new value. The state list was still fluid at bootstrap.
2. **`CHECK (status IN ('uploading','ingesting',…))`** — viable today. Postponed because (a) we need to be confident the state list has stopped evolving, (b) backfill verification against historical rows is required, (c) one migration that adds the constraint is one deploy that can fail if any legacy row has a non-conforming value.
3. **State as a foreign key to a `session_states` lookup table** — rejected as over-indexed for a discrete 7-state finite machine.

## When this ADR should be revisited

- When the state list stops evolving for >3 months. Then a CHECK constraint becomes cheap to add.
- If a state-corruption incident traces back to a code path that bypassed `ensure_can_transition` — that's the forcing function for a CHECK migration.
- A future ADR would supersede this one to add the CHECK constraint + migration + backfill verifier.

## Hardening checklist (deferred work)

If we ever decide to add DB-level enforcement, the work would be:

1. Verify every existing `sessions.status` value is inside `ALLOWED_TRANSITIONS.keys() ∪ {"published","archived"}`.
2. Author a migration adding `CHECK (status IN (…))`.
3. Migration runs `IF EXISTS` so it is idempotent and safe to re-run.
4. Add a test that the migration's expected set matches `ALLOWED_TRANSITIONS.keys()` (single source of truth).
5. Document in `CLAUDE.md` that hand-written SQL updates to `sessions.status` are no longer tolerated.
