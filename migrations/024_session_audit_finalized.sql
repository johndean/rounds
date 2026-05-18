-- 024_session_audit_finalized — add finalized_at column.
--
-- Phase 7i (parity-3): closes 🟡 #80 (state_machine.finalized_at field
-- referenced in code but column doesn't exist). MIC writes finalized_at
-- when a session reaches ready — Rounds needs the same field to support
-- duration metrics + UI ready-timestamp display.

ALTER TABLE session_audit ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS session_audit_finalized_idx
    ON session_audit (finalized_at DESC)
    WHERE finalized_at IS NOT NULL;
