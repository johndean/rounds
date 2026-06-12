-- 059_bulk_reassign_batches.sql — self-contained snapshot store for bulk
-- segment reassignment undo.
--
-- Plan ref: docs/plans/2026-06-11-001-polls-cms-publish-and-bulk-speaker-reassign.md (Item 2).
-- Additive table only — zero-risk, forward-only per ADR-011. Nothing else is altered.
--
-- Bulk reassign updates segments.speaker_id / slide_id directly (mirroring the
-- per-segment endpoints, which do NOT write the correction_ledger). This is
-- deliberately decoupled from the ledger pointer-undo (which reverts text edits
-- + split/merge only, never speaker/slide). For batches of <= 10 segments we
-- snapshot prior values here so a dedicated undo endpoint can restore them.
-- Batches larger than 10 are not undoable (prior_values left NULL); the UI
-- warns the operator before such an action.

CREATE TABLE IF NOT EXISTS bulk_reassign_batches (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id        UUID         NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    actor_email       TEXT         NOT NULL,
    kind              TEXT         NOT NULL,            -- 'speaker' | 'slide' | 'speaker+slide'
    target_speaker_id UUID,                             -- NULL when not reassigning speaker
    target_slide_id   UUID,                             -- NULL when not reassigning slide
    segment_count     INTEGER      NOT NULL,
    undoable          BOOLEAN      NOT NULL DEFAULT FALSE,
    undone            BOOLEAN      NOT NULL DEFAULT FALSE,
    -- [{segment_id, prior_speaker_id, prior_slide_id}] captured pre-update; NULL when not undoable.
    prior_values      JSONB,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    undone_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS bulk_reassign_batches_session_idx
    ON bulk_reassign_batches (session_id, created_at DESC);
