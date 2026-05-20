"""
/v1/sessions/{session_id}/word-alignment — per-Gemini-word STT timing pairs.

L2 word-highlight backbone. The editor fetches this once on load and uses
the (stt_start_ms, stt_end_ms) pairs to anchor karaoke highlighting on the
AI Transcript tab to real audio timing instead of MIC's broken proportional
interpolation (which drifted by 2+ sentences over an hour-long recording).

Rows are written by `lcs_discrepancies_task` (see app/tasks/lcs_discrepancies.py)
right after STT lands. Direct-pipeline sessions get them via the
stt_background_task → lcs_discrepancies_task chain that ai_process_task
fires; enhanced-pipeline sessions get them via the standard normalize →
lcs_discrepancies flow.

Sessions uploaded before migration 036 returned no rows; the editor's
SegmentText falls through to the legacy whole-text render path in that
case (no per-word highlight, but no crash).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(
    prefix="/v1/sessions/{session_id}/word-alignment",
    tags=["word-alignment"],
)


class AlignmentEntry(BaseModel):
    """One Gemini word's per-token alignment row. Field names are short
    so the JSON payload stays compact — for an hour-long lecture this
    endpoint returns ~12k entries, ~16 bytes per entry on the wire."""
    g: int                      # gemini_idx (0-based position in seg.text.split())
    s: Optional[int]            # stt_start_ms — null when match_kind='unmatched'
    e: Optional[int]            # stt_end_ms — null when match_kind='unmatched'
    k: str                      # match_kind: 'exact' | 'unmatched'


class WordAlignmentResponse(BaseModel):
    session_id: UUID
    count:      int             # total alignment rows (matched + unmatched)
    matched:    int             # rows with non-null stt timestamps
    segments:   dict[str, list[AlignmentEntry]]


@router.get("", response_model=WordAlignmentResponse)
async def get_word_alignment(
    session_id: UUID,
    db:         DbSession,
    _u:         CurrentUser,
) -> dict:
    """
    Return every Gemini word's alignment row, grouped by segment_id.

    Frontend stores this as `Map<segment_id, AlignmentEntry[]>` and looks
    up by index when rendering. The (g) field equals the 0-based index
    into `seg.text.split()` — keep that invariant when splitting on the
    frontend (no trim/normalize).
    """
    rows = (await db.execute(text(
        """
        SELECT wa.segment_id::text AS segment_id,
               wa.gemini_idx,
               wa.stt_start_ms,
               wa.stt_end_ms,
               wa.match_kind
          FROM word_alignment wa
          JOIN segments s ON s.id = wa.segment_id
         WHERE s.session_id = CAST(:sid AS uuid)
         ORDER BY wa.segment_id, wa.gemini_idx
        """
    ), {"sid": str(session_id)})).mappings().all()

    grouped: dict[str, list[AlignmentEntry]] = {}
    matched = 0
    for r in rows:
        seg_id = r["segment_id"]
        entry = {
            "g": r["gemini_idx"],
            "s": r["stt_start_ms"],
            "e": r["stt_end_ms"],
            "k": r["match_kind"],
        }
        if r["stt_start_ms"] is not None:
            matched += 1
        grouped.setdefault(seg_id, []).append(entry)  # type: ignore[arg-type]

    return {
        "session_id": session_id,
        "count":      len(rows),
        "matched":    matched,
        "segments":   grouped,
    }
