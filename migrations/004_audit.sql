-- 004_audit — global append-only event log for every wired UI action.

CREATE TABLE IF NOT EXISTS audit_events (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        REFERENCES sessions(id) ON DELETE SET NULL,  -- NULL for non-session events (login, settings)
    actor_email     TEXT,
    kind            TEXT        NOT NULL,                          -- "segment.edit", "sop.advance", "settings.save", "auth.login", ...
    summary         TEXT,                                          -- short human description
    details         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_session_idx ON audit_events (session_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS audit_events_actor_idx   ON audit_events (actor_email, occurred_at DESC);
CREATE INDEX IF NOT EXISTS audit_events_kind_idx    ON audit_events (kind, occurred_at DESC);
