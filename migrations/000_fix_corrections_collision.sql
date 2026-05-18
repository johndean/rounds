-- 000_fix_corrections_collision — sort-before-001 hotfix.
--
-- WHY THIS RUNS FIRST: alphabetical glob order sorts "000" before "001".
-- An earlier version of migration 029_corrections.sql created a `corrections`
-- table with the Phase 4 MIC-parity schema (sequence_number, correction_type,
-- action_id, etc.) — colliding with migration 002_discrepancies.sql which
-- already declares `corrections` with a legacy edit-log schema (occurred_at,
-- actor_email, was, now_).
--
-- Failed-deploy state to clean up:
--   • `corrections` table exists with Phase 4 schema (no occurred_at column)
--   • `correction_pointers` table exists (Phase 4 originally used this name;
--     029 now uses ledger_pointers)
--   • `transcription_discrepancies.resolution_correction_id` FK targets the
--     wrong corrections table — must be dropped so the new FK (to
--     correction_ledger, added in 029) can replace it.
--
-- After this migration drops the orphans, migration 002 re-creates the
-- legacy `corrections` cleanly, and migration 029 creates
-- `correction_ledger` + `ledger_pointers` under their new distinct names.
--
-- Idempotent: every operation guarded by IF EXISTS — runs once cleanly
-- on partial-state databases, becomes a complete no-op on fresh/healthy
-- databases. Safe to keep in the migration directory permanently.

DO $$
BEGIN
    -- If `corrections` exists with Phase 4 schema (no occurred_at), drop it.
    -- The 002 migration will recreate it with the legacy schema in this
    -- same deploy.
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'corrections'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'corrections'
           AND column_name = 'occurred_at'
    ) THEN
        DROP TABLE corrections CASCADE;
    END IF;

    -- Drop the orphan Phase 4 pointer table (renamed to ledger_pointers in 029).
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'correction_pointers'
    ) THEN
        DROP TABLE correction_pointers CASCADE;
    END IF;

    -- Drop transcription_discrepancies columns whose FK pointed at the
    -- wrong corrections table (CASCADE on the table DROP above already
    -- nuked the FK constraint; the column itself remains until dropped
    -- explicitly). Migration 029 re-adds them with the correct FK
    -- target via ADD COLUMN IF NOT EXISTS.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'transcription_discrepancies'
           AND column_name = 'resolution_correction_id'
    ) THEN
        ALTER TABLE transcription_discrepancies DROP COLUMN resolution_correction_id;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'transcription_discrepancies'
           AND column_name = 'resolved'
    ) THEN
        ALTER TABLE transcription_discrepancies DROP COLUMN resolved;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'transcription_discrepancies'
           AND column_name = 'resolved_at'
    ) THEN
        ALTER TABLE transcription_discrepancies DROP COLUMN resolved_at;
    END IF;
END $$;
