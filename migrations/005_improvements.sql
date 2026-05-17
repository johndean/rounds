-- 005_improvements — Improvements master table + 5-step wizard payload per IMPLEMENTATION.md §13.

CREATE TABLE IF NOT EXISTS improvements (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT        NOT NULL,
    description     TEXT,
    type            TEXT,                                          -- "feature" | "bug" | "ux" | etc.
    status          TEXT        NOT NULL DEFAULT 'pending',        -- pending | under_review | approved | in_progress | rolled_out | declined | archived
    priority        TEXT        NOT NULL DEFAULT 'medium',         -- low | medium | high | critical
    risk            TEXT        NOT NULL DEFAULT 'low',            -- low | medium | high
    area            TEXT,                                          -- "editor" | "sessions" | etc.
    target_version  TEXT,
    is_security     BOOLEAN     NOT NULL DEFAULT FALSE,
    submitted_by    TEXT        NOT NULL,
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    admin_notes     TEXT,
    -- Wizard step payloads (markdown bodies)
    requirements_md TEXT,
    implementation_md TEXT,
    testing_md      TEXT,
    review_md       TEXT,
    deleted_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS improvements_status_idx       ON improvements (status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS improvements_submitted_at_idx ON improvements (submitted_at DESC) WHERE deleted_at IS NULL;
