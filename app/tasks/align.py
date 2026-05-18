"""
align_task — 4-signal per-segment alignment + pre-ready gate.

Phase 6i ports MIC's real align engine, replacing the time-proportional
stub. Reads segments + slides + slide_time_ranges (from 6h fusion);
writes alignments table; updates segments.slide_id for editor display.

When 6h hasn't produced slide_time_ranges (legacy path), falls back to
the proportional bucketing kept in _align_session_fallback so the
pipeline never blocks.

Phase 6i / U108-U112. Closes audit gaps 🔴 #17, 🟠 #15.
"""
from __future__ import annotations

import json
import logging

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


def _align_session(session_id: str) -> dict:
    """Pure function — callable from finalize_task without Celery binding."""
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.engines.alignment import (
        AlignmentRecord,
        SegmentInput,
        SlideRangeInput,
        align_segment,
    )
    from app.engines.pre_ready_gate import GateFailure, run_pre_ready_gate

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM alignments WHERE session_id = CAST(:sid AS uuid) LIMIT 1"),
                {"sid": session_id},
            ).fetchone()
            if existing:
                logger.info(f"align: skip — alignments exist for {session_id}")
                return {"skipped": True, "session_id": session_id}

            seg_rows = conn.execute(
                text(
                    """
                    SELECT id, seq, start_ms, end_ms, text
                      FROM segments WHERE session_id = CAST(:sid AS uuid)
                      ORDER BY seq ASC
                    """
                ),
                {"sid": session_id},
            ).fetchall()
            slide_range_rows = conn.execute(
                text(
                    """
                    SELECT str.slide_id, sl.slide_index,
                           str.start_time, str.end_time,
                           str.slide_soft_start, str.slide_soft_end,
                           COALESCE(sl.title, ''), COALESCE(sl.title, '')
                      FROM slide_time_ranges str
                      LEFT JOIN slides sl ON sl.id = str.slide_id
                     WHERE str.session_id = CAST(:sid AS uuid)
                     ORDER BY str.start_time
                    """
                ),
                {"sid": session_id},
            ).fetchall()

        if not seg_rows:
            logger.info(f"align: no segments for {session_id}")
            return {"session_id": session_id, "assigned": 0, "slides": 0}

        # If 6h hasn't run, fall back to time-proportional bucketing.
        if not slide_range_rows:
            logger.info(f"align: no slide_time_ranges for {session_id} — fallback path")
            return _align_session_fallback(session_id, engine, seg_rows)

        # Build engine inputs
        segments = [
            SegmentInput(
                segment_id=str(r[0]),
                seq=r[1],
                start_time=(r[2] or 0) / 1000.0,
                end_time=(r[3] or 0) / 1000.0,
                text=r[4] or "",
            )
            for r in seg_rows
        ]
        slide_ranges = [
            SlideRangeInput(
                slide_id=str(r[0]) if r[0] else "",
                slide_number=r[1] if r[1] is not None else 0,
                start_time=float(r[2] or 0.0),
                end_time=float(r[3] or 0.0),
                soft_start=float(r[4] or 0.0),
                soft_end=float(r[5] or 0.0),
                full_text=r[6] or "",
                bullets=r[7] or "",
            )
            for r in slide_range_rows
            if r[0] is not None
        ]

        # Single placeholder speaker if none exist (matches old behavior).
        with engine.connect() as conn:
            speaker_row = conn.execute(
                text("SELECT id FROM speakers WHERE session_id = CAST(:sid AS uuid) LIMIT 1"),
                {"sid": session_id},
            ).fetchone()
        speaker_id = None
        if not speaker_row:
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
            speaker_id = speaker_row[0]

        # Align segments
        results: list[AlignmentRecord] = []
        prev_slide_number = None
        for seg in segments:
            rec = align_segment(
                seg, slide_ranges,
                w_semantic=settings.ALIGN_WEIGHT_SEMANTIC,
                w_coverage=settings.ALIGN_WEIGHT_COVERAGE,
                w_temporal=settings.ALIGN_WEIGHT_TEMPORAL,
                w_sequential=settings.ALIGN_WEIGHT_SEQUENTIAL,
                sequential_penalty=settings.ALIGN_SEQUENTIAL_PENALTY,
                prev_slide_number=prev_slide_number,
                drift_confidence_penalty=settings.IIL_DRIFT_CONFIDENCE_PENALTY,
            )
            results.append(rec)
            if rec.slide_id:
                # Find matching slide_number for next segment's sequential signal.
                match = next((s for s in slide_ranges if s.slide_id == rec.slide_id), None)
                if match:
                    prev_slide_number = match.slide_number

        # Phase 7b — pre-ready gate uses the 5 named gates from
        # app/engines/pre_ready_gate.py. We need to assemble a per-segment
        # dict with the fields each gate inspects: alignment record + segment
        # data + template id + normalized_text.
        with engine.connect() as conn:
            template_row = conn.execute(
                text("SELECT template_id, iil_config FROM session_templates WHERE session_id = CAST(:sid AS uuid)"),
                {"sid": session_id},
            ).fetchone()
            norm_rows = conn.execute(
                text(
                    """
                    SELECT segment_id, normalized_text, template_id
                      FROM normalization_results
                     WHERE session_id = CAST(:sid AS uuid)
                    """
                ),
                {"sid": session_id},
            ).fetchall()
        session_template_id = template_row[0] if template_row else None
        iil_config = template_row[1] if template_row else {}
        if isinstance(iil_config, str):
            iil_config = json.loads(iil_config)
        norm_by_seg = {str(r[0]): {"normalized_text": r[1], "template_id": r[2]} for r in norm_rows}

        # Build the gate input.
        gate_input: list[dict] = []
        seg_by_id = {s.segment_id: s for s in segments}
        for rec in results:
            seg = seg_by_id.get(rec.segment_id)
            norm_info = norm_by_seg.get(rec.segment_id, {})
            gate_input.append({
                "segment_id":      rec.segment_id,
                "start_time":      seg.start_time if seg else 0.0,
                "end_time":        seg.end_time if seg else 0.0,
                "text":            seg.text if seg else "",
                "confidence":      rec.confidence,
                "status":          rec.status,
                "slide_id":        rec.slide_id,
                "template_id":     norm_info.get("template_id") or session_template_id,
                "normalized_text": norm_info.get("normalized_text"),
            })

        gate_failures: list[GateFailure] = []
        try:
            run_pre_ready_gate(gate_input, iil_config or {}, session_template_id or "")
        except GateFailure as gf:
            logger.warning(f"align: gate failed for {session_id}: {gf} — marking review")
            gate_failures.append(gf)
            for rec in results:
                if rec.status == "assigned":
                    rec.status = "review"

        # Write alignments + update segments.slide_id + speaker_id
        with engine.begin() as conn:
            for rec in results:
                conn.execute(
                    text(
                        """
                        INSERT INTO alignments
                            (session_id, segment_id, slide_id, confidence, signals,
                             sources, drift_flag, anchor_hit, uncertain_flag, status)
                        VALUES
                            (CAST(:sid AS uuid), CAST(:seg AS uuid), :slide,
                             :conf, CAST(:sig AS jsonb), CAST(:src AS jsonb),
                             :drift, :anchor, :uncertain, :status)
                        ON CONFLICT (session_id, segment_id) DO UPDATE
                          SET slide_id       = EXCLUDED.slide_id,
                              confidence     = EXCLUDED.confidence,
                              signals        = EXCLUDED.signals,
                              drift_flag     = EXCLUDED.drift_flag,
                              anchor_hit     = EXCLUDED.anchor_hit,
                              uncertain_flag = EXCLUDED.uncertain_flag,
                              status         = EXCLUDED.status,
                              attempt_number = alignments.attempt_number + 1
                        """
                    ),
                    {
                        "sid":       session_id,
                        "seg":       rec.segment_id,
                        "slide":     rec.slide_id,
                        "conf":      rec.confidence,
                        "sig":       json.dumps(rec.signals),
                        "src":       json.dumps({"visual": 0.0, "anchor": 0.0, "semantic": 0.0}),
                        "drift":     rec.drift_flag,
                        "anchor":    rec.anchor_hit,
                        "uncertain": rec.uncertain_flag,
                        "status":    rec.status,
                    },
                )
                conn.execute(
                    text(
                        """
                        UPDATE segments
                           SET slide_id   = CAST(:slide AS uuid),
                               speaker_id = COALESCE(speaker_id, :spk)
                         WHERE id = CAST(:seg AS uuid)
                        """
                    ),
                    {
                        "slide": rec.slide_id,
                        "spk":   str(speaker_id) if speaker_id else None,
                        "seg":   rec.segment_id,
                    },
                )

            # Phase 7b — write validation_results rows for every alignment.
            # Verdict: APPROVE for assigned/clean, REVIEW for uncertain, ESCALATE
            # when any pre-ready gate failed (gate_failures non-empty).
            base_verdict = "ESCALATE" if gate_failures else "APPROVE"
            for rec in results:
                if base_verdict == "ESCALATE":
                    verdict = "ESCALATE"
                elif rec.uncertain_flag or rec.status == "review":
                    verdict = "REVIEW"
                else:
                    verdict = "APPROVE"
                details = {
                    "signals":      rec.signals,
                    "drift_flag":   rec.drift_flag,
                    "anchor_hit":   rec.anchor_hit,
                    "uncertain":    rec.uncertain_flag,
                    "gate_failures": [
                        {"gate": gf.gate_id, "reason": gf.reason}
                        for gf in gate_failures
                    ],
                }
                conn.execute(
                    text(
                        """
                        INSERT INTO validation_results (alignment_id, verdict, details)
                        SELECT a.id, :verdict, CAST(:d AS jsonb)
                          FROM alignments a
                         WHERE a.session_id = CAST(:sid AS uuid)
                           AND a.segment_id = CAST(:seg AS uuid)
                        """
                    ),
                    {
                        "verdict": verdict,
                        "d":       json.dumps(details),
                        "sid":     session_id,
                        "seg":     rec.segment_id,
                    },
                )

        assigned = sum(1 for r in results if r.status == "assigned")
        uncertain = sum(1 for r in results if r.uncertain_flag)
        drift = sum(1 for r in results if r.drift_flag)
        logger.info(
            f"align: session={session_id} segments={len(results)} assigned={assigned} "
            f"uncertain={uncertain} drift={drift}"
        )
        return {
            "session_id": session_id,
            "assigned":   assigned,
            "uncertain":  uncertain,
            "drift":      drift,
            "slides":     len(slide_ranges),
        }
    finally:
        engine.dispose()


