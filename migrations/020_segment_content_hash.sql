-- 020_segment_content_hash — content-deterministic segment ID via SHA256.
--
-- Closes audit gap 🟠 (segment ID UUID vs MIC SHA256). Phase 7a.
--
-- Adds segments.content_hash TEXT — SHA256(session_id + start_ms). Re-runs
-- with identical input produce identical hashes, so re-running transcribe
-- on the same audio UPSERTs by content_hash instead of (session_id, seq),
-- preserving FK relationships in alignments / normalization_results / words /
-- transcription_discrepancies / key_points_annotations.
--
-- We keep UUID as PK to avoid breaking 5 dependent table FKs; content_hash
-- is the deterministic UNIQUE that drives idempotency.

ALTER TABLE segments ADD COLUMN IF NOT EXISTS content_hash TEXT;

-- Backfill existing rows with their deterministic hash. This is a no-op
-- on fresh DBs; on staging/prod sessions it makes the existing UUID stable
-- under future re-transcribe.
UPDATE segments
   SET content_hash = encode(sha256(((session_id::text) || start_ms::text)::bytea), 'hex')
 WHERE content_hash IS NULL;

ALTER TABLE segments ALTER COLUMN content_hash SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS segments_content_hash_uq
  ON segments (session_id, content_hash);
