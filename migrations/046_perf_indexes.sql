-- 046_perf_indexes — fill three small gaps in the existing index coverage.
--
-- Phase 1 of the 2026-05-23 zero-risk perf plan. Idempotent (every statement
-- uses IF NOT EXISTS), additive (no data change, no schema change), reversible
-- via DROP INDEX.
--
-- A pre-write audit found that several originally-proposed indexes already
-- exist in earlier migrations:
--   * sources(session_id)        → 001_init.sql:49  sources_session_idx
--   * slides(session_id)         → 001_init.sql:66  slides_session_idx
--   * audit_events(session_id…)  → 004_audit.sql:13 audit_events_session_idx
-- so this migration only adds the three that are actually missing.

-- 1) Default ORDER BY in GET /v1/sessions — `created_at DESC NULLS LAST` with
--    the always-applied `deleted_at IS NULL` predicate. Today this falls back
--    to a sort over the filtered set. Partial index keeps it tight.
CREATE INDEX IF NOT EXISTS sessions_created_at_idx
    ON sessions (created_at DESC) WHERE deleted_at IS NULL;

-- 2) Title LIKE search in the same endpoint — `LOWER(title) LIKE :f`. There's
--    already a parallel index on lower(code) (001_init.sql:32); this is its
--    sibling for title.
CREATE INDEX IF NOT EXISTS sessions_title_lower_idx
    ON sessions (lower(title));

-- 3) chat_messages list — `WHERE session_id = :s ORDER BY sent_at_ms LIMIT N`
--    (see app/api/add_to_session.py:551). Existing chat_messages_session_idx
--    is unordered, so Postgres sorts the filtered rows. Compound index lets
--    the index ordering serve the ORDER BY directly.
CREATE INDEX IF NOT EXISTS chat_messages_session_sent_idx
    ON chat_messages (session_id, sent_at_ms);
