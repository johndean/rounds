-- 023_artifact_versions — versioned artifacts (is_current pattern).
--
-- Phase 7i (parity-3): closes 🟠 #63 (burn_captions overwrites in place,
-- loses version history) + 🟠 #68 (generate_* artifact pipeline needs versioned
-- Artifact rows with lineage).
--
-- Changes:
--   - Add version (INT, default 1)
--   - Add is_current (BOOL, default TRUE)
--   - Add style_config (JSONB, default '{}')
--   - Drop UNIQUE (session_id, kind) — now multiple versions allowed
--   - Add unique-current-per-kind partial index — only one is_current per (session, kind)

ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS is_current BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS style_config JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE artifacts DROP CONSTRAINT IF EXISTS artifacts_session_id_kind_key;

CREATE UNIQUE INDEX IF NOT EXISTS artifacts_unique_current_idx
    ON artifacts (session_id, kind)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS artifacts_session_kind_version_idx
    ON artifacts (session_id, kind, version DESC);
