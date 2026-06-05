-- migrations/053_help_articles.sql
--
-- Phase 3 of the Help Center port (plan 2026-06-05-009).
-- Creates the help_articles table that backs the admin CMS surface.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS preserves admin edits across
-- re-runs. We DO NOT DROP TABLE here (unlike 047_prompt_templates.sql,
-- which is fully seed-derived) because once seeding runs in 055 and
-- admins edit articles, the table holds authoritative data.
--
-- The `slug` column is the stable seed identifier so 055 can use
-- ON CONFLICT (slug) DO NOTHING for idempotency. Admin-created articles
-- get an auto-generated slug = lower(replace(title, ' ', '-')) or
-- a UUID fallback if collision.
--
-- Related ADRs: ADR-005 (corrections-ledger pattern mirrored for versions),
--               ADR-011 (append-only migrations).
-- Related business rules: BR-001 (admin gate via LEGACY_ADMIN_EMAIL).

CREATE TABLE IF NOT EXISTS help_articles (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                TEXT         NOT NULL UNIQUE,
    title               TEXT         NOT NULL,
    summary             TEXT         NOT NULL DEFAULT '',
    category            TEXT         NOT NULL DEFAULT 'general',
    audience            TEXT         NOT NULL DEFAULT 'users',
    feature_tags        JSONB        NOT NULL DEFAULT '[]'::jsonb,
    steps               JSONB        NOT NULL DEFAULT '[]'::jsonb,
    related_article_ids JSONB        NOT NULL DEFAULT '[]'::jsonb,
    display_order       INTEGER      NOT NULL DEFAULT 0,
    is_published        BOOLEAN      NOT NULL DEFAULT FALSE,
    content_domain      TEXT         NOT NULL DEFAULT 'general',
    workflow_slug       TEXT,
    version             INTEGER      NOT NULL DEFAULT 1,
    last_edited_by      TEXT         NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- List queries filter on (is_published, audience); coverage groups by content_domain.
CREATE INDEX IF NOT EXISTS help_articles_published_idx        ON help_articles (is_published);
CREATE INDEX IF NOT EXISTS help_articles_content_domain_idx   ON help_articles (content_domain);
CREATE INDEX IF NOT EXISTS help_articles_audience_idx         ON help_articles (audience);

-- GIN on JSONB for fast "give me articles with this feature_tag" queries.
CREATE INDEX IF NOT EXISTS help_articles_feature_tags_gin_idx
    ON help_articles USING GIN (feature_tags);

-- Sort by display_order within a (content_domain, audience) bucket.
CREATE INDEX IF NOT EXISTS help_articles_domain_order_idx
    ON help_articles (content_domain, display_order);
