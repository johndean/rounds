-- 040_stage_assignees_typed_fk — Add person_id / group_id FKs to stage_assignees.
--
-- Unit 5 of the Team & Roles port. Today stage_assignees.assignee_email
-- is a free-text column: "carlab@vin.com" for a person, "Group: External"
-- for a group. That breaks two ways:
--   - deleting a person leaves orphan rows that still show the email
--   - renaming a group breaks every assignment via positional string match
--
-- MIC parity: add nullable typed FKs alongside assignee_email. Writes
-- populate both surfaces; reads JOIN on the typed FK and fall back to the
-- text column if neither FK matches. Cascade deletes are SET NULL so the
-- chip renders "(unassigned)" instead of becoming an orphan.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, IF NOT EXISTS index, constraint
-- guarded by information_schema check.

ALTER TABLE stage_assignees
    ADD COLUMN IF NOT EXISTS person_id UUID REFERENCES people(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS group_id  UUID REFERENCES groups(id) ON DELETE SET NULL;

-- Exactly one of person_id / group_id may be set; both NULL = unassigned
-- (legacy assignee_email text might still carry a value but typed FKs win
-- on read).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
         WHERE constraint_name = 'chk_stage_assignees_single_assignee'
           AND table_name = 'stage_assignees'
    ) THEN
        ALTER TABLE stage_assignees
            ADD CONSTRAINT chk_stage_assignees_single_assignee
            CHECK ((person_id IS NULL) OR (group_id IS NULL));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS stage_assignees_person_idx ON stage_assignees (person_id);
CREATE INDEX IF NOT EXISTS stage_assignees_group_idx  ON stage_assignees (group_id);

-- Backfill: match existing assignee_email strings to people / groups.
-- Person match: lowered email vs people.email (people.email is canonical).
UPDATE stage_assignees sa
   SET person_id = p.id
  FROM people p
 WHERE sa.person_id IS NULL
   AND sa.group_id  IS NULL
   AND LOWER(sa.assignee_email) = LOWER(p.email);

-- Group match: legacy "Group: <name>" prefix convention.
UPDATE stage_assignees sa
   SET group_id = g.id
  FROM groups g
 WHERE sa.person_id IS NULL
   AND sa.group_id  IS NULL
   AND sa.assignee_email = 'Group: ' || g.name;
