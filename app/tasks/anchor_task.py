"""
anchor_task — combines frame_task visual signals + segment semantic shifts
into confirmed AnchorHit list. Stored in Redis for fusion_task (Phase 6h).

Ports MIC `app/tasks/anchor_task.py` (284 LOC) with the same contract:
  Reads visual signals from `rounds:frame:{id}` (frame_task output)
  Reads segments from DB (transcribe_task output)
  Computes semantic_shifts via adjacent-token overlap
  Calls detect_anchors() with LOCKED settings.ANCHOR_CROSS_VALIDATE_WINDOW
  Writes AnchorHit[] to Redis `rounds:anchor:{id}`
  Triggers normalize_task (no-op until 6g lands).

Reads frame_task output gracefully — proceeds with empty visual signals if
frame_task has not yet completed (matches MIC's degradation strategy).
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


_REDIS_ANCHOR_KEY = "rounds:anchor:{session_id}"
_REDIS_DONE_KEY   = "rounds:anchor:done:{session_id}"
_REDIS_SEMANTIC_KEY = "rounds:semantic:{session_id}"
_REDIS_TTL        = 86400


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.anchor",
    max_retries=3,
)
def anchor_task(self, session_id: str) -> dict:
    """Combine visual + semantic signals → confirmed AnchorHit list in Redis."""
    import redis as _redis

    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.engines.anchor import compute_semantic_shifts, detect_anchors
    from app.tasks.frame_task import load_visual_signals_from_redis

    r = _redis.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        done_key = _REDIS_DONE_KEY.format(session_id=session_id)
        if r.exists(done_key):
            logger.info(f"anchor_task: skip — done flag set for {session_id}")
            _trigger_normalize(session_id)
            return {"skipped": True, "session_id": session_id}

        sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        engine = create_engine(sync_url)
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT text, end_ms
                          FROM segments
                         WHERE session_id = CAST(:sid AS uuid)
                         ORDER BY seq ASC
                        """
                    ),
                    {"sid": session_id},
                ).fetchall()
        finally:
            engine.dispose()

        if not rows:
            raise RuntimeError(
                f"anchor_task: no segments for {session_id} — transcribe must run first"
            )

        # Compute semantic shifts at boundaries (end_ms / 1000 = seconds).
        segments = [(r[0] or "", (r[1] or 0) / 1000.0) for r in rows]
        semantic_shifts = compute_semantic_shifts(segments)

        # Visual signals from frame_task (may be empty if frame_task not run).
        visual_signals = load_visual_signals_from_redis(session_id)
        visual_timestamps = [v.timestamp for v in visual_signals]

        anchors = detect_anchors(
            visual_timestamps=visual_timestamps,
            semantic_shifts=semantic_shifts,
            cross_validate_window=settings.ANCHOR_CROSS_VALIDATE_WINDOW,
            semantic_threshold=0.3,  # locked per CLAUDE.md §7
        )

        anchor_dicts = [asdict(a) for a in anchors]
        shift_dicts = [asdict(s) for s in semantic_shifts]
        r.setex(_REDIS_ANCHOR_KEY.format(session_id=session_id), _REDIS_TTL, json.dumps(anchor_dicts))
        r.setex(_REDIS_SEMANTIC_KEY.format(session_id=session_id), _REDIS_TTL, json.dumps(shift_dicts))
        r.setex(done_key, _REDIS_TTL, "1")

        confirmed = sum(1 for a in anchors if a.confirmed)
        logger.info(
            f"anchor_task: session={session_id} anchors={len(anchors)} confirmed={confirmed} "
            f"visual={len(visual_signals)} semantic={len(semantic_shifts)}"
        )

        _trigger_normalize(session_id)
        return {
            "session_id":         session_id,
            "anchors":            len(anchors),
            "confirmed":          confirmed,
            "visual_signals":     len(visual_signals),
            "semantic_shifts":    len(semantic_shifts),
        }

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        raise
    finally:
        try:
            r.close()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"redis close ignored: {e}")


def _trigger_normalize(session_id: str) -> None:
    """Trigger normalize_task. No-op until 6g lands."""
    try:
        from app.tasks.normalize import normalize_task  # type: ignore

        normalize_task.apply_async(args=[session_id], queue="celery")
        logger.info(f"anchor_task: triggered normalize_task for {session_id}")
    except ImportError:
        logger.info(f"anchor_task: normalize_task not yet ported (6g) — skipping trigger")


def load_anchor_signals_from_redis(session_id: str) -> list:
    """Read AnchorHit[] from Redis. Returns [] if anchor_task hasn't run."""
    import redis as _redis

    from app.config import settings
    from app.engines.anchor import AnchorHit

    r = _redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        raw = r.get(_REDIS_ANCHOR_KEY.format(session_id=session_id))
        if not raw:
            return []
        return [AnchorHit(**d) for d in json.loads(raw)]
    finally:
        try:
            r.close()
        except Exception:  # noqa: BLE001
            pass


def load_semantic_shifts_from_redis(session_id: str) -> list:
    import redis as _redis

    from app.config import settings
    from app.engines.anchor import SemanticShift

    r = _redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        raw = r.get(_REDIS_SEMANTIC_KEY.format(session_id=session_id))
        if not raw:
            return []
        return [SemanticShift(**d) for d in json.loads(raw)]
    finally:
        try:
            r.close()
        except Exception:  # noqa: BLE001
            pass
