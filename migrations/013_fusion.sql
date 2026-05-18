-- 013_fusion — slide_time_ranges + replay_log.
--
-- Closes audit gap 🔴 #6 (fusion engine + LOCKED FUSION_WEIGHT_* unread).
-- Phase 6h / U103.

CREATE TABLE IF NOT EXISTS slide_time_ranges (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    slide_id            UUID        REFERENCES slides(id) ON DELETE CASCADE,
    start_time          REAL        NOT NULL,
    end_time            REAL        NOT NULL,
    slide_soft_start    REAL        NOT NULL,
    slide_soft_end      REAL        NOT NULL,
    confidence          REAL        NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    sources             JSONB       NOT NULL,         -- {visual, anchor, semantic} contributions
    status              TEXT        NOT NULL,
    attempt_number      INTEGER     NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS slide_time_ranges_session_idx ON slide_time_ranges (session_id, start_time);

-- replay_log — append-only fusion replay record (Rule 6 in MIC CLAUDE.md §12).
CREATE TABLE IF NOT EXISTS replay_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    input_hash      TEXT        NOT NULL,
    fusion_inputs   JSONB       NOT NULL,
    fusion_output   JSONB       NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS replay_log_session_idx ON replay_log (session_id, created_at DESC);
