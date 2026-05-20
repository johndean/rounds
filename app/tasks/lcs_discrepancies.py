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
    from app.engines.diff import align_words, diff_words

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM transcription_discrepancies WHERE session_id = CAST(:sid AS uuid) LIMIT 1"),
                {"sid": session_id},
            ).fetchone()
            existing_alignment = conn.execute(
                text(
                    """
                    SELECT 1
                      FROM word_alignment wa
                      JOIN segments s ON s.id = wa.segment_id
                     WHERE s.session_id = CAST(:sid AS uuid)
                     LIMIT 1
                    """
                ),
                {"sid": session_id},
            ).fetchone()

            # When discrepancies already exist we still want to (re)build the
            # alignment table if it's empty — the table was added in migration
            # 036 after some sessions had already produced discrepancies, so
            # the old skip would have starved them of L2 highlight data.
            if existing and existing_alignment:
                logger.info(f"lcs_discrepancies: skip — discrepancies + alignment exist for {session_id}")
                return {"skipped": True}

            write_diffs = existing is None
            write_alignment = existing_alignment is None

            # Pair each segment with its raw STT (via words) + normalized
            # text (via normalization_results). We also fetch the per-word
            # id / start_ms / end_ms vectors so L2 alignment can denormalize
            # timestamps into word_alignment without a second roundtrip.
            rows = conn.execute(
                text(
                    """
                    SELECT s.id, s.text AS segment_text,
                           nr.normalized_text,
                           array_agg(w.word     ORDER BY w.seq) AS stt_words,
                           array_agg(w.id       ORDER BY w.seq) AS stt_ids,
                           array_agg(w.start_ms ORDER BY w.seq) AS stt_starts,
                           array_agg(w.end_ms   ORDER BY w.seq) AS stt_ends
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
        alignments_written = 0
        with engine.begin() as conn:
            for seg_id, segment_text, normalized_text, stt_words, stt_ids, stt_starts, stt_ends in rows:
                stt_words = stt_words or []
                stt_ids   = stt_ids   or []
                stt_starts = stt_starts or []
                stt_ends   = stt_ends   or []
                # array_agg over a missing LEFT JOIN yields [None]; flatten that.
                if stt_words == [None]:
                    stt_words, stt_ids, stt_starts, stt_ends = [], [], [], []

                # Pair-up positionally — array_agg ORDER BY w.seq guarantees
                # all four arrays line up.
                stt_clean: list[str] = []
                stt_meta:  list[tuple[str | None, int | None, int | None]] = []
                for w, wid, sm, em in zip(stt_words, stt_ids, stt_starts, stt_ends):
                    if not w:
                        continue
                    stt_clean.append(w)
                    stt_meta.append((str(wid) if wid else None, sm, em))

                # AI side: prefer normalized text (enhanced pipeline) but fall
                # back to segments.text (direct pipeline writes Gemini text
                # straight into segments.text without a normalization_results row).
                ai_text = normalized_text or segment_text or ""
                ai_tokens = ai_text.split()
                if not stt_clean and not ai_tokens:
                    continue

                if write_diffs:
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

                # L2 word-alignment population. Always run when alignment is
                # missing (cheap LCS walk over the same DP shape). For segments
                # with no STT words, every Gemini word goes in as 'unmatched'
                # so the frontend still gets a complete row set.
                if write_alignment and ai_tokens:
                    pairs = align_words(stt_clean, ai_tokens)
                    for p in pairs:
                        meta = stt_meta[p.stt_idx] if p.stt_idx is not None else (None, None, None)
                        stt_word_id, st_ms, en_ms = meta
                        conn.execute(
                            text(
                                """
                                INSERT INTO word_alignment
                                    (segment_id, gemini_idx, stt_word_id, stt_start_ms, stt_end_ms, match_kind)
                                VALUES
                                    (CAST(:seg AS uuid), :gidx,
                                     CASE WHEN :wid IS NULL THEN NULL ELSE CAST(:wid AS uuid) END,
                                     :st, :en, :kind)
                                ON CONFLICT (segment_id, gemini_idx) DO UPDATE
                                  SET stt_word_id  = EXCLUDED.stt_word_id,
                                      stt_start_ms = EXCLUDED.stt_start_ms,
                                      stt_end_ms   = EXCLUDED.stt_end_ms,
                                      match_kind   = EXCLUDED.match_kind
                                """
                            ),
                            {
                                "seg":  str(seg_id),
                                "gidx": p.ai_idx,
                                "wid":  stt_word_id,
                                "st":   st_ms,
                                "en":   en_ms,
                                "kind": p.match_kind,
                            },
                        )
                        alignments_written += 1

        logger.info(
            f"lcs_discrepancies: session={session_id} "
            f"diffs={diffs_written} alignments={alignments_written}"
        )

        # Kick classify (non-fatal — failure doesn't block ready transition).
        try:
            from app.tasks.classify_task import classify_discrepancies_task

            classify_discrepancies_task.apply_async(args=[session_id], queue="celery")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"lcs_discrepancies: failed to enqueue classify: {e}")

        return {
            "session_id":   session_id,
            "diffs":        diffs_written,
            "alignments":   alignments_written,
        }

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        # Non-fatal — discrepancies are an editor convenience, not a gate.
        logger.exception(f"lcs_discrepancies: terminal failure for {session_id}")
        return {"session_id": session_id, "error": str(exc)}
    finally:
        engine.dispose()
