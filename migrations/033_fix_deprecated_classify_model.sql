-- 033_fix_deprecated_classify_model — Defensive reset of classify_model if it
-- ever points at a truly-retired Google model (1.5-pro, 1.5-flash). MIC uses
-- gemini-2.0-flash and it's intentionally NOT in this target list — Rounds
-- shares MIC's grandfathered GEMINI_API_KEY and can call 2.0-flash. If a
-- future deploy lands without that key, the classifier will surface the
-- gemini_model_deprecated category via call_gemini_text and the operator can
-- pick a different model in Settings -> Discrepancy classification.
--
-- Idempotent: only updates when current value is one of the truly-retired
-- models below. Re-running this migration is safe.

UPDATE org_settings
SET    value = '"gemini-2.5-flash-lite"'::jsonb,
       updated_at = now()
WHERE  key = 'classify_model'
  AND  value::text IN (
       '"gemini-1.5-flash"',
       '"gemini-1.5-pro"'
);
