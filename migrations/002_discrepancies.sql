-- 002_discrepancies — STT vs AI mode comparison + per-discrepancy classifications.

CREATE TABLE IF NOT EXISTS discrepancies (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    segment_id      UUID        REFERENCES segments(id) ON DELETE SET NULL,
    slide_id        UUID        REFERENCES slides(id)   ON DELETE SET NULL,
    kind            TEXT        NOT NULL,                          -- medication | name | number | date | terminology | filler | punctuation | style | other
    severity        TEXT        NOT NULL DEFAULT 'flagged',        -- flagged | meaningful | uncertain | drift | low_conf
    ai_text         TEXT,
    stt_text        TEXT,
    classification  JSONB       NOT NULL DEFAULT '{}'::jsonb,      -- Gemini/Vertex output: {backend, model, confidence, ...}
    is_resolved     BOOLEAN     NOT NULL DEFAULT FALSE,
    resolved_by     TEXT,                                          -- email of operator who marked resolved
    resolved_at     TIMESTAMPTZ,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS discrepancies_session_idx      ON discrepancies (session_id);
CREATE INDEX IF NOT EXISTS discrepancies_session_kind_idx ON discrepancies (session_id, kind);
CREATE INDEX IF NOT EXISTS discrepancies_open_idx         ON discrepancies (session_id) WHERE NOT is_resolved;

-- ─── Corrections (Word Track Changes ledger) ────────────────────────────
-- Append-only history of every text edit / reassign / speaker change.
CREATE TABLE IF NOT EXISTS corrections (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    segment_id      UUID        REFERENCES segments(id) ON DELETE SET NULL,
    actor_email     TEXT        NOT NULL,
    kind            TEXT        NOT NULL,                          -- edited | inserted_chat | slide_reassigned | speaker_change | annotation
    was             JSONB       NOT NULL DEFAULT '{}'::jsonb,      -- old state snapshot
    now_            JSONB       NOT NULL DEFAULT '{}'::jsonb,      -- new state snapshot ("now" is reserved)
    note            TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS corrections_session_idx       ON corrections (session_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS corrections_segment_idx       ON corrections (segment_id, occurred_at DESC);
