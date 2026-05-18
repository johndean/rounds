-- 026_validation_repair_columns — MIC-style validate_and_repair tracking.
--
-- Phase 7j (zero-gap parity): closes the IIL validate-and-repair design
-- deviation surfaced by the parity-3 re-audit. Adds repair_applied +
-- repair_attempts columns so the editor can render "this segment fell
-- through to raw STT" without parsing the validation_results JSONB.
--
-- validation_results JSONB now contains MIC-style check1..check4 keys
-- ("pass" | "fail" | "repaired"). No new column needed for those — they
-- live inside the existing JSONB blob.

ALTER TABLE normalization_results
    ADD COLUMN IF NOT EXISTS repair_applied  BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS repair_attempts INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS normalization_results_repair_idx
    ON normalization_results (session_id)
    WHERE repair_applied = TRUE;

-- Index for the clinical-safety raw-fallback query: which segments had
-- the broken-normalize fallback applied? Editor flag chip + audit pane
-- both filter on this.
CREATE INDEX IF NOT EXISTS normalization_results_raw_fallback_idx
    ON normalization_results (session_id, repair_attempts)
    WHERE repair_attempts = 2 AND repair_applied = FALSE;
