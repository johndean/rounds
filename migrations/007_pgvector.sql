-- 007_pgvector — embeddings for semantic search + alignment.
--
-- IMPORTANT: requires the pgvector extension to be installed on the Postgres instance.
-- Run once (operator/user task; see use-railway User-only commands section):
--     python3 scripts/pg-extensions.py --service Postgres install vector
-- This migration's CREATE EXTENSION is a NO-OP if vector is already enabled,
-- and a clean error if the binaries aren't present (then run the script above).

CREATE EXTENSION IF NOT EXISTS vector;

-- Add semantic-search vector column to segments.
-- 768 dims matches gemini-embedding-001 output. Adjust if model changes.
ALTER TABLE segments
    ADD COLUMN IF NOT EXISTS embedding vector(768);

-- HNSW index for fast cosine-similarity search.
-- Only created when there's data — IF NOT EXISTS makes replays safe.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'segments_embedding_hnsw'
    ) THEN
        CREATE INDEX segments_embedding_hnsw
            ON segments
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
    END IF;
END$$;
