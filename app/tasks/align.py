"""
Align task — assign segments to slides + write slide windows.

First-pass aligner: time-proportional bucketing of segments across the slide
count. When a future `frame_task` writes visual change signals, the LOCKED
ALIGN_WEIGHT_* fusion (audit §6) replaces this.

The core work lives in `_align_session(session_id)` so `finalize_task` can
call it synchronously without entering Celery's bind-self plumbing.

Side-effect: writes a placeholder speakers row ("Presenter") if the session
has no speakers, so the editor's right rail has something to show. Real
speaker diarization is Phase 6b.
"""
from __future__ import annotations

import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _align_session(session_id: str) -> dict:
    """
    Pure function — no Celery binding. Reusable from `finalize_task` so we
    can chain align + status-flip atomically without re-entering the
    worker's bind/retry machinery.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            segs = conn.execute(
                text(
                    """
                    SELECT id, seq, start_ms, end_ms
                      FROM segments
                     WHERE session_id = CAST(:sid AS uuid)
                     ORDER BY seq ASC
                    """
                ),
                {"sid": session_id},
            ).fetchall()
            slides = conn.execute(
                text(
                    """
                    SELECT id, slide_index FROM slides
                     WHERE session_id = CAST(:sid AS uuid)
                     ORDER BY slide_index ASC
                    """
                ),
                {"sid": session_id},
            ).fetchall()
            speaker_existing = conn.execute(
                text("SELECT id FROM speakers WHERE session_id = CAST(:sid AS uuid) LIMIT 1"),
                {"sid": session_id},
            ).fetchone()

        if not segs:
            logger.info(f"align: no segments for {session_id} — nothing to do")
            return {"session_id": session_id, "assigned": 0, "slides": 0}

        if not speaker_existing:
            with engine.begin() as conn:
                row = conn.execute(
                    text(
                        """
                        INSERT INTO speakers (session_id, name, role, avatar_color)
                        VALUES (CAST(:sid AS uuid), 'Presenter', 'Instructor', '#2563eb')
                        RETURNING id
                        """
                    ),
                    {"sid": session_id},
                ).fetchone()
                speaker_id = row[0] if row else None
        else:
            speaker_id = speaker_existing[0]

        max_end = max(s[3] for s in segs)
        slide_assignments: dict[int, list[tuple]] = {}

        if slides:
            buckets = len(slides)
            bucket_ms = max(1, max_end // buckets)
            for s in segs:
                bucket = min(buckets - 1, s[2] // bucket_ms)
                slide_assignments.setdefault(bucket, []).append(s)
        else:
            slide_assignments[0] = list(segs)

        with engine.begin() as conn:
            for s in segs:
                conn.execute(
                    text("UPDATE segments SET speaker_id = :spk WHERE id = :sid"),
                    {"spk": speaker_id, "sid": s[0]},
                )
            for bucket_idx, bucket_segs in slide_assignments.items():
                if not slides or bucket_idx >= len(slides):
                    continue
                slide_id = slides[bucket_idx][0]
                bucket_start = min(seg[2] for seg in bucket_segs)
                bucket_end = max(seg[3] for seg in bucket_segs)
                conn.execute(
                    text(
                        """
                        UPDATE slides
                           SET start_ms = :st, end_ms = :et
                         WHERE id = :sid
                        """
                    ),
                    {"st": bucket_start, "et": bucket_end, "sid": slide_id},
                )
                for seg in bucket_segs:
                    conn.execute(
                        text("UPDATE segments SET slide_id = :sl WHERE id = :seg"),
                        {"sl": slide_id, "seg": seg[0]},
                    )

        logger.info(f"align: session={session_id} assigned={len(segs)} slides={len(slides)}")
        return {"session_id": session_id, "assigned": len(segs), "slides": len(slides)}
    finally:
        engine.dispose()


@celery_app.task(
    bind=True,
    name="rounds.tasks.align",
    max_retries=2,
    default_retry_delay=30,
)
def align_task(self, session_id: str) -> dict:
    try:
        return _align_session(session_id)
    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            logger.warning(f"align failed (attempt {attempt + 1}): {exc} — retrying")
            raise self.retry(exc=exc, countdown=30 * (attempt + 1))
        logger.exception(f"align: terminal failure for {session_id}")
        raise
