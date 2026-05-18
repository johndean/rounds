-- 025_kp_annotations_kp04 — KP-04/07/08/09 schema.
--
-- Phase 7i (parity-3): closes 🟠 #47 + #49 — KP engine port. MIC §25 stores
-- key_points as JSONB array (max 5 items; KP-07/08), with explanation,
-- available (false → UI shows "not available"), extraction_confidence.
--
-- Migration steps:
--   1. Add new columns
--   2. Backfill key_points from legacy label column
--   3. Make legacy `label` and `score` nullable (kept for backward-compat reads)
--   4. UNIQUE (session_id, segment_id) so kp_task UPSERT works

ALTER TABLE key_points_annotations
    ADD COLUMN IF NOT EXISTS key_points            JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS explanation           TEXT  NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS available             BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS extraction_confidence REAL  NOT NULL DEFAULT 0.0;

-- Backfill key_points from legacy label column.
UPDATE key_points_annotations
   SET key_points = to_jsonb(ARRAY[label]),
       available = TRUE
 WHERE label IS NOT NULL
   AND label <> ''
   AND key_points = '[]'::jsonb;

ALTER TABLE key_points_annotations ALTER COLUMN label DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS key_points_annotations_unique
    ON key_points_annotations (session_id, segment_id)
    WHERE segment_id IS NOT NULL;
