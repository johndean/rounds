-- migrations/054_help_article_versions.sql
--
-- Phase 3 of the Help Center port (plan 2026-06-05-009).
-- Append-only version snapshots of help_articles. Every PATCH on
-- /v1/help/articles/{id} snapshots the prior state into this table
-- BEFORE applying the change, bumps help_articles.version, and stamps
-- last_edited_by. The admin Version History dialog reads from here.
--
-- The "append-only" posture mirrors corrections_ledger (ADR-005) — rows
-- in this table are NEVER updated or deleted directly. Restoring an
-- older version is a fresh PATCH whose payload is the older snapshot;
-- the restore itself appends a new row with the current state. There
-- is no DELETE path.
--
-- ON DELETE CASCADE on article_id: when an article row is permanently
-- removed (admin "hard purge" — not currently exposed in the UI; only
-- via DB intervention), its versions are dropped too. Soft-archive
-- (is_published=FALSE) preserves the article and all its versions.
--
-- Related ADRs: ADR-005 (corrections ledger append-only invariant).

CREATE TABLE IF NOT EXISTS help_article_versions (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id  UUID         NOT NULL REFERENCES help_articles(id) ON DELETE CASCADE,
    version     INTEGER      NOT NULL,
    snapshot    JSONB        NOT NULL,
    edited_by   TEXT         NOT NULL DEFAULT '',
    edited_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (article_id, version)
);

-- The History dialog lists versions newest-first per article.
CREATE INDEX IF NOT EXISTS help_article_versions_article_edited_at_idx
    ON help_article_versions (article_id, edited_at DESC);
