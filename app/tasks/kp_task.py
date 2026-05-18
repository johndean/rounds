"""
kp_task — extracts key-point annotations + learns instructor IIL patterns.

Two tasks here (matches MIC's kp_task.py):
  • kp_task        — extracts segment-level key points via Gemini text call.
  • learn_iil_task — folds this session's signals into instructor_profiles.

Triggered after session lands ready (from finalize_task on the standard
chain, or directly by ai_process for the direct path).

Phase 6q / U147-U148.
"""
from __future__ import annotations

import json
import logging

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.kp",
    max_retries=2,
)
def kp_task(self, session_id: str) -> dict:
    """
    Extract per-segment key-point annotations using the rule-based engine
    in `app/iil/key_points.py`. Enforces KP-01..KP-09 invariants.

    Activation gate (#48): when the session's template has
    `structure_extraction = False`, write key_points=[] / available=False
    for every segment and return early without computing candidates.

    Closes 🟠 #47 (was calling Gemini instead of rule-based engine) +
    🟠 #49 (iil/key_points.py was absent) + 🟡 #48 (activation gate).
    """
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.iil.key_points import extract_key_points

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM key_points_annotations WHERE session_id = CAST(:sid AS uuid) LIMIT 1"),
                {"sid": session_id},
            ).fetchone()
            if existing:
                logger.info(f"kp: skip — annotations exist for {session_id}")
                return {"skipped": True}

            # Activation gate from template (#48).
            template_row = conn.execute(
                text(
                    """
                    SELECT t.structure_extraction
                      FROM session_templates st
                      JOIN templates t ON t.id = st.template_id
                     WHERE st.session_id = CAST(:sid AS uuid)
                    """
                ),
                {"sid": session_id},
            ).fetchone()
            structure_extraction = bool(template_row[0]) if template_row else True

            seg_rows = conn.execute(
                text(
                    """
                    SELECT s.id, s.seq, s.text, s.slide_id,
                           coalesce(a.status, 'assigned') AS status
                      FROM segments s
                      LEFT JOIN alignments a ON a.segment_id = s.id
                     WHERE s.session_id = CAST(:sid AS uuid)
                     ORDER BY s.seq ASC
                    """
                ),
                {"sid": session_id},
            ).fetchall()

            # Slide bullet text per slide_id for KP-09 content source.
            bullet_rows = conn.execute(
                text(
                    """
                    SELECT slide_id, text FROM bullets
                     WHERE slide_id IN (
                       SELECT id FROM slides WHERE session_id = CAST(:sid AS uuid)
                     )
                    """
                ),
                {"sid": session_id},
            ).fetchall()
            bullets_by_slide: dict[str, list[str]] = {}
            for slide_id, btext in bullet_rows:
                bullets_by_slide.setdefault(str(slide_id), []).append(btext or "")

        if not seg_rows:
            return {"session_id": session_id, "key_points": 0}

        written = 0
        with engine.begin() as conn:
            for seg_id, _seq, seg_text, slide_id, status in seg_rows:
                slide_bullets = bullets_by_slide.get(str(slide_id), []) if slide_id else []
                result = extract_key_points(
                    segment_id=str(seg_id),
                    normalized_text=seg_text or "",
                    slide_id=str(slide_id) if slide_id else None,
                    status=status or "assigned",
                    slide_bullets=slide_bullets,
                    structure_extraction=structure_extraction,
                )

                # Persist row even when available=False so the UI can render the
                # "no key points" state without ambiguity.
                conn.execute(
                    text(
                        """
                        INSERT INTO key_points_annotations
                            (session_id, segment_id, key_points, explanation,
                             available, extraction_confidence)
                        VALUES
                            (CAST(:sid AS uuid), :seg, CAST(:kps AS jsonb), :exp,
                             :av, :conf)
                        ON CONFLICT (session_id, segment_id) DO UPDATE
                          SET key_points = EXCLUDED.key_points,
                              explanation = EXCLUDED.explanation,
                              available = EXCLUDED.available,
                              extraction_confidence = EXCLUDED.extraction_confidence
                        """
                    ),
                    {
                        "sid":  session_id,
                        "seg":  str(seg_id),
                        "kps":  json.dumps(result.key_points),
                        "exp":  result.explanation or "",
                        "av":   result.available,
                        "conf": result.extraction_confidence,
                    },
                )
                if result.available:
                    written += 1

        # Trigger learn_iil after kp completes (per-instructor profile update).
        try:
            learn_iil_task.apply_async(args=[session_id], queue="celery")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"kp: failed to trigger learn_iil: {e}")

        logger.info(
            f"kp: session={session_id} key_points={written} "
            f"structure_extraction={structure_extraction}"
        )
        return {
            "session_id":           session_id,
            "key_points":           written,
            "structure_extraction": structure_extraction,
        }

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        raise
    finally:
        engine.dispose()


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.learn_iil",
    max_retries=1,
)
def learn_iil_task(self, session_id: str) -> dict:
    """
    Update instructor_profiles + session_patterns based on this session.
    Non-fatal — failure NEVER marks session as failed.

    Phase 7f: replaces the simple bucketing with real feature extraction
    via app/iil/adaptive_learning.py. Now computes:
      - rolling-average filler_rate across all sessions for the instructor
      - rolling-average compression_ratio across all segments
      - discovered filler_words list (frequency > 3%)
    Patterns table still holds the bucket labels for UI/dashboards.
    """
    import json
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.iil.adaptive_learning import update_instructor_profile

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            sess = conn.execute(
                text("SELECT presenter, duration_sec, segment_count FROM sessions WHERE id = CAST(:sid AS uuid)"),
                {"sid": session_id},
            ).fetchone()
            if not sess:
                return {"skipped": True, "reason": "no_session"}

            speaker = conn.execute(
                text(
                    """
                    SELECT name, credentials, bio FROM session_speakers
                     WHERE session_id = CAST(:sid AS uuid)
                       AND role = 'primary'
                     LIMIT 1
                    """
                ),
                {"sid": session_id},
            ).fetchone()

            slide_count_row = conn.execute(
                text("SELECT COUNT(*) FROM slides WHERE session_id = CAST(:sid AS uuid)"),
                {"sid": session_id},
            ).fetchone()
            kp_count_row = conn.execute(
                text("SELECT COUNT(*) FROM key_points_annotations WHERE session_id = CAST(:sid AS uuid)"),
                {"sid": session_id},
            ).fetchone()

            # Phase 7f — pull this session's normalize audit (tier1/2 removed
            # lists + compression ratios) so adaptive_learning can compute
            # real features.
            norm_rows = conn.execute(
                text(
                    """
                    SELECT nr.validation_results, s.text
                      FROM normalization_results nr
                      JOIN segments s ON s.id = nr.segment_id
                     WHERE nr.session_id = CAST(:sid AS uuid)
                    """
                ),
                {"sid": session_id},
            ).fetchall()

        instructor_name = (speaker[0] if speaker else sess[0]) or "Unknown"
        instructor_creds = speaker[1] if speaker else None
        instructor_bio = speaker[2] if speaker else None
        duration_min = (sess[1] or 0) // 60

        # Build engine inputs
        session_patterns: list[dict] = []
        normalization_stats: list[dict] = []
        for vr, raw_text in norm_rows:
            audit = vr if isinstance(vr, dict) else (json.loads(vr) if vr else {})
            session_patterns.append({
                "tier1_removed": audit.get("tier1_removed", []),
                "tier2_removed": audit.get("tier2_removed", []),
            })
            normalization_stats.append({
                "filler_count":      audit.get("filler_count", 0),
                "compression_ratio": audit.get("compression", 1.0),
                "raw_text":          raw_text or "",
            })

        with engine.begin() as conn:
            # Upsert profile row first to get current_profile
            row = conn.execute(
                text(
                    """
                    INSERT INTO instructor_profiles (name, credentials, bio, avg_session_min, sample_count)
                    VALUES (:n, :c, :b, :d, 0)
                    ON CONFLICT (name) DO UPDATE
                      SET credentials = COALESCE(instructor_profiles.credentials, EXCLUDED.credentials),
                          bio         = COALESCE(instructor_profiles.bio, EXCLUDED.bio),
                          updated_at  = now()
                    RETURNING id, filler_words, avg_filler_rate, avg_compression_ratio, sample_count
                    """
                ),
                {"n": instructor_name, "c": instructor_creds, "b": instructor_bio, "d": int(duration_min)},
            ).fetchone()
            instructor_id = row[0] if row else None
            current_profile = {
                "filler_words":         list(row[1] or []) if row else [],
                "avg_filler_rate":      row[2] if row else 0.0,
                "avg_compression_ratio": row[3] if row else 1.0,
                "sessions_processed":   row[4] if row else 0,
            }

            # Run feature extraction
            update = update_instructor_profile(
                session_id=session_id,
                instructor_id=str(instructor_id) if instructor_id else "",
                session_patterns=session_patterns,
                normalization_stats=normalization_stats,
                current_profile=current_profile,
            )

            # Persist computed features
            conn.execute(
                text(
                    """
                    UPDATE instructor_profiles
                       SET filler_words          = CAST(:fw AS jsonb),
                           avg_filler_rate       = :fr,
                           avg_compression_ratio = :cr,
                           sample_count          = :sc,
                           avg_session_min       = ((COALESCE(avg_session_min, 0) * :prior_n) + :d) / :sc,
                           updated_at            = now()
                     WHERE id = :iid
                    """
                ),
                {
                    "fw":       json.dumps(update.filler_words),
                    "fr":       update.avg_filler_rate,
                    "cr":       update.avg_compression_ratio,
                    "sc":       update.sessions_processed,
                    "prior_n":  current_profile["sessions_processed"],
                    "d":        int(duration_min),
                    "iid":      instructor_id,
                },
            )

            if instructor_id:
                conn.execute(
                    text(
                        """
                        INSERT INTO session_instructor_map (session_id, instructor_id, matched_by, confidence)
                        VALUES (CAST(:sid AS uuid), :iid, :mb, 1.0)
                        ON CONFLICT (session_id) DO UPDATE
                          SET instructor_id = EXCLUDED.instructor_id,
                              matched_by    = EXCLUDED.matched_by
                        """
                    ),
                    {"sid": session_id, "iid": str(instructor_id),
                     "mb": "manifest" if speaker else "presenter_field"},
                )

            # session_patterns table — still capture bucket labels for UI
            patterns = []
            seg_count = sess[2] or 0
            if seg_count:
                patterns.append(("density_low" if seg_count < 30
                                  else "density_med" if seg_count < 80
                                  else "density_high", 1))
            slide_count = slide_count_row[0] if slide_count_row else 0
            if slide_count:
                patterns.append((f"slides_{min(50, (slide_count // 10) * 10)}", 1))
            kp_count = kp_count_row[0] if kp_count_row else 0
            if kp_count:
                patterns.append(("kp_dense" if kp_count > 10 else "kp_sparse", 1))
            # Phase 7f — also record measured filler_rate as a numeric pattern
            patterns.append((
                "filler_high" if update.avg_filler_rate > 0.05
                else "filler_med" if update.avg_filler_rate > 0.02
                else "filler_low",
                1,
            ))

            for pattern_name, freq in patterns:
                conn.execute(
                    text(
                        """
                        INSERT INTO session_patterns (session_id, pattern_name, frequency)
                        VALUES (CAST(:sid AS uuid), :n, :f)
                        ON CONFLICT (session_id, pattern_name) DO UPDATE
                          SET frequency = session_patterns.frequency + EXCLUDED.frequency
                        """
                    ),
                    {"sid": session_id, "n": pattern_name, "f": freq},
                )

        logger.info(
            f"learn_iil: session={session_id} instructor={instructor_name} "
            f"filler_rate={update.avg_filler_rate:.4f} "
            f"compression={update.avg_compression_ratio:.4f} "
            f"new_fillers={len(update.filler_words) - len(current_profile['filler_words'])}"
        )
        return {
            "session_id":          session_id,
            "instructor":          instructor_name,
            "avg_filler_rate":     update.avg_filler_rate,
            "avg_compression":     update.avg_compression_ratio,
            "filler_words":        update.filler_words,
            "sessions_processed":  update.sessions_processed,
        }

    except Exception as exc:  # noqa: BLE001
        logger.warning(f"learn_iil: non-fatal failure — {exc}")
        return {"session_id": session_id, "error": str(exc)}
    finally:
        engine.dispose()