def _align_session_fallback(session_id: str, engine, seg_rows: list) -> dict:
    """Time-proportional bucketing fallback used when no slide_time_ranges exist."""
    from sqlalchemy import text

    with engine.connect() as conn:
        slide_rows = conn.execute(
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

    speaker_id = None
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

    max_end = max(s[3] for s in seg_rows)
    slide_assignments: dict[int, list[tuple]] = {}
    if slide_rows:
        buckets = len(slide_rows)
        bucket_ms = max(1, max_end // buckets)
        for s in seg_rows:
            bucket = min(buckets - 1, s[2] // bucket_ms)
            slide_assignments.setdefault(bucket, []).append(s)
    else:
        slide_assignments[0] = list(seg_rows)

    with engine.begin() as conn:
        for s in seg_rows:
            conn.execute(
                text("UPDATE segments SET speaker_id = :spk WHERE id = :sid"),
                {"spk": speaker_id, "sid": s[0]},
            )
        for bucket_idx, bucket_segs in slide_assignments.items():
            if not slide_rows or bucket_idx >= len(slide_rows):
                continue
            slide_id = slide_rows[bucket_idx][0]
            for seg in bucket_segs:
                conn.execute(
                    text("UPDATE segments SET slide_id = :sl WHERE id = :seg"),
                    {"sl": slide_id, "seg": seg[0]},
                )
    return {"session_id": session_id, "assigned": len(seg_rows), "slides": len(slide_rows), "fallback": True}


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.align",
    max_retries=2,
)
def align_task(self, session_id: str) -> dict:
    from app.engines.state_machine import ConflictError, transition_session_sync

    try:
        result = _align_session(session_id)
        try:
            transition_session_sync(session_id, "aligning", actor="align_task")
        except ConflictError:
            pass
        # Trigger finalize for ready transition.
        try:
            from app.tasks.finalize import finalize_task

            finalize_task.apply_async(args=[session_id], queue="celery")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"align: failed to trigger finalize: {e}")
        return result
    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            logger.warning(f"align failed (attempt {attempt + 1}): {exc}")
            self.retry_with_backoff(exc, attempt)
        raise
