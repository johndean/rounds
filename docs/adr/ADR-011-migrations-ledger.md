# ADR-011 — Append-only schema_migrations ledger (post-bootstrap)

- **Status:** Accepted
- **Date:** 2026-05-17 (initial), refined 2026-06-05
- **Deciders:** johndean@vin.com
- **Related:** [ADR-002](./ADR-002-session-lifecycle.md), [ADR-003](./ADR-003-fsm-python-only.md), [ADR-005](./ADR-005-corrections-ledger.md)

## Context

Rounds' schema is shipped as numbered SQL files in `migrations/` (`000_*.sql` through `052_*.sql` at HEAD `56eb009` = 53 files). Each file is idempotent — every `CREATE` uses `IF NOT EXISTS` and every `ALTER` checks for existing state before applying.

Two design questions had to be resolved:

1. **Tracking** — how do we know which migrations have been applied to a given database?
2. **Reversibility** — do we ship down-migrations?

The MIC migration record gave precedent: numbered files, idempotent SQL, no down-migrations. Rounds inherited that posture and refined it post-bootstrap.

## Decision

**An append-only `schema_migrations` table records every applied migration; no down-migrations exist.**

- Migrations are numbered files in `migrations/<NNN>_<slug>.sql`. NNN is monotone-increasing; gaps are not allowed.
- The applier (`app/db/migrations.py`) reads `migrations/`, sorts by NNN, and for each file:
  1. Checks the `schema_migrations` table for the slug.
  2. If absent, applies the file inside a transaction.
  3. Records `(migration_id, applied_at)` in `schema_migrations` on success.
- Every migration file uses `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE … ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, etc. Idempotency is the file's responsibility — if it errors mid-run, re-running must be safe.
- **No down-migrations are written or maintained.** If a schema change needs to be reversed, the reversal is written as a new forward migration with a higher NNN.

## Consequences

- **Positive.**
  - Re-running the applier is always safe.
  - The schema's history is auditable from `migrations/` (chronological) + `schema_migrations` (per-database state).
  - No matrix of "which down-migrations are compatible with which up-migrations" to maintain.
- **Negative.**
  - **No rollback safety net.** A migration that ships data corruption requires a hand-authored forward migration to repair, not a `down()` that magically reverts.
  - Idempotency is a discipline — a migration that forgets `IF NOT EXISTS` doesn't fail in the author's environment (clean DB) but fails everywhere else.
  - A migration with a hardcoded value (e.g. backfilling enum values) can drift from the live data over time without a clean way to verify.
- **Risks.**
  - A production migration that takes longer than the Railway deploy window blocks the deploy. Long-running migrations need to be authored carefully (e.g. `CREATE INDEX CONCURRENTLY` instead of `CREATE INDEX`).
  - The `schema_migrations` ledger has no checksum — a migration file edited after deploy isn't re-applied (because the slug still matches). Author discipline is the only guard.

## Code locations

- `migrations/` — 53 SQL files at HEAD `56eb009`
- `migrations/000_*.sql` — schema bootstrap (creates `schema_migrations`)
- `app/db/migrations.py` — applier
- `app/main.py` — does NOT auto-apply on boot; migrations run in a separate `scripts/migrate.py` invocation as part of Railway's deploy command

## Alternatives considered

1. **Alembic** — viable; rejected because (a) the inherited MIC posture was raw SQL, (b) Alembic's autogeneration adds a SQLAlchemy-model dependency that Rounds' migrations don't need, (c) the raw-SQL approach is more transparent for reviewers reading the migration history.
2. **Hash-based migration ledger** — would catch post-deploy edits to a migration file. Considered; deferred because the dev process today doesn't edit applied migrations.
3. **Down-migrations** — rejected because the operational reality is that reversing a production schema change is almost always done with a hand-authored forward migration anyway; maintaining down-migrations for change events that may not happen is over-investment.

## When this ADR should be revisited

- If a migration ships that corrupts data and the lack of an automated rollback path becomes the incident's primary lesson.
- If the team grows to a size where a migration framework's autogeneration / hash-checking pays off.
- If a regulatory audit demands provable migration immutability — add a hash column to `schema_migrations` and verify on apply.
