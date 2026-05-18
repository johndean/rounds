-- 029_corrections — Phase 4 MIC-parity append-only correction ledger.
--
-- TABLE NAME COLLISION FIX: migration 002 already declares a table called
-- `corrections` (with columns actor_email/kind/was/now_/occurred_at) used
-- by app/api/segments.py + audit.py for inline-save edit logging. The
-- first version of this migration tried to take the same name and
-- collided — partial state from those failed deploys is cleaned up by
-- the DO block below.
--
-- This migration creates Phase 4's MIC-parity tables under DIFFERENT
-- names so both schemas coexist:
--   • correction_ledger  — Phase 4 MIC-parity append-only ledger
--   • ledger_pointers    — Phase 4 undo/redo pointer
--   • 002's corrections  — legacy edit-log (preserved verbatim)
--
-- segments.py + audit.py will be migrated to correction_ledger in a
-- follow-up scope; until then both schemas coexist.
--
-- Consolidates MIC migrations: schema.sql:132-156 base + 024 + 026 + 027 + 028
-- (final 11-type enum). Invariant: APPEND-ONLY. UPDATE/DELETE forbidden.

-- ───────────────────────────────────────────────────────────────────────
-- STEP 1 — clean up partial state from prior failed deploy attempts.
-- Idempotent: no-op on fresh databases.
-- ───────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    -- If `corrections` exists with Phase 4 schema (no occurred_at column —
    -- only the failed-deploy state would look like this), drop it so
    -- migration 002 can re-create its legacy version on this deploy.
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

    -- Drop the orphan Phase 4 pointer table if it exists under the old name.
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'correction_pointers'
    ) THEN
        DROP TABLE correction_pointers CASCADE;
    END IF;

    -- Drop transcription_discrepancies columns added by failed-deploy
    -- attempts (FK targeted the wrong corrections table; CASCADE above
    -- already dropped the FK constraint, but the column remains until
    -- explicitly dropped).
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'transcription_discrepancies'
           AND column_name = 'resolution_correction_id'
    ) THEN
        ALTER TABLE transcription_discrepancies DROP COLUMN resolution_correction_id;
    END IF;

    -- The other two columns (resolved + resolved_at) don't need explicit
    -- handling — ADD COLUMN IF NOT EXISTS below is idempotent. Drop them
    -- anyway for cleanliness, since their values would carry leftover
    -- state from a partial run.
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


-- ───────────────────────────────────────────────────────────────────────
-- STEP 2 — create Phase 4's MIC-parity tables under their distinct names.
-- Idempotent via CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
-- ───────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS correction_ledger (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    segment_id      UUID NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    correction_type TEXT NOT NULL,
    old_slide_id    UUID REFERENCES slides(id) ON DELETE SET NULL,
    new_slide_id    UUID REFERENCES slides(id) ON DELETE SET NULL,
    old_text        TEXT,
    new_text        TEXT,
    applied_by      TEXT NOT NULL DEFAULT 'operator',
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    action_id       UUID NOT NULL,
    sequence_number INTEGER NOT NULL
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
         WHERE constraint_schema = 'public' AND constraint_name = 'correction_ledger_type_enum'
    ) THEN
        ALTER TABLE correction_ledger ADD CONSTRAINT correction_ledger_type_enum
            CHECK (correction_type IN (
                'slide_reassignment',
                'text_edit',
                'split',
                'merge',
                'mark_ok',
                'chat_insert',
                'chat_edit',
                'chat_remove',
                'poll_insert',
                'poll_remove',
                'speaker_reassignment'
            ));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS correction_ledger_session_idx        ON correction_ledger (session_id);
CREATE INDEX IF NOT EXISTS correction_ledger_session_seq_idx    ON correction_ledger (session_id, sequence_number);
CREATE INDEX IF NOT EXISTS correction_ledger_session_action_idx ON correction_ledger (session_id, action_id);
CREATE INDEX IF NOT EXISTS correction_ledger_segment_idx        ON correction_ledger (segment_id);


CREATE TABLE IF NOT EXISTS ledger_pointers (
    session_id      UUID PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    current_pointer INTEGER NOT NULL DEFAULT -1,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ───────────────────────────────────────────────────────────────────────
-- STEP 3 — augment transcription_discrepancies for discrepancy resolution.
-- ADD COLUMN IF NOT EXISTS is idempotent.
-- ───────────────────────────────────────────────────────────────────────
ALTER TABLE transcription_discrepancies
    ADD COLUMN IF NOT EXISTS resolved BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE transcription_discrepancies
    ADD COLUMN IF NOT EXISTS resolution_correction_id UUID
        REFERENCES correction_ledger(id) ON DELETE SET NULL;
ALTER TABLE transcription_discrepancies
    ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS transcription_discrepancies_unresolved_idx
    ON transcription_discrepancies (session_id) WHERE resolved = FALSE;
