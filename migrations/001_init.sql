-- 001_init — core session + ingestion tables for Rounds.
--
-- Mirrors MIC's session graph (sessions → sources → segments + slides + speakers).
-- All tables are idempotent (CREATE IF NOT EXISTS) so migrate.py replays safely.
--
-- Extensions:
--   pgcrypto   — gen_random_uuid()
--   vector     — pgvector (installed by user via use-railway pg-extensions.py)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ─── sessions ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT        NOT NULL UNIQUE,                  -- e.g. "VIN-2026-001"
    title           TEXT        NOT NULL,
    presenter       TEXT,
    recorded_at     TIMESTAMPTZ,
    duration_sec    INTEGER,
    attendee_count  INTEGER,
    word_count      INTEGER,
    segment_count   INTEGER,
    taxonomy        JSONB       NOT NULL DEFAULT '[]'::jsonb,     -- ["Surgery", "Oncology", ...]
    status          TEXT        NOT NULL DEFAULT 'ingesting',     -- ingesting | ready | failed | archived
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sessions_status_idx       ON sessions (status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS sessions_recorded_at_idx  ON sessions (recorded_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS sessions_code_lower_idx   ON sessions (lower(code));

-- ─── sources ─────────────────────────────────────────────────────────────
-- One row per uploaded artifact (video, slide deck, manifest, supplementary audio).
CREATE TABLE IF NOT EXISTS sources (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role            TEXT        NOT NULL,                          -- video | slide | manifest | audio_enhance | other
    filename        TEXT        NOT NULL,
    gcs_uri         TEXT        NOT NULL,
    content_type    TEXT,
    size_bytes      BIGINT,
    duration_sec    INTEGER,                                       -- video/audio only
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sources_session_idx        ON sources (session_id);
CREATE INDEX IF NOT EXISTS sources_session_role_idx   ON sources (session_id, role);
CREATE UNIQUE INDEX IF NOT EXISTS sources_gcs_uri_uq  ON sources (gcs_uri);

-- ─── slides ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS slides (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    slide_index     INTEGER     NOT NULL,                          -- 0-based, matches SLIDE_PALETTE
    title           TEXT,
    image_uri       TEXT,                                          -- gcs path for slide thumb
    start_ms        INTEGER,                                       -- inferred from alignment
    end_ms          INTEGER,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (session_id, slide_index)
);

CREATE INDEX IF NOT EXISTS slides_session_idx ON slides (session_id);

-- ─── speakers ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS speakers (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    name            TEXT        NOT NULL,
    role            TEXT,                                          -- "Instructor", "Q&A", "Moderator", etc
    avatar_color    TEXT,                                          -- hex from SLIDE_PALETTE or override
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS speakers_session_idx ON speakers (session_id);

-- ─── segments ────────────────────────────────────────────────────────────
-- One row per AI-mode segment (also covers STT chunks via metadata.kind).
CREATE TABLE IF NOT EXISTS segments (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    slide_id            UUID        REFERENCES slides(id)   ON DELETE SET NULL,
    speaker_id          UUID        REFERENCES speakers(id) ON DELETE SET NULL,
    seq                 INTEGER     NOT NULL,                      -- ordering within session
    start_ms            INTEGER     NOT NULL,
    end_ms              INTEGER     NOT NULL,
    text                TEXT        NOT NULL,
    confidence          REAL,                                      -- 0..1
    flags               JSONB       NOT NULL DEFAULT '[]'::jsonb,  -- ["medication","filler",...]
    is_anchor           BOOLEAN     NOT NULL DEFAULT FALSE,         -- poll/chat anchor blocks
    anchor_kind         TEXT,                                       -- "poll" | "chat" | NULL
    metadata            JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, seq)
);

CREATE INDEX IF NOT EXISTS segments_session_idx              ON segments (session_id);
CREATE INDEX IF NOT EXISTS segments_session_seq_idx          ON segments (session_id, seq);
CREATE INDEX IF NOT EXISTS segments_session_slide_idx        ON segments (session_id, slide_id);
CREATE INDEX IF NOT EXISTS segments_session_speaker_idx      ON segments (session_id, speaker_id);
CREATE INDEX IF NOT EXISTS segments_session_anchor_idx       ON segments (session_id) WHERE is_anchor = TRUE;
