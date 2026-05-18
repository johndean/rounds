-- 021_iil_features — instructor_profiles persistent features.
--
-- Closes residual 🟠 (IIL learning was simple bucketing, no feature extraction).
-- Phase 7f.

ALTER TABLE instructor_profiles ADD COLUMN IF NOT EXISTS filler_words           JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE instructor_profiles ADD COLUMN IF NOT EXISTS avg_compression_ratio  REAL;
-- avg_filler_rate already exists; nothing to add. Same for sample_count.
