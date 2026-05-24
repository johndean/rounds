-- 047_prompt_templates — Settings → Prompt templates CRUD backing table.
--
-- Phase 4 of the 2026-05-23 Settings BUILD remediation plan. Replaces the
-- frontend's PROMPT_TEMPLATES fixture (frontend/src/fixtures/settings.ts).
--
-- Single table with a JSONB `config` column so the two kinds of templates
-- (Processing/STT presets + AI Prompt system prompts) share one shape.
-- For 'processing' kind, config holds { filler_policy, tone, terminology,
-- rewrite_level, structure, keypoints, chips }. For 'ai_prompt' kind,
-- config holds { system_prompt }.
--
-- Idempotent (every CREATE uses IF NOT EXISTS), additive, reversible via
-- DROP TABLE. The 8 seed rows below match the previously-hardcoded UI.

CREATE TABLE IF NOT EXISTS prompt_templates (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    kind            TEXT         NOT NULL,                       -- 'processing' | 'ai_prompt'
    name            TEXT         NOT NULL,
    icon            TEXT         NOT NULL DEFAULT '📝',
    description     TEXT,
    category        TEXT         NOT NULL DEFAULT 'Custom',      -- 'Education' | 'Technical' | 'Conversational' | 'Business' | 'Custom'
    config          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    is_system       BOOLEAN      NOT NULL DEFAULT FALSE,         -- system templates can be duplicated but not deleted
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,          -- soft-delete via is_active = FALSE
    version         INTEGER      NOT NULL DEFAULT 1,
    created_by      TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS prompt_templates_kind_active_idx
    ON prompt_templates (kind) WHERE is_active = TRUE;
CREATE UNIQUE INDEX IF NOT EXISTS prompt_templates_name_uq
    ON prompt_templates (lower(name)) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS prompt_templates_system_idx
    ON prompt_templates (is_system) WHERE is_active = TRUE;

-- ─── Seed: 6 processing templates + 2 AI prompt templates ────────────────
-- These previously lived in frontend/src/fixtures/settings.ts as
-- PROMPT_TEMPLATES + were inlined in the AI Prompt Templates section of
-- SectionPromptTemplates.vue. Idempotent via the UNIQUE index on lower(name).

INSERT INTO prompt_templates (kind, name, icon, description, category, config, is_system)
VALUES
    ('processing', 'Lecture', '🎓', 'Optimized for structured teaching content', 'Education',
     '{"filler_policy":"Strict","tone":"Neutral","terminology":"Medium","rewrite_level":"Minimal","structure":true,"keypoints":true,"chips":["strict","neutral","medium","structure","key points"]}'::jsonb,
     TRUE),
    ('processing', 'Training / Workshop', '🛠️', 'Handles Q&A, exercises and interaction patterns', 'Education',
     '{"filler_policy":"Moderate","tone":"Neutral","terminology":"Medium","rewrite_level":"Moderate","structure":true,"keypoints":true,"chips":["moderate","preserve","medium","structure","key points"]}'::jsonb,
     TRUE),
    ('processing', 'Technical Deep Dive', '⚙️', 'Terminology preservation — minimal rewrite', 'Technical',
     '{"filler_policy":"Moderate","tone":"Neutral","terminology":"Strict","rewrite_level":"Minimal","structure":true,"keypoints":true,"chips":["moderate","preserve","strict","structure","key points"]}'::jsonb,
     TRUE),
    ('processing', 'Podcast / Conversation', '🎙️', 'Light cleanup — conversational flow preserved', 'Conversational',
     '{"filler_policy":"Light","tone":"Conversational","terminology":"Loose","rewrite_level":"Minimal","structure":false,"keypoints":false,"chips":["light","conversational","low"]}'::jsonb,
     TRUE),
    ('processing', 'Sales / Presentation', '📊', 'Emphasis and persuasion patterns preserved', 'Business',
     '{"filler_policy":"Moderate","tone":"Persuasive","terminology":"Medium","rewrite_level":"Moderate","structure":true,"keypoints":true,"chips":["moderate","persuasive","medium","structure","key points"]}'::jsonb,
     TRUE),
    ('processing', 'Custom', '⚡', 'Define your own processing rules', 'Custom',
     '{"filler_policy":"Moderate","tone":"Neutral","terminology":"Medium","rewrite_level":"Minimal","structure":true,"keypoints":true,"chips":["moderate","neutral","medium","structure","key points"]}'::jsonb,
     TRUE),
    ('ai_prompt', 'Transcript', '📝', 'Clean, enhanced transcript with corrected speech errors', 'Custom',
     '{"system_prompt":"You are generating a VIN transcript that must be 100% compliant with the full Transcript SOP and downstream processing."}'::jsonb,
     TRUE),
    ('ai_prompt', 'Transcript (Paragraph v1)', '📝', 'Clean, enhanced transcript with corrected speech errors', 'Custom',
     '{"system_prompt":"You are generating a VIN transcript in paragraph form. Preserve speaker turns, correct disfluencies, and emit one paragraph per topic shift."}'::jsonb,
     TRUE)
ON CONFLICT ((lower(name))) WHERE is_active = TRUE DO NOTHING;
