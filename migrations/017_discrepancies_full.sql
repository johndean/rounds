-- 017_discrepancies_full — transcription_discrepancies table.
--
-- Closes audit gap 🟠 #16 (classify task missing). Phase 6l / U122.
--
-- Distinct from the existing `discrepancies` table (which is for the editor
-- Discrepancies tab and is keyed by segment + slide). This table is the
-- per-word LCS-detected diff between raw STT and normalized text.

CREATE TABLE IF NOT EXISTS transcription_discrepancies (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    segment_id      UUID        REFERENCES segments(id) ON DELETE CASCADE,
    ai_text         TEXT,                                       -- normalized version
    stt_text        TEXT,                                       -- raw STT version
    category        TEXT,                                       -- medication | terminology | filler | punctuation | drift | low_confidence | other
    is_meaningful   BOOLEAN,                                    -- NULL until classify runs
    classifier_model TEXT,
    classified_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS transcription_discrepancies_session_idx ON transcription_discrepancies (session_id);
CREATE INDEX IF NOT EXISTS transcription_discrepancies_unclassified_idx
    ON transcription_discrepancies (session_id) WHERE is_meaningful IS NULL;
