-- 044_backfill_session_stage_assignees — Populate per-session stage
-- assignees for every existing session from its Type's matrix.
--
-- Unit 6 backfill. Each session gets 7-8 rows (one per stage Carla
-- assigned). If sessions.session_type_id is set, we use that Type's
-- matrix. Otherwise we fall back to the org default Type
-- (session_types.is_default = TRUE), guaranteed by migration 038.
--
-- Idempotent: NOT EXISTS guard skips sessions that already have rows.
-- Sessions ingested AFTER this migration get their rows via
-- app/services/session_init.py::init_session_stages — see app/api/gcs_upload.py.

WITH default_type AS (
    SELECT id FROM session_types WHERE is_default = TRUE LIMIT 1
)
INSERT INTO session_stage_assignees
    (session_id, stage, person_id, group_id, notify_email, source, assigned_by, assigned_at)
SELECT
    s.id,
    sa.stage,
    sa.person_id,
    sa.group_id,
    sa.notify_email,
    'default',
    'system:migration_044',
    now()
  FROM sessions s
 CROSS JOIN LATERAL (
    SELECT stage, person_id, group_id, notify_email
      FROM stage_assignees
     WHERE type_id = COALESCE(s.session_type_id, (SELECT id FROM default_type))
 ) sa
 WHERE s.deleted_at IS NULL
   AND NOT EXISTS (
       SELECT 1 FROM session_stage_assignees ssa
        WHERE ssa.session_id = s.id AND ssa.stage = sa.stage
   );
