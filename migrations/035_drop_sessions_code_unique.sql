-- 035_drop_sessions_code_unique — Allow multiple sessions to share a code.
--
-- Background: every extras2 manifest carries a `session code = ...` line
-- that identifies the lecture. The first upload of a given lecture
-- successfully UPDATEs sessions.code from the manifest. Every subsequent
-- upload of the same lecture (a re-process, a fresh attempt, a different
-- reviewer's run) hit the UNIQUE constraint, raising UniqueViolationError
-- inside _parse_manifest_and_chat_sources. SQLAlchemy aborted the
-- transaction; speakers, polls, poll_options, slide_resources, and chat
-- INSERTs all silently failed via "current transaction is aborted." The
-- editor displayed CHAT 0 / POLLS 0 honestly because no rows landed.
--
-- The code is a human-readable lecture identifier, not a primary key.
-- Multiple sessions for the same lecture should coexist (retries,
-- versioning, parallel reviewers). Dropping the UNIQUE constraint is
-- the correct architectural fix. The btree index can stay for lookup
-- performance.
--
-- Idempotent: DROP CONSTRAINT IF EXISTS.

ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_code_key;

-- Keep the non-unique btree index for lookup performance.
-- (sessions_code_key index is dropped automatically with the constraint.)
CREATE INDEX IF NOT EXISTS sessions_code_idx ON sessions (code);
