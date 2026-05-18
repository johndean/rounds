-- 009_session_templates — pipeline config + templates.
--
-- Closes audit gap 🔴 #10 (no per-session config) + #21 (no settings persistence).
-- Phase 6a / U73-U77 in 2026-05-18-001-feat-full-mic-parity.md.

-- ─── templates ──────────────────────────────────────────────────────────
-- One row per processing template. iil_config defaults reference these.
CREATE TABLE IF NOT EXISTS templates (
    id                      TEXT        PRIMARY KEY,
    name                    TEXT        NOT NULL,
    filler_policy           TEXT        NOT NULL DEFAULT 'medium',   -- light | medium | strict
    structure_extraction    TEXT        NOT NULL DEFAULT 'on',       -- on | off
    key_points              TEXT        NOT NULL DEFAULT 'on',       -- on | off
    tone                    TEXT        NOT NULL DEFAULT 'neutral',  -- formal | neutral | conversational
    terminology             TEXT        NOT NULL DEFAULT 'medium',   -- low | medium | high
    rewrite                 TEXT        NOT NULL DEFAULT 'minimal',  -- minimal | moderate | aggressive
    filler_words            JSONB       NOT NULL DEFAULT '[]'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO templates (id, name, filler_policy, structure_extraction, key_points, tone, terminology, rewrite, filler_words)
VALUES
    ('lecture_v1',   'Lecture',                 'strict',  'on',  'on',  'neutral',        'high',   'minimal',  '["um","uh","er","ah"]'::jsonb),
    ('training_v1',  'Training / Workshop',     'medium',  'on',  'on',  'conversational', 'medium', 'minimal',  '["um","uh","you know"]'::jsonb),
    ('technical_v1', 'Technical Deep Dive',     'light',   'on',  'on',  'neutral',        'high',   'minimal',  '["um","uh"]'::jsonb),
    ('podcast_v1',   'Podcast / Conversation',  'light',   'off', 'off', 'conversational', 'medium', 'minimal',  '["um","uh"]'::jsonb),
    ('sales_v1',     'Sales / Presentation',    'medium',  'on',  'on',  'formal',         'medium', 'moderate', '["um","uh"]'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ─── session_templates ──────────────────────────────────────────────────
-- One row per session — captures the pipeline routing chosen at upload.
CREATE TABLE IF NOT EXISTS session_templates (
    session_id                  UUID        PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    ai_pipeline                 TEXT        NOT NULL DEFAULT 'enhanced',   -- direct | enhanced
    ai_mode                     TEXT        NOT NULL DEFAULT 'transcript', -- transcript | summary | key-moments | structured-notes | custom-prompt
    ai_model                    TEXT        NOT NULL DEFAULT 'gemini-2.5-pro',
    prompt_mode                 TEXT        NOT NULL DEFAULT 'transcript',
    custom_prompt               TEXT,
    stt_backend                 TEXT        NOT NULL DEFAULT 'google_latest_long',
    template_id                 TEXT        NOT NULL DEFAULT 'lecture_v1' REFERENCES templates(id),
    iil_config                  JSONB       NOT NULL DEFAULT '{"enabled":true,"tier1":true,"tier2":true,"tier3":true}'::jsonb,
    auto_detected_template_id   TEXT        REFERENCES templates(id),
    auto_detected_confidence    REAL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS session_templates_template_idx ON session_templates (template_id);

-- ─── Backfill existing sessions with default template ───────────────────
-- Any session created before 6a lands gets a default enhanced/lecture_v1 row
-- so the editor + reingest endpoints don't 404 on missing template config.
INSERT INTO session_templates (session_id)
SELECT s.id FROM sessions s
LEFT JOIN session_templates st ON st.session_id = s.id
WHERE st.session_id IS NULL;
