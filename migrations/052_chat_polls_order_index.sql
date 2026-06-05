-- 052_chat_polls_order_index — Phase 6 of the 2026-06-04 stakeholder
-- remediation. Adds an `order_index INTEGER` nullable column to
-- chat_messages + polls so operators can drag-reorder rows within a
-- session's right-rail Chat / Polls tabs without losing the original
-- arrival-time ordering for un-reordered rows.
--
-- Backwards-compat strategy:
--   * order_index NULL for all existing rows (no migration of data).
--   * list endpoints use COALESCE(order_index, sent_at_ms) /
--     COALESCE(order_index, opened_at_ms) so un-reordered rows still
--     appear in chronological order.
--   * Drag-reorder sets order_index for every row in the list, in
--     ascending positional order (1, 2, 3, ...). The first reorder
--     promotes all rows to explicit order_index; subsequent reorders
--     only need to renumber. Operators can't end up in a half-NULL,
--     half-set state because the bulk endpoint is all-or-nothing.
--
-- No partial unique index on (session_id, order_index) — the bulk
-- endpoint is the only writer and assigns deterministic values, so
-- duplicates would require a backend bug rather than a race.

ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS order_index INTEGER;

ALTER TABLE polls
    ADD COLUMN IF NOT EXISTS order_index INTEGER;

-- Indexes to keep ORDER BY cheap on large sessions (chat threads can
-- exceed 100 rows; the COALESCE in the list query benefits from an
-- index on each ordering column individually).
--
-- CREATE INDEX CONCURRENTLY (2026-06-05): chat_messages + polls are
-- live operational tables that receive writes during pipeline runs;
-- a plain CREATE INDEX takes ACCESS EXCLUSIVE on the table for the
-- duration of the build, blocking inserts. CONCURRENTLY trades a
-- two-pass build (slower wall-clock) for lock-light behavior. Safe
-- to use here because scripts/migrate.py runs with autocommit=True,
-- which is required (CONCURRENTLY cannot run inside a transaction).
-- IF NOT EXISTS is supported on CONCURRENTLY since PostgreSQL 9.5
-- and keeps the migration idempotent for re-runs on dev DBs.
--
-- This migration was originally shipped with non-concurrent CREATE
-- INDEX and applied to production while the tables were small; the
-- production indexes are already healthy and the schema_migrations
-- ledger records 052 as applied. This edit is forward-fix only: it
-- (a) demonstrates the correct pattern for future migrations that
-- add indexes to populated tables, and (b) makes a fresh dev DB run
-- the lock-light path. Existing prod state is unaffected because
-- the runner is name-based (no content-hash re-apply).
CREATE INDEX CONCURRENTLY IF NOT EXISTS chat_messages_order_idx
    ON chat_messages (session_id, order_index)
    WHERE order_index IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS polls_order_idx
    ON polls (session_id, order_index)
    WHERE order_index IS NOT NULL;
