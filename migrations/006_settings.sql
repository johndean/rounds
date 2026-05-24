-- 006_settings — Org-wide settings + per-type stage assignee matrix + email templates.

CREATE TABLE IF NOT EXISTS org_settings (
    key             TEXT        PRIMARY KEY,
    value           JSONB       NOT NULL,
    updated_by      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed the General-section defaults (idempotent on conflict)
INSERT INTO org_settings (key, value) VALUES
    ('org_name',          '"Vetstreet Internal Network"'::jsonb),
    ('default_locale',    '"en-US"'::jsonb),
    ('time_zone',         '"America/New_York"'::jsonb),
    ('default_ai_model',  '"gemini-2.5-pro"'::jsonb),
    ('upload_backend',    '"gcs"'::jsonb),
    ('classify_backend',  '"gemini_dev"'::jsonb),
    ('classify_model',    '"gemini-2.5-flash-lite"'::jsonb),
    ('include_key_points','true'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- ─── People / groups (team & roles section) ─────────────────────────────
CREATE TABLE IF NOT EXISTS people (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT        NOT NULL UNIQUE,
    name            TEXT        NOT NULL,
    role            TEXT,                                          -- "Operator" | "Editor" | "Reviewer" | "Admin"
    avatar_color    TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS groups (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT        NOT NULL UNIQUE,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS group_members (
    group_id        UUID        NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    person_id       UUID        NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, person_id)
);

-- ─── Session types + per-type stage assignee matrix ─────────────────────
CREATE TABLE IF NOT EXISTS session_types (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT        NOT NULL UNIQUE,                   -- "lecture" | "panel" | "workshop" | ...
    label           TEXT        NOT NULL,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS stage_assignees (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    type_id         UUID        NOT NULL REFERENCES session_types(id) ON DELETE CASCADE,
    stage           TEXT        NOT NULL,                          -- one of the 8 SOP stages
    assignee_email  TEXT        NOT NULL,
    notify_email    BOOLEAN     NOT NULL DEFAULT TRUE,
    UNIQUE (type_id, stage)
);

-- ─── Email templates (8 stage defaults + custom per-type, IMPLEMENTATION.md §11) ─
CREATE TABLE IF NOT EXISTS email_templates (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    type_id         UUID        REFERENCES session_types(id) ON DELETE CASCADE,  -- NULL = default-for-all-types
    stage           TEXT        NOT NULL,
    subject         TEXT        NOT NULL,
    body_html       TEXT        NOT NULL,
    body_text       TEXT,
    variables_used  JSONB       NOT NULL DEFAULT '[]'::jsonb,      -- ["{{session_code}}", ...]
    enabled         BOOLEAN     NOT NULL DEFAULT TRUE,
    updated_by      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (type_id, stage)                                        -- NULL type_id allowed multiple times
);

-- Legacy partial unique index for the original 006 email_templates schema
-- (columns: stage, type_id). Migration 048 reshapes the table to the new
-- schema (columns: stage_id, session_type_id) and adds its own unique
-- indexes. On re-runs after 048 has applied, this CREATE INDEX would
-- fail with `column "type_id" does not exist`. Wrap in a DO block so
-- the index is only created when BOTH legacy columns exist - which is
-- true on the FIRST run (right after this CREATE TABLE) and false on
-- every re-run after 048 has reshaped the table.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'email_templates' AND column_name = 'type_id'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'email_templates' AND column_name = 'stage'
    ) THEN
        EXECUTE 'CREATE UNIQUE INDEX IF NOT EXISTS email_templates_default_uq '
             || 'ON email_templates (stage) WHERE type_id IS NULL';
    END IF;
END $$;

-- ─── Prompt templates catalog (IMPLEMENTATION.md §10) ───────────────────
CREATE TABLE IF NOT EXISTS prompt_templates (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT        NOT NULL,
    category        TEXT        NOT NULL,                          -- "IIL" | "AI_MODE" | "Classification" | ...
    icon            TEXT,
    description     TEXT,
    system_prompt   TEXT        NOT NULL,
    iil_config      JSONB       NOT NULL DEFAULT '{}'::jsonb,      -- {filler:bool, tone:bool, terminology:bool, rewrite:bool, structure:bool, key_points:bool}
    type            TEXT,                                          -- "lecture" | etc.
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (category, name)
);
