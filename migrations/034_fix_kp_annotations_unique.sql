-- 034_fix_kp_annotations_unique — Replace partial unique index on
-- key_points_annotations with a non-partial one so kp_task's
-- ON CONFLICT (session_id, segment_id) inference succeeds.
--
-- Migration 025 created the index as partial (WHERE segment_id IS NOT NULL).
-- That's correct semantically (only enforce uniqueness when the row is tied
-- to a segment), but PostgreSQL's ON CONFLICT requires the index predicate to
-- appear in the clause to use a partial index — sqlalchemy.text() can't add
-- it. Workers retrying kp_task land on "no unique or exclusion constraint
-- matching the ON CONFLICT specification" and the session shows FAILED.
--
-- kp_task only INSERTs rows with a non-NULL segment_id (see app/tasks/
-- kp_task.py:123), so dropping the partial predicate is safe. If a NULL
-- segment_id row ever exists, the constraint allows exactly one NULL row
-- per (session_id, NULL) which is the standard PG semantics for NULL in
-- a UNIQUE constraint.
--
-- Idempotent: DROP/CREATE wrapped in IF (NOT) EXISTS.

DROP INDEX IF EXISTS key_points_annotations_unique;

CREATE UNIQUE INDEX IF NOT EXISTS key_points_annotations_unique
    ON key_points_annotations (session_id, segment_id);
