-- 011_manifest — manifest-parsed speakers/resources/polls and session columns.
--
-- Closes audit gap 🔴 #4 (manifest never parsed — speakers/polls/links never populate).
-- Phase 6f / U93-U97.

-- ─── session metadata columns from extras2.txt ──────────────────────────
-- These map to ParsedManifest.{code, title_long, title_short, ce_broker_id,
-- class_id, tags, publishing_links, polls, polls_parsed}. `code` already
-- exists on sessions. Others are new.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS title_long       TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS title_short      TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS ce_broker_id     TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS class_id         TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS tags             JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS publishing_links JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS polls_raw        TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS polls_parsed     JSONB NOT NULL DEFAULT '[]'::jsonb;

-- ─── session_speakers ───────────────────────────────────────────────────
-- One row per speaker parsed from the manifest. Independent of the speakers
-- table which holds runtime AI/STT-detected speakers used by segments.
CREATE TABLE IF NOT EXISTS session_speakers (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role         TEXT        NOT NULL,           -- moderator | primary | guest
    name         TEXT        NOT NULL,
    credentials  TEXT,
    bio          TEXT,
    sort_order   INTEGER     NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS session_speakers_session_idx ON session_speakers (session_id, sort_order);

-- ─── session_slide_resources ────────────────────────────────────────────
-- @N anchored resource links from the manifest's Additional Resources block.
CREATE TABLE IF NOT EXISTS session_slide_resources (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    slide_number INTEGER     NOT NULL,
    label        TEXT,
    url          TEXT        NOT NULL,
    sort_order   INTEGER     NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS session_slide_resources_session_idx ON session_slide_resources (session_id, slide_number);
