-- 041_session_type_link — Add session_type_id FK on sessions.
--
-- Unit 6 part 1. Lets every session declare which Type's stage matrix it
-- should auto-init from. NULL means "use the org default Type"
-- (`session_types.is_default = TRUE`, guaranteed by migration 038).
--
-- ON DELETE SET NULL means deleting a Type doesn't cascade-delete sessions —
-- they just fall back to the default.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, CREATE INDEX IF NOT EXISTS.

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS session_type_id UUID REFERENCES session_types(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS sessions_session_type_id_idx ON sessions (session_type_id);
