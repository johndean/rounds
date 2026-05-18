-- 016_bullets — bullets table + slides full_text/slide_number.
--
-- Closes audit gap 🟠 #17 (no bullets, slide_extract is PNG-only).
-- Phase 6k / U117.

ALTER TABLE slides ADD COLUMN IF NOT EXISTS full_text     TEXT;
ALTER TABLE slides ADD COLUMN IF NOT EXISTS thumbnail_uri TEXT;

CREATE TABLE IF NOT EXISTS bullets (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    slide_id    UUID        NOT NULL REFERENCES slides(id) ON DELETE CASCADE,
    text        TEXT        NOT NULL,
    position    INTEGER     NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (slide_id, position)
);

CREATE INDEX IF NOT EXISTS bullets_slide_idx ON bullets (slide_id, position);
