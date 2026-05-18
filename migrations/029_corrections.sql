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
-- Phase 4 of audit remediation (Rounds parity-plan-002). Closes audit gaps:
--   • Editor Undo/Redo (Phase 1.2) — now restorable in Phase 4b
--   • FindReplaceModal (Phase 1.1) — restorable in Phase 4b
--   • Inline saves (Phase 1.3) — restorable in Phase 4b
--   • Discrepancy resolution audit trail
--
-- Rounds schema adaptation:
--   • segment_id is UUID NOT NULL REFERENCES segments(id) ON DELETE CASCADE
--     (MIC used TEXT — Rounds segments.id is UUID per migration 001).
--   • old_slide_id / new_slide_id are UUID REFERENCES slides(id) ON DELETE
--     SET NULL — survives the slide being deleted (corrections are append-
--     only history; can't NULL the row but can null the FK).
--
-- Invariant: corrections are APPEND-ONLY. NEVER UPDATE or DELETE a row.
-- Undo/redo moves correction_pointers.current_pointer, never touches rows.

CREATE TABLE IF NOT EXISTS corrections (
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
    sequence_number INTEGER NOT NULL,
    CONSTRAINT corrections_type_enum CHECK (correction_type IN (
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
    ))
);

CREATE INDEX IF NOT EXISTS corrections_session_idx     ON corrections (session_id);
CREATE INDEX IF NOT EXISTS corrections_session_seq_idx ON corrections (session_id, sequence_number);
CREATE INDEX IF NOT EXISTS corrections_session_action_idx ON corrections (session_id, action_id);
CREATE INDEX IF NOT EXISTS corrections_segment_idx     ON corrections (segment_id);


CREATE TABLE IF NOT EXISTS correction_pointers (
    session_id      UUID PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    current_pointer INTEGER NOT NULL DEFAULT -1,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- transcription_discrepancies needs `resolved` + `resolution_correction_id`
-- so apply_correction (text_edit / mark_ok on a flagged segment) can mark
-- the discrepancy resolved and back-link to the correction that closed it.
-- Mirrors MIC schema where these columns existed from day one.
ALTER TABLE transcription_discrepancies
    ADD COLUMN IF NOT EXISTS resolved                 BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS resolution_correction_id UUID    REFERENCES corrections(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS resolved_at              TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS transcription_discrepancies_unresolved_idx
    ON transcription_discrepancies (session_id) WHERE resolved = FALSE;
