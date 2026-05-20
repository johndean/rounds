-- 036_word_alignment — Per-Gemini-word STT timestamp pairings (L2 highlight).
--
-- Background: the AI Transcript renders Gemini-cleaned segment text. The
-- previous per-word highlighter (MIC parity) used proportional time
-- interpolation (idx = floor(elapsed/duration * wordCount)) which drifts
-- because Gemini's word count != STT's word count and segment durations
-- for direct-pipeline sessions are fabricated (ai_process.py:283-292).
--
-- L2 fix: precompute an LCS pairing between each segment's Gemini words
-- and the STT words inside that segment. Every Gemini word that has an
-- STT match gets the exact STT (start_ms, end_ms). Unmatched Gemini words
-- (e.g. inserted/rewrote tokens) get NULL and the frontend skips them.
--
-- Population path: extended `lcs_discrepancies_task` writes these rows
-- in the same transaction that emits transcription_discrepancies, so
-- zero new STT/LLM calls. See app/tasks/lcs_discrepancies.py.
--
-- Storage budget: ~50 bytes/word × ~12k words for an hour-long lecture
-- = ~600 KB/session. Negligible.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS + ON CONFLICT-friendly PK.

CREATE TABLE IF NOT EXISTS word_alignment (
    segment_id   UUID    NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    gemini_idx   INTEGER NOT NULL,                -- 0-based position in seg.text.split()
    stt_word_id  UUID             REFERENCES words(id) ON DELETE SET NULL,
    stt_start_ms INTEGER,                         -- denormalized for O(1) frontend lookup
    stt_end_ms   INTEGER,
    match_kind   TEXT    NOT NULL,                -- 'exact' | 'fuzzy' | 'unmatched'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (segment_id, gemini_idx)
);

CREATE INDEX IF NOT EXISTS word_alignment_segment_idx
    ON word_alignment (segment_id);
