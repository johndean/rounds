-- 058_schema_comments.sql — metadata-only schema annotations.
--
-- Plan ref: docs/plans/2026-06-10-001-zero-risk-gap-remediation.md (Track B).
-- Resolves docs/gap-analysis.md §4 in-database by labeling the tables/columns
-- that the documentation-factory audit flagged as confusing or orphaned.
--
-- ZERO RISK: COMMENT ON statements only. No DDL on structure, no data touched,
-- no locks of consequence, instant. Forward-only per ADR-011.
-- Rollback (if ever needed): re-run with `IS NULL` in place of each string.
--
-- This migration deliberately does NOT add the session_locks FK or drop
-- sop_approvals — those are opt-in, non-zero-risk steps (plan Tracks C2/C3).

COMMENT ON TABLE sop_approvals IS
    'RESERVED/UNUSED as of 2026-06-10: no app reader/writer (verified). Planned per-stage sign-off feature; empty in all environments. See docs/gap-analysis.md G1.';

COMMENT ON TABLE validation_results IS
    'Alignment validation rows, keyed by alignment_id (written by app/tasks/align.py). NOT the same as the normalization_results.validation_results JSONB column. See docs/gap-analysis.md G6.';

COMMENT ON COLUMN normalization_results.validation_results IS
    'IIL normalization validation (JSONB: check1..check4). Distinct from the validation_results TABLE (alignment validation). See docs/gap-analysis.md G6.';

COMMENT ON TABLE correction_ledger IS
    'LIVE Phase-4 append-only correction ledger (029). Twin of the legacy corrections table (002); both are in use and distinct. See docs/gap-analysis.md G5.';

COMMENT ON TABLE session_speakers IS
    'Manifest-parsed speakers (011). Twin of the runtime speakers table (001); both are in use and distinct. See docs/gap-analysis.md G5.';

COMMENT ON TABLE transcription_discrepancies IS
    'STT-vs-normalized diff discrepancies (017). Twin of the editor discrepancies table (002); both are in use and distinct. See docs/gap-analysis.md G5.';

COMMENT ON TABLE session_locks IS
    'Concurrent-edit lock, 1/session (057). session_id has no FK by design: rows are ephemeral (90s TTL, swept). Optional CASCADE-FK hardening tracked as plan Track C2. See docs/gap-analysis.md G2.';
