-- 049_prompt_templates_default_for_mode — wire Settings catalog to upload pipeline.
--
-- Adds a nullable `default_for_mode` column to prompt_templates so ops can mark
-- ONE template per ai_mode as "the default Gemini prompt for this mode". The
-- upload pipeline (app/prompts.py::get_prompt_for_mode) reads this column on
-- every Gemini call; falls back to the hardcoded constants in app/prompts.py
-- if no row is marked (so a DB outage can't break uploads).
--
-- ai_mode values are the 4 catalog-bindable strings emitted by
-- frontend/src/views/UploadView.vue line 413:
--   'transcript' | 'summary' | 'key-moments' | 'structured-notes'
-- (The 5th mode, 'custom-prompt', comes from the upload form's free-text
-- field, not the catalog — so it's NOT in the CHECK constraint.)
--
-- After this migration:
--   * Editing prompt_templates.config->'system_prompt' in Settings UI
--     immediately changes what Gemini receives on the next upload.
--   * Renaming a template is rename-safe (binding is by column, not name).
--   * Soft-deleting a template (is_active = FALSE) removes its default-flag
--     from the partial unique index, so a replacement can claim that slot.

ALTER TABLE prompt_templates
    ADD COLUMN IF NOT EXISTS default_for_mode TEXT;

-- CHECK constraint added in a DO block so re-runs don't error on duplicate
-- constraint names. ADD CONSTRAINT IF NOT EXISTS isn't supported in Postgres
-- the way ADD COLUMN IF NOT EXISTS is, so we guard with a catalog lookup.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
         WHERE constraint_name = 'prompt_templates_default_for_mode_chk'
    ) THEN
        ALTER TABLE prompt_templates
          ADD CONSTRAINT prompt_templates_default_for_mode_chk
          CHECK (default_for_mode IS NULL
              OR default_for_mode IN ('transcript','summary','key-moments','structured-notes'));
    END IF;
END $$;

-- One default per mode. Partial index excludes NULL + soft-deleted rows so
-- multiple unbound templates coexist freely and a replacement can claim the
-- slot after soft-delete.
CREATE UNIQUE INDEX IF NOT EXISTS prompt_templates_default_for_mode_uq
    ON prompt_templates (default_for_mode)
 WHERE default_for_mode IS NOT NULL AND is_active = TRUE;

-- Lookup index for the hot path (every upload runs this query in
-- app/prompts.py::get_prompt_for_mode).
CREATE INDEX IF NOT EXISTS prompt_templates_default_mode_lookup_idx
    ON prompt_templates (default_for_mode, is_active)
 WHERE default_for_mode IS NOT NULL;

-- Seed: bind the existing 'Transcript' system template (seeded by migration
-- 047) to ai_mode='transcript'. Idempotent: only updates is_system rows where
-- default_for_mode is currently NULL, so re-runs don't disturb ops edits.
UPDATE prompt_templates
   SET default_for_mode = 'transcript'
 WHERE kind = 'ai_prompt'
   AND lower(name) = 'transcript'
   AND is_system = TRUE
   AND default_for_mode IS NULL;
