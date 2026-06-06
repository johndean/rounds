-- 057_session_locks.sql — concurrent-edit lock for the session editor.
--
-- Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 1.
-- Audit IDs closed: E1 (silent concurrent-edit overwrite).
--
-- Shape: one row per session that's actively being edited. Heartbeat keeps
-- the lock alive (default TTL = 90s = 3 missed heartbeats). When tab closes
-- cleanly, frontend POSTs /release. When the heartbeat ages out, the lock
-- is considered stale and another user can force-take it.
--
-- Idempotency: PK on session_id means acquire is a single UPSERT.
-- Forward-only per ADR-011: no UNIQUE add, no destructive alter.

CREATE TABLE IF NOT EXISTS session_locks (
    session_id     UUID         PRIMARY KEY,
    user_email     TEXT         NOT NULL,
    acquired_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    heartbeat_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at     TIMESTAMPTZ  NOT NULL DEFAULT (now() + INTERVAL '90 seconds')
);

-- Sweep stale locks via this index. NOT a UNIQUE — just a lookup helper for
-- the operator dashboard + future cron sweeper.
CREATE INDEX IF NOT EXISTS idx_session_locks_expires_at
    ON session_locks (expires_at);
