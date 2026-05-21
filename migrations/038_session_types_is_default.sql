-- 038_session_types_is_default — Mark one Type as the org default.
--
-- Background: every new session needs a starting Type. Today the
-- frontend hard-codes the string 'default' as the first option, but
-- there's no DB-level guarantee that a row with that code exists or
-- that exactly one default is chosen. MIC parity (sop_types.is_default
-- + partial unique index on TRUE) makes the concept explicit and
-- protects the default row from accidental delete.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, CREATE UNIQUE INDEX IF NOT
-- EXISTS, UPDATE-only-where-needed.

ALTER TABLE session_types
    ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE;

-- At most one row can be the default. Partial unique index lets every
-- non-default row stay FALSE without violating the constraint.
CREATE UNIQUE INDEX IF NOT EXISTS session_types_is_default_uq
    ON session_types (is_default) WHERE is_default = TRUE;

-- Promote the existing 'default' code row (created by 039 seed or by
-- prior org_settings rollout) to is_default=TRUE if no row already is.
UPDATE session_types SET is_default = TRUE
 WHERE code = 'default'
   AND NOT EXISTS (SELECT 1 FROM session_types WHERE is_default = TRUE);
