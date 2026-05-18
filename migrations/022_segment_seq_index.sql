-- 022_segment_seq_index — drop UNIQUE on (session_id, seq), keep as plain index.
--
-- Phase 7h follow-up. After 7a's content_hash UNIQUE, the (session_id, seq)
-- UNIQUE is redundant for idempotency AND introduces a collision risk:
-- a re-run with a refined segmenter could place content_hash=Y at seq=3 when
-- a stale row has content_hash=X at seq=3. The content_hash ON CONFLICT
-- can't fire (Y != X) so the row is INSERTed — and the seq UNIQUE blocks it.
--
-- Resolution: demote the constraint to a non-unique index. The seq is still
-- used for ORDER BY and seq-based lookups; uniqueness lives on content_hash.

ALTER TABLE segments DROP CONSTRAINT IF EXISTS segments_session_id_seq_key;

CREATE INDEX IF NOT EXISTS segments_session_seq_idx_v2 ON segments (session_id, seq);
