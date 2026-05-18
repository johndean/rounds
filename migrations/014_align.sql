-- 014_align — alignments table + validation_results.
--
-- Closes audit gap 🔴 #17 (no real align engine, ALIGN_* weights unread).
-- Phase 6i / U107.

CREATE TABLE IF NOT EXISTS alignments (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    segment_id      UUID        NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    slide_id        UUID        REFERENCES slides(id),
    confidence      REAL        NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    signals         JSONB       NOT NULL,           -- {semantic, coverage, temporal, sequential}
    sources         JSONB       NOT NULL,           -- {visual, anchor, semantic} pass-through
    drift_flag      BOOLEAN     NOT NULL DEFAULT FALSE,
    anchor_hit      BOOLEAN     NOT NULL DEFAULT FALSE,
    uncertain_flag  BOOLEAN     NOT NULL DEFAULT FALSE,
    status          TEXT        NOT NULL CHECK (status IN ('assigned','uncertain','review')),
    attempt_number  INTEGER     NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, segment_id)
);

CREATE INDEX IF NOT EXISTS alignments_session_idx     ON alignments (session_id);
CREATE INDEX IF NOT EXISTS alignments_session_seg_idx ON alignments (session_id, segment_id);
CREATE INDEX IF NOT EXISTS alignments_uncertain_idx   ON alignments (session_id) WHERE uncertain_flag = TRUE;

CREATE TABLE IF NOT EXISTS validation_results (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    alignment_id    UUID        NOT NULL REFERENCES alignments(id) ON DELETE CASCADE,
    verdict         TEXT        NOT NULL CHECK (verdict IN ('APPROVE','REVIEW','ESCALATE')),
    details         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
