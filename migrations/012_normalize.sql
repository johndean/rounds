-- 012_normalize — normalization_results + extend templates.
--
-- Closes audit gap 🔴 #5 (no filler removal / IIL tiers / template-driven rewrite).
-- Phase 6g / U98-U102.

ALTER TABLE templates ADD COLUMN IF NOT EXISTS filler_words JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Backfill filler_words for the seed templates (idempotent).
UPDATE templates SET filler_words = CAST(:fw AS jsonb)
  WHERE id = 'lecture_v1' AND filler_words = '[]'::jsonb;
-- Postgres doesn't bind ":fw" in raw SQL — inline literal arrays per template:
UPDATE templates SET filler_words = '["um","uh","er","ah","hm","mm"]'::jsonb
  WHERE id = 'lecture_v1' AND filler_words = '[]'::jsonb;
UPDATE templates SET filler_words = '["um","uh","you know","basically"]'::jsonb
  WHERE id = 'training_v1' AND filler_words = '[]'::jsonb;
UPDATE templates SET filler_words = '["um","uh"]'::jsonb
  WHERE id = 'technical_v1' AND filler_words = '[]'::jsonb;
UPDATE templates SET filler_words = '["um","uh"]'::jsonb
  WHERE id = 'podcast_v1' AND filler_words = '[]'::jsonb;
UPDATE templates SET filler_words = '["um","uh"]'::jsonb
  WHERE id = 'sales_v1' AND filler_words = '[]'::jsonb;

CREATE TABLE IF NOT EXISTS normalization_results (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    segment_id          UUID        NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    normalized_text     TEXT        NOT NULL,
    template_id         TEXT        NOT NULL REFERENCES templates(id),
    validation_results  JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, segment_id)
);

CREATE INDEX IF NOT EXISTS normalization_session_idx ON normalization_results (session_id);
