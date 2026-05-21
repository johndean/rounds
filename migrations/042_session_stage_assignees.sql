-- 042_session_stage_assignees — Per-session, per-stage assignee table.
--
-- Unit 6 part 2. Holds the assignment that the Editor's right-rail Admin
-- chip + SOP stepper actually display. New sessions get rows here at
-- ingest time, copied from the chosen Type's stage_assignees matrix via
-- app/services/session_init.py::init_session_stages. Operators can later
-- override per-stage (PATCH endpoint in a future Unit 7).
--
-- Stored fields:
--   - person_id / group_id: typed FK (ON DELETE SET NULL — orphan-safe)
--   - notify_email: copied from the Type's matrix; future hook fires emails
--     on stage transition.
--   - source: 'default' if auto-populated from the Type matrix at ingest,
--     'manual' if an operator overrode the stage.
--   - assigned_by + assigned_at: audit fields.
--
-- PRIMARY KEY (session_id, stage) enforces one assignee per stage per session.
-- Deleting the session cascades. Idempotent: CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS session_stage_assignees (
    session_id     UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    stage          TEXT        NOT NULL,
    person_id      UUID                 REFERENCES people(id)  ON DELETE SET NULL,
    group_id       UUID                 REFERENCES groups(id)  ON DELETE SET NULL,
    notify_email   BOOLEAN     NOT NULL DEFAULT TRUE,
    source         TEXT        NOT NULL DEFAULT 'manual',   -- 'default' | 'manual'
    assigned_by    TEXT,
    assigned_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, stage),
    CONSTRAINT chk_session_stage_assignees_single_assignee
        CHECK ((person_id IS NULL) OR (group_id IS NULL))
);

CREATE INDEX IF NOT EXISTS session_stage_assignees_person_idx
    ON session_stage_assignees (person_id);
CREATE INDEX IF NOT EXISTS session_stage_assignees_group_idx
    ON session_stage_assignees (group_id);
