-- 028_session_templates_default_pro — batch-upgrade existing sessions stuck
-- on gemini-2.5-flash to gemini-2.5-pro, and reset the known-failed session
-- afb1d4df so its retry on the now-correct model can succeed.
--
-- Trigger: user-visible session failure 2026-05-18 — session afb1d4df
-- (042326_Hendershott chat, 236 MB video + 140-slide PDF) had been retrying
-- ai_process_task every ~2 min for >1 hour, all 9 retries failing with
-- 400 INVALID_ARGUMENT — input token count exceeds 1,048,576.
--
-- Root cause: session_templates.ai_model was 'gemini-2.5-flash' (1M context)
-- baked in at upload time, BEFORE migrations 027 + commit ced0155 flipped
-- the upload-page default and org-wide default to gemini-2.5-pro (2M context).
-- The Python pipeline code is byte-equivalent to MIC's — MIC works because
-- MIC's UploadView has always defaulted to pro
-- (Desktop/mic/frontend/src/stores/ui.js:50,143).
--
-- This migration:
--   (1) Bulk-upgrades every session_templates row still on gemini-2.5-flash
--       to gemini-2.5-pro. Idempotent — no-op for rows already on pro.
--   (2) Resets sessions.status for the known failed-due-to-overflow session
--       afb1d4df so the next ingest re-runs cleanly with the new model.

-- (1) Bulk model upgrade for stuck sessions
UPDATE session_templates
   SET ai_model = 'gemini-2.5-pro',
       updated_at = now()
 WHERE ai_model = 'gemini-2.5-flash';

-- (2) Reset the known-failed session afb1d4df so its retry picks up the new model.
-- Other failed sessions are NOT auto-reset to avoid masking unrelated bugs;
-- operators can re-trigger them via the diagnostics /reingest endpoint.
UPDATE sessions
   SET status = 'uploading',
       updated_at = now()
 WHERE id = 'afb1d4df-6e0f-46aa-aeda-33f58e61d54d'
   AND status = 'failed';
