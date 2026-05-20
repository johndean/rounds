"""
align_task — 4-signal per-segment alignment + pre-ready gate.

Phase 6i ports MIC's real align engine. Reads segments + slides +
slide_time_ranges (from 6h fusion); writes alignments table; updates
segments.slide_id for editor display.

Two gates protect the persist transaction (mirrors MIC tasks/align.py:202-207):

  GATE 1 — fusion_output: if 6h fusion produced 0 slide_time_ranges,
    halt the session via state machine + audit_events row + WS event.
    Previously this path silently called _align_session_fallback (time-
    proportional bucketing), which produced complete-looking but
    arithmetic-noise alignments with no operator-visible diagnostic.
    The fallback function is removed.

  GATE 2 — pre_ready_gate (Section 11.4): run BEFORE the persist
    transaction. Previously a GateFailure was caught as a warning and
    per-segment status was downgraded to 'review' — but since the API
    doesn't surface alignment status (Cause C from the slide-align audit),
    that was effectively a no-op. Now: GateFailure halts the session
    identically to GATE 1.

Phase 6i / U108-U112 + slide-align audit R1. Closes audit gaps 🔴 #17, 🟠 #15.
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

        # GATE 1 — fusion output sanity check (Cause A from slide-align audit).
        # MIC halts the session when fusion produced 0 usable slide_time_ranges.
        # Rounds previously fell through to _align_session_fallback (time-
        # proportional bucketing), which produced a complete-looking but
        # arithmetic-noise alignment with no operator-visible diagnostic.
        if not slide_range_rows:
            reason = (
                "fusion produced 0 slide_time_ranges — cannot align. "
                "Likely causes: visual frame diff produced no boundaries, "
                "anchor extraction failed, or semantic ranges collapsed. "
                "Re-run fusion or inspect the upstream tasks."
            )
            logger.error(f"align: GATE FAILED for {session_id} — {reason}")
            _halt_session(engine, session_id, gate_id="fusion_output", reason=reason)
            return {
                "session_id": session_id,
                "halted": True,
                "gate": "fusion_output",
                "reason": reason,
            }

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

        # GATE 2 — pre-ready gate (Section 11.4). Mirrors MIC tasks/align.py:202-207.
        # Previously this caught GateFailure as a warning and downgraded
        # per-segment status from 'assigned' to 'review' — but the API never
        # surfaces alignment status (Cause C from the audit), so the gate was
        # effectively a no-op. Now: gate failure halts the session via the
        # state machine + audit_events row + WS event, exactly like MIC.
        try:
            run_pre_ready_gate(gate_input, iil_config or {}, session_template_id or "")
        except GateFailure as gf:
            reason = f"{gf.gate_id}: {gf.reason}"
            logger.error(f"align: GATE FAILED for {session_id} — {reason}")
            _halt_session(engine, session_id, gate_id=gf.gate_id, reason=gf.reason)
            return {
                "session_id": session_id,
                "halted": True,
                "gate": gf.gate_id,
                "reason": gf.reason,
            }

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
            # Verdict: APPROVE for assigned/clean, REVIEW for uncertain.
            # ESCALATE branch removed — gate failure now halts the session
            # before reaching this code (see GATE 2 above).
            for rec in results:
                if rec.uncertain_flag or rec.status == "review":
                    verdict = "REVIEW"
                else:
                    verdict = "APPROVE"
                details = {
                    "signals":    rec.signals,
                    "drift_flag": rec.drift_flag,
                    "anchor_hit": rec.anchor_hit,
                    "uncertain":  rec.uncertain_flag,
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


def _halt_session(engine, session_id: str, *, gate_id: str, reason: str) -> None:
    """Transition the session to 'failed' with durable diagnostic detail.

    Mirrors MIC's RoundsTask._fail_session pattern (tasks/align.py:202-207).
    Writes an audit_events row with the gate id + reason so the operator
    can inspect what fired without parsing rotated logs, then transitions
    via the state machine, then publishes a WS event so the live editor /
    processing view shows the failure instead of waiting on a finalize
    that will never come.
    """
    from sqlalchemy import text
    from app.engines.state_machine import ConflictError, transition_session_sync
    from app.engines.ws_bridge import publish_ws_event_sync

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
                    "VALUES (CAST(:sid AS uuid), NULL, 'align.gate_failure', :sum, CAST(:det AS jsonb))"
                ),
                {
                    "sid": session_id,
                    "sum": f"{gate_id}: {reason[:180]}",
                    "det": json.dumps({"gate": gate_id, "reason": reason}),
                },
            )
    except Exception as e:
        logger.warning(f"_halt_session: audit_events insert failed for {session_id}: {e}")

    try:
        transition_session_sync(session_id, "failed", actor="align_gate")
    except ConflictError as e:
        logger.warning(f"_halt_session: state transition conflict for {session_id}: {e}")
    except Exception as e:
        logger.error(f"_halt_session: state transition failed for {session_id}: {e}")

    try:
        publish_ws_event_sync(session_id, {
            "type":   "align_gate_failed",
            "gate":   gate_id,
            "reason": reason,
        })
    except Exception as e:
        logger.warning(f"_halt_session: ws publish failed for {session_id}: {e}")


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

        # If GATE 1 or GATE 2 halted the session, do NOT advance the state
        # machine or fire finalize. The session is already in 'failed' state
        # with an audit_events row and a WS event; let the operator inspect.
        if result.get("halted"):
            logger.info(f"align: halted by gate for {session_id} — finalize NOT triggered")
            return result

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
