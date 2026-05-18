-- 008 — chat_messages + polls + poll_options
--
-- Backs the editor's right-rail Chat + Polls tabs and the inline anchor
-- blocks. Ingest pipeline (when it lands) will populate from Zoom recordings.
-- For now these tables are empty and the GET endpoints return [].

CREATE TABLE IF NOT EXISTS chat_messages (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    author          TEXT        NOT NULL,
    body            TEXT        NOT NULL,
    sent_at_ms      INTEGER     NOT NULL,                          -- ms offset from session start
    anchor_segment  UUID        REFERENCES segments(id) ON DELETE SET NULL,
    placed          BOOLEAN     NOT NULL DEFAULT false,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chat_messages_session_idx ON chat_messages (session_id);
CREATE INDEX IF NOT EXISTS chat_messages_anchor_idx  ON chat_messages (anchor_segment);


CREATE TABLE IF NOT EXISTS polls (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    question        TEXT        NOT NULL,
    opened_at_ms    INTEGER     NOT NULL,
    closed_at_ms    INTEGER,
    status          TEXT        NOT NULL DEFAULT 'open',           -- open | closed
    total_votes     INTEGER     NOT NULL DEFAULT 0,
    anchor_segment  UUID        REFERENCES segments(id) ON DELETE SET NULL,
    placed          BOOLEAN     NOT NULL DEFAULT false,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS polls_session_idx ON polls (session_id);


CREATE TABLE IF NOT EXISTS poll_options (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    poll_id         UUID        NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    label           TEXT        NOT NULL,
    seq             INTEGER     NOT NULL,
    votes           INTEGER     NOT NULL DEFAULT 0,
    UNIQUE (poll_id, seq)
);

CREATE INDEX IF NOT EXISTS poll_options_poll_idx ON poll_options (poll_id);
