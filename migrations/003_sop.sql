-- 003_sop — SOP workflow state machine + per-stage approvals.
-- 8 stages per IMPLEMENTATION.md §8 / §9 Pipeline 2:
--   prep · copy_draft · medical · copy_final · cms · captions · qa · complete

CREATE TABLE IF NOT EXISTS sop_state (
    session_id          UUID        PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    current_stage       TEXT        NOT NULL DEFAULT 'prep',
    is_blocked          BOOLEAN     NOT NULL DEFAULT FALSE,
    blockers            JSONB       NOT NULL DEFAULT '[]'::jsonb,  -- [{check_id, reason, raised_at}]
    assignees           JSONB       NOT NULL DEFAULT '{}'::jsonb,  -- {prep: {email,name,role}, copy_draft: ...}
    entered_current_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    sla_target_hours    JSONB       NOT NULL DEFAULT '{}'::jsonb,  -- {prep: 8, copy_draft: 24, ...}
    metadata            JSONB       NOT NULL DEFAULT '{}'::jsonb,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sop_state_stage_idx ON sop_state (current_stage);

-- ─── Stage transitions (append-only audit) ──────────────────────────────
CREATE TABLE IF NOT EXISTS sop_transitions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    from_stage      TEXT,                                          -- NULL on initial entry
    to_stage        TEXT        NOT NULL,
    actor_email     TEXT        NOT NULL,
    note            TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sop_transitions_session_idx ON sop_transitions (session_id, occurred_at DESC);

-- ─── Stage check resolutions ────────────────────────────────────────────
-- Acceptance-check rows per stage. Each can be resolved/raised independently.
CREATE TABLE IF NOT EXISTS sop_checks (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    stage           TEXT        NOT NULL,
    check_id        TEXT        NOT NULL,                          -- "medical.dosage_review", etc.
    label           TEXT        NOT NULL,
    is_resolved     BOOLEAN     NOT NULL DEFAULT FALSE,
    resolved_by     TEXT,
    resolved_at     TIMESTAMPTZ,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (session_id, stage, check_id)
);

CREATE INDEX IF NOT EXISTS sop_checks_stage_idx ON sop_checks (session_id, stage);

-- ─── Approvals (append-only signatures) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS sop_approvals (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    stage           TEXT        NOT NULL,
    actor_email     TEXT        NOT NULL,
    signature       TEXT        NOT NULL,                          -- arbitrary signoff string
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sop_approvals_session_idx ON sop_approvals (session_id, stage);
