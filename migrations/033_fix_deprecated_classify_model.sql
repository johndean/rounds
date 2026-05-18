-- 033_fix_deprecated_classify_model — Reset classify_model to a still-supported
-- Gemini model if it points at a deprecated one. Google retired gemini-2.0-flash
-- and gemini-2.0-flash-lite (404 NOT_FOUND), which left the discrepancy classifier
-- stuck looping through every batch and burning hours of worker time per session.
--
-- Idempotent: only updates when current value is a known-bad model. Re-running
-- this migration is safe.

UPDATE org_settings
SET    value = '"gemini-2.5-flash-lite"'::jsonb,
       updated_at = now()
WHERE  key = 'classify_model'
  AND  value::text IN (
       '"gemini-2.0-flash"',
       '"gemini-2.0-flash-lite"',
       '"gemini-2.0-flash-prev"',
       '"gemini-1.5-flash"',
       '"gemini-1.5-pro"'
);
