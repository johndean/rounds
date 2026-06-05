-- 052_chat_polls_order_index — Phase 6 of the 2026-06-04 stakeholder
-- remediation. Adds an `order_index INTEGER` nullable column to
-- chat_messages + polls so operators can drag-reorder rows within a
-- session's right-rail Chat / Polls tabs without losing the original
-- arrival-time ordering for un-reordered rows.
--
-- Backwards-compat strategy:
--   * order_index NULL for all existing rows (no migration of data).
--   * list endpoints use COALESCE(order_index, sent_at_ms) /
--     COALESCE(order_index, opened_at_ms) so un-reordered rows still
--     appear in chronological order.
--   * Drag-reorder sets order_index for every row in the list, in
--     ascending positional order (1, 2, 3, ...). The first reorder
--     promotes all rows to explicit order_index; subsequent reorders
--     only need to renumber. Operators can't end up in a half-NULL,
--     half-set state because the bulk endpoint is all-or-nothing.
--
-- No partial unique index on (session_id, order_index) — the bulk
-- endpoint is the only writer and assigns deterministic values, so
-- duplicates would require a backend bug rather than a race.

ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS order_index INTEGER;

ALTER TABLE polls
    ADD COLUMN IF NOT EXISTS order_index INTEGER;

-- Indexes to keep ORDER BY cheap on large sessions (chat threads can
-- exceed 100 rows; the COALESCE in the list query benefits from an
-- index on each ordering column individually).
CREATE INDEX IF NOT EXISTS chat_messages_order_idx
    ON chat_messages (session_id, order_index)
    WHERE order_index IS NOT NULL;

CREATE INDEX IF NOT EXISTS polls_order_idx
    ON polls (session_id, order_index)
    WHERE order_index IS NOT NULL;
