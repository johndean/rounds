-- 029_corrections — append-only correction ledger + undo/redo pointer.
--
-- Consolidates MIC migrations:
--   * base corrections + correction_pointers from MIC schema.sql:132-156
--   * 021_relabel_legacy_operator_corrections (no-op for fresh deploys)
--   * 024_add_chat_correction_types     (added chat_insert/chat_remove)
--   * 026_add_poll_correction_types     (added poll_insert/poll_remove)
--   * 027_add_speaker_reassignment      (added speaker_reassignment)
--   * 028_add_chat_edit_correction_type (added chat_edit — final form)
--
-- Phase 4 of audit remediation. Invariant: corrections are APPEND-ONLY.
-- UPDATE / DELETE on this table is forbidden. Undo/redo moves
-- `correction_pointers.current_pointer`; the rows themselves are never
-- mutated.
--
-- DEFENSIVE RESET: the initial deploy of this migration left the DB in
-- a partial state (corrections table existed without sequence_number
-- column — psycopg2 multi-statement execute apparently bailed
-- mid-CREATE on the first attempt). Drop any prior partial state with
-- CASCADE so the FK on transcription_discrepancies.resolution_correction_id
-- (added later in this file) goes with it, then recreate cleanly. Safe
-- because:
--   • corrections + correction_pointers are new tables — no live data
--   • The 3 ALTER columns on transcription_discrepancies were added by
--     the same failed migration attempt — no live data either
-- DROP CASCADE is idempotent on fresh databases (IF EXISTS).

DROP TABLE IF EXISTS corrections CASCADE;
DROP TABLE IF EXISTS correction_pointers CASCADE;

ALTER TABLE transcription_discrepancies DROP COLUMN IF EXISTS resolution_correction_id;
ALTER TABLE transcription_discrepancies DROP COLUMN IF EXISTS resolved;
ALTER TABLE transcription_discrepancies DROP COLUMN IF EXISTS resolved_at;


-- Rounds schema adaptation vs MIC:
--   • segment_id is UUID NOT NULL (MIC used TEXT — Rounds segments.id is UUID since 001)
--   • old/new_slide_id are UUID REFERENCES slides(id) ON DELETE SET NULL
--     (survives slide deletion since corrections are append-only history)
--   • CASCADE on session_id (matches the rest of Rounds schema)
CREATE TABLE corrections (
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

ALTER TABLE corrections ADD CONSTRAINT corrections_type_enum
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

CREATE INDEX corrections_session_idx        ON corrections (session_id);
CREATE INDEX corrections_session_seq_idx    ON corrections (session_id, sequence_number);
CREATE INDEX corrections_session_action_idx ON corrections (session_id, action_id);
CREATE INDEX corrections_segment_idx        ON corrections (segment_id);


CREATE TABLE correction_pointers (
    session_id      UUID PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    current_pointer INTEGER NOT NULL DEFAULT -1,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- transcription_discrepancies needs resolved + resolution_correction_id
-- so apply_correction (text_edit / mark_ok on a flagged segment) can mark
-- the discrepancy resolved and back-link to the closing correction.
ALTER TABLE transcription_discrepancies
    ADD COLUMN resolved                 BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE transcription_discrepancies
    ADD COLUMN resolution_correction_id UUID    REFERENCES corrections(id) ON DELETE SET NULL;
ALTER TABLE transcription_discrepancies
    ADD COLUMN resolved_at              TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS transcription_discrepancies_unresolved_idx
    ON transcription_discrepancies (session_id) WHERE resolved = FALSE;
