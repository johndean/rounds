-- 027_default_gcs_upload_backend — two related org-wide default flips:
--
--   (1) upload_backend  "railway" → "gcs"
--   (2) default_ai_model "gemini-2.5-flash" → "gemini-2.5-pro"
--
-- The seed in 006_settings.sql is ON CONFLICT DO NOTHING so existing
-- deployments retain the old values; this migration explicitly updates them
-- for current production. The 006 seed has also been bumped so fresh
-- deployments pick the new defaults directly.
--
-- Trigger: user directive 2026-05-18.
--
-- Rationale for upload_backend=gcs:
--   railway-routed uploads stream bytes through the FastAPI container, which
--   is slower and less reliable for the typical 200MB+ CE session video.
--   GCS direct uploads the bytes browser→bucket via a v4 signed PUT,
--   bypassing the server entirely.
--
-- Rationale for default_ai_model=gemini-2.5-pro:
--   gemini-2.5-flash has a 1M-token context. A 200MB+ video + 100+ slide
--   PDF + transcript prompt routinely exceeds 1M tokens, causing the
--   Gemini multimodal call to fail with `400 INVALID_ARGUMENT — input
--   token count exceeds 1048576`. gemini-2.5-pro has a 2M-token context
--   and handles these sessions. Cost is non-issue at current scale per
--   product owner.

INSERT INTO org_settings (key, value, updated_by, updated_at) VALUES
    ('upload_backend',   '"gcs"'::jsonb,           'migration_027', now()),
    ('default_ai_model', '"gemini-2.5-pro"'::jsonb, 'migration_027', now())
ON CONFLICT (key) DO UPDATE
    SET value      = EXCLUDED.value,
        updated_by = EXCLUDED.updated_by,
        updated_at = EXCLUDED.updated_at;
