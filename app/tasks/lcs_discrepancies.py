"""
lcs_discrepancies_task — produces transcription_discrepancies rows by
LCS-diffing each segment's raw STT vs normalized text.

Triggered after normalize_task completes. Each diff is initially
classified by the cheap heuristic; classify_discrepancies_task (6l) calls
Gemini to refine `is_meaningful` per row.

Phase 6l / U123.
"""
from __future__ import annotations

import logging

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.lcs_discrepancies",
    max_retries=2,
)
def lcs_discrepancies_task(self, session_id: str) -> dict:
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.engines.diff import diff_words

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM transcription_discrepancies WHERE session_id = CAST(:sid AS uuid) LIMIT 1"),
                {"sid": session_id},
            ).fetchone()
            if existing:
                logger.info(f"lcs_discrepancies: skip — exist for {session_id}")
                return {"skipped": True}

            # Pair each segment with its raw STT (via words) + normalized
            # text (via normalization_results).
            rows = conn.execute(
                text(
                    """
                    SELECT s.id, s.text AS normalized,
                           nr.normalized_text,
                           array_agg(w.word ORDER BY w.seq) AS stt_words
                      FROM segments s
                      LEFT JOIN normalization_results nr ON nr.segment_id = s.id
                      LEFT JOIN words w ON w.segment_id = s.id
                     WHERE s.session_id = CAST(:sid AS uuid)
                     GROUP BY s.id, s.text, nr.normalized_text
                     ORDER BY s.seq
                    """
                ),
                {"sid": session_id},
            ).fetchall()

        diffs_written = 0
        with engine.begin() as conn:
            for seg_id, segment_text, normalized_text, stt_words in rows:
                if not stt_words or stt_words == [None]:
                    continue
                stt_clean = [w for w in stt_words if w]
                ai_text = normalized_text or segment_text or ""
                ai_tokens = ai_text.split()
                if not stt_clean and not ai_tokens:
                    continue
                diffs = diff_words(stt_clean, ai_tokens)
                for d in diffs:
                    conn.execute(
                        text(
                            """
                            INSERT INTO transcription_discrepancies
                                (session_id, segment_id, ai_text, stt_text, category)
                            VALUES
                                (CAST(:sid AS uuid), CAST(:seg AS uuid), :ai, :stt, :cat)
                            """
                        ),
                        {
                            "sid": session_id,
                            "seg": str(seg_id),
                            "ai":  d.ai,
                            "stt": d.stt,
                            "cat": d.category,
                        },
                    )
                    diffs_written += 1

        logger.info(f"lcs_discrepancies: session={session_id} diffs={diffs_written}")

        # Kick classify (non-fatal — failure doesn't block ready transition).
        try:
            from app.tasks.classify_task import classify_discrepancies_task

            classify_discrepancies_task.apply_async(args=[session_id], queue="celery")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"lcs_discrepancies: failed to enqueue classify: {e}")

        return {"session_id": session_id, "diffs": diffs_written}

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        # Non-fatal — discrepancies are an editor convenience, not a gate.
        logger.exception(f"lcs_discrepancies: terminal failure for {session_id}")
        return {"session_id": session_id, "error": str(exc)}
    finally:
        engine.dispose()
