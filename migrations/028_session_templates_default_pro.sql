-- 028_session_templates_default_pro — batch-upgrade existing sessions still
-- configured for gemini-2.5-flash to gemini-2.5-pro.
--
-- Context: the Python pipeline code in app/tasks/ai_process.py is a verbatim
-- port of MIC's, but MIC's UploadView store
-- (Desktop/mic/frontend/src/stores/ui.js:50,143) defaults selectedModel to
-- gemini-2.5-pro while Rounds was defaulting to gemini-2.5-flash. flash has
-- a 1M-token context, which is exceeded by typical CE sessions (30-60 min
-- video + 100+ slide deck = ~1.0-1.5M tokens) — those sessions fail with
-- 400 INVALID_ARGUMENT. gemini-2.5-pro has a 2M context and handles them.
--
-- Migrations 027 + commit 705d4a8 + earlier ced0155 flipped every default
-- layer (org_settings.default_ai_model, frontend UploadView, Pydantic
-- PipelineConfig, fixtures AI_MODELS[0], call_gemini_multimodal default).
-- This migration cleans up any session_templates rows already in the DB
-- that were created on the old flash default — they would otherwise
-- continue retrying on flash and failing forever.
--
-- Idempotent. No-op on rows already at gemini-2.5-pro.
-- session_templates has no updated_at column — the row update is by
-- composite (session_id pk + ai_model value), tracked via session_audit
-- if any caller cares to log the upgrade.

UPDATE session_templates
   SET ai_model = 'gemini-2.5-pro'
 WHERE ai_model = 'gemini-2.5-flash';
