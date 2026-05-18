-- 015_words — words table for per-token timestamps + confidence.
--
-- Closes audit gap 🟠 #5 (no per-word data persistence). Phase 6j / U113.
--
-- Rounds keeps segments.id as UUID rather than MIC's TEXT/SHA256 form; the
-- deterministic-ID benefit is achieved by enforcing UNIQUE (session_id, seq)
-- (already on segments since 001_init). Reruns with the same (sid, seq) hit
-- the conflict and update existing rows.

CREATE TABLE IF NOT EXISTS words (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_id  UUID        NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    seq         INTEGER     NOT NULL,                        -- ordering within segment
    word        TEXT        NOT NULL,
    start_ms    INTEGER     NOT NULL,
    end_ms      INTEGER     NOT NULL,
    confidence  REAL        NOT NULL DEFAULT 0.85 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    UNIQUE (segment_id, seq)
);

CREATE INDEX IF NOT EXISTS words_segment_idx ON words (segment_id);
