-- 037_backfill_poll_anchors — Persist anchor_segment for every unplaced poll
-- across every session.
--
-- Background: the auto-placement service (app/services/poll_autoplace.py)
-- was added in commit a409fdc and only runs at the end of new ingests.
-- Every session ingested before that commit has polls in the `polls` table
-- with their declared `metadata.slide_n` but anchor_segment IS NULL — the
-- editor showed them as "0 PLACED" and the operator had to drag manually.
--
-- This migration runs the same algorithm as auto_place_polls() but across
-- every session at once. Idempotent: WHERE anchor_segment IS NULL means
-- already-placed polls are untouched.
--
-- Convention reminder:
--   extras2 emits slide_n as 1-based ("Slide 7 Poll Question #1").
--   slides.slide_index is 0-based.
--   Bridge: slides.slide_index + 1 = poll.metadata.slide_n.

WITH first_seg_per_slide AS (
    SELECT DISTINCT ON (sl.session_id, sl.slide_index)
        sl.session_id,
        sl.slide_index,
        seg.id AS segment_id
      FROM segments seg
      JOIN slides   sl ON sl.id = seg.slide_id
     WHERE seg.slide_id IS NOT NULL
     ORDER BY sl.session_id, sl.slide_index, seg.start_ms ASC, seg.seq ASC
)
UPDATE polls p
   SET anchor_segment = fs.segment_id,
       placed         = TRUE
  FROM first_seg_per_slide fs
 WHERE p.session_id = fs.session_id
   AND p.anchor_segment IS NULL
   AND p.metadata ? 'slide_n'
   AND (p.metadata->>'slide_n')::int = fs.slide_index + 1;
