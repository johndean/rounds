-- 010_state_machine — status enum CHECK + session_audit table.
--
-- Closes audit gaps:
--   🟠 #1   sessions.status has no CHECK constraint
--   🔴 #11  No state machine — raw UPDATE sessions SET status= is unrestricted
--   🟡 #4   No append-only audit log on transitions
--
-- Phase 6b / U78-U81.

-- Status enum aligned to MIC SSOT, with `ingesting` retained as legacy alias
-- of `uploading` (the pre-6b Rounds default — backfilled below).
-- Adding via CHECK on the existing column. Postgres will scan all rows on
-- the constraint add; on a small table this is fine. Drop any prior CHECK
-- to keep migration idempotent.
ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_status_check;

-- Normalize legacy 'ingesting' → 'uploading' so the constraint can be added
-- without rejecting historic rows.
UPDATE sessions SET status = 'uploading' WHERE status = 'ingesting';

ALTER TABLE sessions
    ADD CONSTRAINT sessions_status_check
    CHECK (status IN (
        'uploading', 'transcribing', 'normalizing',
        'fusing', 'aligning', 'ready', 'complete', 'failed'
    ));

-- ─── session_audit ──────────────────────────────────────────────────────
-- Append-only processing log per session. One row per session — log JSONB
-- accumulates {ts, prev, next, actor, reason} entries.
CREATE TABLE IF NOT EXISTS session_audit (
    session_id     UUID        PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    processing_log JSONB       NOT NULL DEFAULT '[]'::jsonb,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS session_audit_updated_idx ON session_audit (updated_at DESC);

-- Backfill — one row per existing session.
INSERT INTO session_audit (session_id, processing_log)
SELECT s.id, '[]'::jsonb
FROM sessions s
LEFT JOIN session_audit sa ON sa.session_id = s.id
WHERE sa.session_id IS NULL;
