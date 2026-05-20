"""
Auto-placement of parsed polls onto their slide's first segment.

Port of MIC `app/services/poll_autoplace.py` adapted to Rounds' schema.

Background
----------
The extras2 manifest declares each poll with a `slide_n` (the 1-based slide
the poll was opened on during the live session). gcs_upload writes the
poll into the `polls` table with `metadata.slide_n` preserved JSONB. Until
this service runs, `polls.anchor_segment` is NULL and `placed = FALSE` —
the poll shows up in the right-rail Polls panel as unplaced, and the
operator has to drag it onto the transcript.

This service auto-anchors each unplaced poll to the first segment of its
declared slide (by start_ms, with seq as a tiebreaker). User drag-to-place
and drag-to-clear continue to work unchanged; once a user has placed a
poll, this service won't touch it (`WHERE anchor_segment IS NULL`).

Differences from MIC
--------------------
MIC writes a `poll_insert` correction row (its placement ledger). Rounds
uses the structured `polls.anchor_segment` column directly. That removes
the entire corrections-table dance, the action_id round-trip, the
sequence_number bump, and the JSON old_text/new_text payloads — one
UPDATE statement does the same work.

Convention note
---------------
- extras2 emits `slide_n` as 1-based (matches the manifest's "Slide 7 Poll" header).
- The `slides.slide_index` column is 0-based (set by ai_process.py:347 as `marker - 1`).
- We bridge with `slides.slide_index + 1 = metadata.slide_n` in the join.

Idempotency + safety
--------------------
- Re-running is a no-op once polls are placed (WHERE clause filters them out).
- Polls whose slide_n has no aligned segment (slide_index never assigned to
  any segment) are silently skipped — they stay unplaced and the operator
  can drag them manually.
- Wrapped at the call site in try/except so a transient failure here never
  blocks the session from transitioning to `ready`.

Performance
-----------
One SQL statement. The CTE scans `segments` filtered by session_id (PK
range scan) and DISTINCT-ON's per slide. For a typical 200-segment session
this is sub-10ms. Runs once per session at ingest completion.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger(__name__)


_AUTO_PLACE_SQL = """
WITH first_seg_per_slide AS (
    SELECT DISTINCT ON (sl.slide_index)
        sl.slide_index,
        seg.id          AS segment_id
      FROM segments seg
      JOIN slides   sl ON sl.id = seg.slide_id
     WHERE seg.session_id = CAST(:sid AS uuid)
       AND sl.session_id  = CAST(:sid AS uuid)
       AND seg.slide_id IS NOT NULL
     ORDER BY sl.slide_index, seg.start_ms ASC, seg.seq ASC
)
UPDATE polls p
   SET anchor_segment = fs.segment_id,
       placed         = TRUE
  FROM first_seg_per_slide fs
 WHERE p.session_id = CAST(:sid AS uuid)
   AND p.anchor_segment IS NULL
   AND p.metadata ? 'slide_n'
   AND (p.metadata->>'slide_n')::int = fs.slide_index + 1
 RETURNING p.id
"""


def auto_place_polls(engine_or_conn: "Engine | Connection", session_id: str) -> int:
    """
    Auto-anchor every unplaced poll in `session_id` to the first segment of
    its declared slide. Returns the number of polls newly placed.

    Accepts either a SQLAlchemy Engine (opens its own transaction) or an
    already-open Connection (joins the caller's transaction). The Connection
    overload lets ingest tasks fold this into their existing engine.begin()
    block so the placement lands atomically with the session's segment writes.
    """
    from sqlalchemy import text
    from sqlalchemy.engine import Connection

    sql = text(_AUTO_PLACE_SQL)
    params = {"sid": session_id}

    if isinstance(engine_or_conn, Connection):
        rows = engine_or_conn.execute(sql, params).fetchall()
        count = len(rows)
    else:
        with engine_or_conn.begin() as conn:
            rows = conn.execute(sql, params).fetchall()
            count = len(rows)

    if count > 0:
        logger.info(f"auto_place_polls: session={session_id} placed={count}")
        try:
            from app.engines.ws_bridge import publish_ws_event_sync
            publish_ws_event_sync(session_id, {
                "type":  "polls_autoplaced",
                "count": count,
            })
        except Exception as e:  # noqa: BLE001
            logger.debug(f"auto_place_polls: ws emit failed (non-fatal): {e}")
    else:
        logger.info(f"auto_place_polls: session={session_id} placed=0 (none unplaced or no slide matches)")

    return count
