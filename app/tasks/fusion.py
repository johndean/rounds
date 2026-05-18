"""
fusion_task — runs the fusion engine + 5-assertion gate, writes
slide_time_ranges + replay_log, transitions fusing→aligning.

Ports MIC `app/tasks/fusion.py` (176 LOC). Phase 6h / U105-U106.
"""
from __future__ import annotations

import json
import logging

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.fusion",
    max_retries=3,
)
def fusion_task(self, session_id: str) -> dict:
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.engines.fusion import (
        AnchorSignal,
        GateFailure,
        SemanticShift,
        VisualSignal,
        run_fusion,
        run_fusion_gate,
    )
    from app.engines.state_machine import ConflictError, transition_session_sync
    from app.tasks.anchor_task import load_anchor_signals_from_redis, load_semantic_shifts_from_redis
    from app.tasks.frame_task import load_visual_signals_from_redis

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM slide_time_ranges WHERE session_id = CAST(:sid AS uuid) LIMIT 1"),
                {"sid": session_id},
            ).fetchone()
            if existing:
                logger.info(f"fusion: skip — slide_time_ranges exist for {session_id}")
                _next_or_stub(session_id)
                return {"skipped": True}

            # Total duration from sessions, slides count from slides table
            sess_row = conn.execute(
                text("SELECT duration_sec FROM sessions WHERE id = CAST(:sid AS uuid)"),
                {"sid": session_id},
            ).fetchone()
            if not sess_row or not sess_row[0]:
                raise RuntimeError(f"fusion: no duration for {session_id}")
            total_duration = float(sess_row[0])

            slide_rows = conn.execute(
                text("SELECT id, slide_index FROM slides WHERE session_id = CAST(:sid AS uuid) ORDER BY slide_index"),
                {"sid": session_id},
            ).fetchall()
            slide_count = len(slide_rows)

        # No slides? Single virtual slide for the whole session.
        if slide_count == 0:
            logger.info(f"fusion: no slides for {session_id} — single virtual range")
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO slide_time_ranges
                            (session_id, slide_id, start_time, end_time,
                             slide_soft_start, slide_soft_end, confidence, sources, status)
                        VALUES
                            (CAST(:sid AS uuid), NULL, 0, :end, 0, :end, 1.0,
                             CAST(:src AS jsonb), 'assigned')
                        """
                    ),
                    {"sid": session_id, "end": total_duration,
                     "src": json.dumps({"visual": 0.0, "anchor": 0.0, "semantic": 0.0})},
                )
            try:
                transition_session_sync(session_id, "fusing", actor="fusion_task")
            except ConflictError:
                pass
            _next_or_stub(session_id)
            return {"session_id": session_id, "ranges": 0, "virtual": True}

        # Load signals from Redis
        visual_dataclasses = load_visual_signals_from_redis(session_id)
        anchor_dataclasses = load_anchor_signals_from_redis(session_id)
        semantic_dataclasses = load_semantic_shifts_from_redis(session_id)

        # Convert engine.anchor types → engine.fusion types (same shape, different names)
        visual_signals = [
            VisualSignal(timestamp=v.timestamp, strength=v.strength, frame_idx=v.frame_idx)
            for v in visual_dataclasses
        ]
        # REG-1 fix: engines.anchor.AnchorHit shape changed in parity-3 (#83)
        # to (timestamp, phrase, confidence, visual_confirmed, speculative).
        # Map to engines.fusion.AnchorSignal which fusion's run_fusion expects.
        anchor_signals = []
        for a in anchor_dataclasses:
            # Backwards-compat: tolerate either the new AnchorHit fields or the
            # legacy AnchorSignal-shaped object (some Redis blobs may still be
            # mid-rollover).
            confirmed_attr = getattr(a, "confirmed", None)
            if confirmed_attr is None:
                # New AnchorHit shape — derive confirmed = not speculative.
                confirmed = not getattr(a, "speculative", True)
                visual_validated = getattr(a, "visual_confirmed", False)
            else:
                confirmed = confirmed_attr
                visual_validated = getattr(a, "visual_validated", False)
            anchor_signals.append(AnchorSignal(
                timestamp=a.timestamp,
                confirmed=confirmed,
                visual_validated=visual_validated,
                semantic_score=getattr(a, "semantic_score", 0.0),
                phrase=getattr(a, "phrase", ""),
                confidence=getattr(a, "confidence", 0.0),
            ))
        semantic_shifts = [
            SemanticShift(timestamp=s.timestamp, shift_score=s.shift_score)
            for s in semantic_dataclasses
        ]

        result = run_fusion(
            session_id=session_id,
            slide_count=slide_count,
            visual_signals=visual_signals,
            anchor_signals=anchor_signals,
            semantic_shifts=semantic_shifts,
            total_duration=total_duration,
            w_visual=settings.FUSION_WEIGHT_VISUAL,
            w_anchor=settings.FUSION_WEIGHT_ANCHOR,
            w_semantic=settings.FUSION_WEIGHT_SEMANTIC,
            boundary_threshold=settings.FUSION_BOUNDARY_THRESHOLD,
            soft_window=settings.SOFT_WINDOW_EXPANSION,
        )

        # Map slide_id by slide_index for FK population
        slide_id_by_index = {row[1]: str(row[0]) for row in slide_rows}

        # Gate
        run_fusion_gate(result.slide_time_ranges, total_duration, slide_count)

        # Write atomically
        with engine.begin() as conn:
            for r in result.slide_time_ranges:
                slide_id = slide_id_by_index.get(r.slide_number)
                conn.execute(
                    text(
                        """
                        INSERT INTO slide_time_ranges
                            (session_id, slide_id, start_time, end_time,
                             slide_soft_start, slide_soft_end, confidence, sources, status)
                        VALUES
                            (CAST(:sid AS uuid), :slide_id, :st, :et,
                             :sst, :set_, :conf, CAST(:src AS jsonb), :status)
                        """
                    ),
                    {
                        "sid":      session_id,
                        "slide_id": slide_id,
                        "st":       r.start_time,
                        "et":       r.end_time,
                        "sst":      r.slide_soft_start,
                        "set_":     r.slide_soft_end,
                        "conf":     r.confidence,
                        "src":      json.dumps(r.sources),
                        "status":   r.status,
                    },
                )
                # Also update slides.start_ms / end_ms for editor display
                if slide_id:
                    conn.execute(
                        text(
                            """
                            UPDATE slides
                               SET start_ms = :sm, end_ms = :em
                             WHERE id = :sid
                            """
                        ),
                        {"sm": int(r.start_time * 1000), "em": int(r.end_time * 1000),
                         "sid": slide_id},
                    )
            # Replay log (append-only)
            conn.execute(
                text(
                    """
                    INSERT INTO replay_log (session_id, input_hash, fusion_inputs, fusion_output)
                    VALUES (CAST(:sid AS uuid), :hash, CAST(:i AS jsonb), CAST(:o AS jsonb))
                    """
                ),
                {
                    "sid":  session_id,
                    "hash": result.input_hash,
                    "i":    json.dumps(result.inputs_dump),
                    "o":    json.dumps(result.output_dump),
                },
            )

        try:
            transition_session_sync(session_id, "fusing", actor="fusion_task")
        except ConflictError:
            pass

        logger.info(
            f"fusion: session={session_id} ranges={len(result.slide_time_ranges)} "
            f"visual={len(visual_signals)} anchor={len(anchor_signals)} sem={len(semantic_shifts)}"
        )
        _next_or_stub(session_id)
        return {
            "session_id": session_id,
            "ranges":     len(result.slide_time_ranges),
            "hash":       result.input_hash,
        }

    except GateFailure as gf:
        logger.error(f"fusion gate failed for {session_id}: {gf}")
        raise
    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        raise
    finally:
        engine.dispose()


def _next_or_stub(session_id: str) -> None:
    """Trigger align_task (6i replaces today's stub)."""
    try:
        from app.tasks.align import align_task

        align_task.apply_async(args=[session_id], queue="celery")
        logger.info(f"fusion: triggered align_task for {session_id}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"fusion: failed to trigger align: {e}")
