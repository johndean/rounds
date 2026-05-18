-- 019_iil_learning — instructor profiles + key points + patterns.
--
-- Closes audit gap 🟠 #2 (no IIL learning loop). Phase 6q / U146.

CREATE TABLE IF NOT EXISTS instructor_profiles (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT        NOT NULL UNIQUE,
    credentials     TEXT,
    bio             TEXT,
    -- IIL signals learned across sessions
    avg_filler_rate REAL,
    avg_session_min INTEGER,
    preferred_template_id TEXT REFERENCES templates(id),
    sample_count    INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS session_instructor_map (
    session_id      UUID        PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    instructor_id   UUID        NOT NULL REFERENCES instructor_profiles(id),
    matched_by      TEXT        NOT NULL,    -- 'manifest' | 'manual' | 'auto'
    confidence      REAL        NOT NULL DEFAULT 1.0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS session_patterns (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    pattern_name    TEXT        NOT NULL,
    frequency       INTEGER     NOT NULL DEFAULT 1,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, pattern_name)
);

CREATE TABLE IF NOT EXISTS key_points_annotations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    segment_id      UUID        REFERENCES segments(id) ON DELETE CASCADE,
    label           TEXT        NOT NULL,
    score           REAL        NOT NULL DEFAULT 0.5,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS instructor_profiles_name_lower_idx ON instructor_profiles (lower(name));
CREATE INDEX IF NOT EXISTS session_patterns_session_idx ON session_patterns (session_id);
CREATE INDEX IF NOT EXISTS key_points_annotations_session_idx ON key_points_annotations (session_id);
