-- 018_artifacts — generated artifacts table.
--
-- Closes audit gap 🟠 #11 (artifact_transformer not ported, burn captions missing).
-- Phase 6p / U141-U145.

CREATE TABLE IF NOT EXISTS artifacts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    kind            TEXT        NOT NULL,         -- docx | srt | vtt | txt | zip | captioned_video
    gcs_uri         TEXT,
    bytes           BIGINT,
    generated_by    TEXT,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, kind)
);

CREATE INDEX IF NOT EXISTS artifacts_session_idx ON artifacts (session_id);
