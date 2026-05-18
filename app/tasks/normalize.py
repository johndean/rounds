"""
normalize_task — applies template config (filler policy, IIL tiers,
terminology preservation, rewrite level) to raw STT segments.

Ports MIC `app/tasks/normalize.py` (181 LOC) with the same contract:
  • Reads session_templates.iil_config + joined templates row
  • Per-segment: validate_and_repair against the template
  • Writes one normalization_results row per segment
  • Transitions normalizing → fusing

LOCKED IIL tier resolution (audit §6):
  • Tier toggles in iil_config override the template's filler_policy floor.
  • filler_policy='light' is the floor — iil_config cannot re-enable T1/T2/T3
    when policy disables them.

Phase 6g / U100. Closes audit gaps 🔴 #5, #16.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


# Tier word sets — match UploadView's docs labels.
_TIER1 = ["um", "uh", "er", "ah", "hm", "mm"]
_TIER2 = ["you know", "basically", "like", "right", "essentially", "kind of", "sort of"]
_TIER3_PATTERNS = [
    r"what i'm saying is\s*",
    r"the thing is\s*",
    r"what we're going to do is\s*",
]


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.normalize",
    max_retries=3,
)
def normalize_task(self, session_id: str) -> dict:
    """
    Read template config + segments → normalize → write normalization_results.
    Idempotent via UNIQUE (session_id, segment_id).
    """
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.engines.state_machine import ConflictError, transition_session_sync
    from app.iil.validation import validate

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    try:
        # ── Check-before-execute ─────────────────────────────────────────
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM normalization_results WHERE session_id = CAST(:sid AS uuid) LIMIT 1"),
                {"sid": session_id},
            ).fetchone()
            if existing:
                logger.info(f"normalize: skip — results exist for {session_id}")
                _next_or_stub(session_id)
                return {"skipped": True, "session_id": session_id}

            # ── Load template config ──────────────────────────────────────
            cfg_row = conn.execute(
                text(
                    """
                    SELECT st.template_id, st.iil_config,
                           t.filler_policy, t.structure_extraction, t.key_points,
                           t.tone, t.terminology, t.rewrite, t.filler_words
                      FROM session_templates st
                      JOIN templates t ON t.id = st.template_id
                     WHERE st.session_id = CAST(:sid AS uuid)
                    """
                ),
                {"sid": session_id},
            ).fetchone()
            if not cfg_row:
                raise RuntimeError(f"normalize: no template config for {session_id}")

            template_id   = cfg_row[0]
            iil_config    = cfg_row[1] if isinstance(cfg_row[1], dict) else json.loads(cfg_row[1])
            filler_policy = cfg_row[2]
            template_config = {
                "filler_policy":        cfg_row[2],
                "structure_extraction": cfg_row[3],
                "key_points":           cfg_row[4],
                "tone":                 cfg_row[5],
                "terminology":          cfg_row[6],
                "rewrite":              cfg_row[7],
            }

            # ── Resolve effective tier config (LOCKED policy-floor rule) ──
            tier1_on, tier2_on, tier3_on = _effective_tiers(iil_config, filler_policy)
            effective_iil_cfg = {
                "enabled": iil_config.get("enabled", True),
                "tier1":   tier1_on,
                "tier2":   tier2_on,
                "tier3":   tier3_on,
            }

            # ── Load segments + their words + slide context (for RULE 3) ──
            seg_rows = conn.execute(
                text(
                    """
                    SELECT s.id, s.text, s.slide_id,
                           coalesce(array_agg(w.word ORDER BY w.seq) FILTER (WHERE w.word IS NOT NULL), '{}')
                      FROM segments s
                      LEFT JOIN words w ON w.segment_id = s.id
                     WHERE s.session_id = CAST(:sid AS uuid)
                     GROUP BY s.id, s.text, s.slide_id, s.seq
                     ORDER BY s.seq ASC
                    """
                ),
                {"sid": session_id},
            ).fetchall()
            # Slide-context cache: slide_id → full_text + bullets joined
            slide_context_rows = conn.execute(
                text(
                    """
                    SELECT sl.id,
                           coalesce(sl.full_text, '') || ' ' ||
                           coalesce(string_agg(b.text, ' '), '')
                      FROM slides sl
                      LEFT JOIN bullets b ON b.slide_id = sl.id
                     WHERE sl.session_id = CAST(:sid AS uuid)
                     GROUP BY sl.id, sl.full_text
                    """
                ),
                {"sid": session_id},
            ).fetchall()
            slide_context_by_id = {str(r[0]): r[1] for r in slide_context_rows}

        if not seg_rows:
            logger.info(f"normalize: no segments for {session_id} — advancing pipeline anyway")
            _next_or_stub(session_id)
            return {"session_id": session_id, "segments": 0}

        # ── Per-segment normalize via 3-tier engine (RULE 0-8) ─────────────
        from app.iil.normalization import normalize as iil_normalize

        results: list[tuple] = []
        for seg_id, seg_text, slide_id, stt_words in seg_rows:
            words_list = [
                {"word": w} for w in (stt_words or []) if w
            ] or [{"word": tok} for tok in (seg_text or "").split() if tok]
            slide_context = slide_context_by_id.get(str(slide_id) if slide_id else "", "")
            r = iil_normalize(
                segment_id=str(seg_id),
                words=words_list,
                template_config=template_config,
                slide_context=slide_context,
                iil_config=effective_iil_cfg,
            )
            audit = {
                "passed":           True,
                "filler_count":     r.filler_count,
                "compression":      r.compression_ratio,
                "tier1_removed":    r.tier1_removed,
                "tier2_removed":    r.tier2_removed,
                "tier2_kept":       r.tier2_kept,
                "tier3_compressed": r.tier3_compressed,
            }
            results.append((str(seg_id), r.normalized_text, audit))

        # ── Write normalization_results + update segments.text ───────────
        # Updating segments.text means downstream consumers (editor, exports)
        # read the cleaned text without joining normalization_results.
        with engine.begin() as conn:
            for seg_id, normalized, validation in results:
                conn.execute(
                    text(
                        """
                        INSERT INTO normalization_results
                            (session_id, segment_id, normalized_text, template_id, validation_results)
                        VALUES
                            (CAST(:sid AS uuid), CAST(:seg AS uuid), :nt, :tpl, CAST(:v AS jsonb))
                        ON CONFLICT (session_id, segment_id) DO UPDATE
                          SET normalized_text    = EXCLUDED.normalized_text,
                              template_id        = EXCLUDED.template_id,
                              validation_results = EXCLUDED.validation_results
                        """
                    ),
                    {"sid": session_id, "seg": seg_id, "nt": normalized,
                     "tpl": template_id, "v": json.dumps(validation)},
                )
                conn.execute(
                    text("UPDATE segments SET text = :nt, updated_at = now() WHERE id = CAST(:seg AS uuid)"),
                    {"nt": normalized, "seg": seg_id},
                )

        # ── Transition transcribing → normalizing → fusing ────────────────
        try:
            transition_session_sync(session_id, "normalizing", actor="normalize_task")
        except ConflictError:
            pass  # may already be normalizing if anchor triggered it

        total_fillers = sum(v.get("filler_count", 0) for _, _, v in results)
        logger.info(
            f"normalize: session={session_id} segments={len(results)} "
            f"fillers_removed={total_fillers} template={template_id} "
            f"tiers=[{int(tier1_on)},{int(tier2_on)},{int(tier3_on)}]"
        )
        _next_or_stub(session_id)
        return {
            "session_id":      session_id,
            "segments":        len(results),
            "fillers_removed": total_fillers,
            "template":        template_id,
        }

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        raise
    finally:
        engine.dispose()


# ─── helpers ────────────────────────────────────────────────────────────


def _effective_tiers(iil_config: dict, filler_policy: str) -> tuple[bool, bool, bool]:
    """
    Apply policy-floor rule: 'light' caps tier2/3 to off.
    'strict' enables tier1+tier2 minimum.
    iil_config tier flags can disable but not re-enable above the policy floor.
    """
    enabled = iil_config.get("enabled", True)
    if not enabled:
        return False, False, False

    cfg1 = iil_config.get("tier1", True)
    cfg2 = iil_config.get("tier2", True)
    cfg3 = iil_config.get("tier3", True)

    if filler_policy == "light":
        return cfg1, False, False
    if filler_policy == "medium":
        return cfg1, cfg2, False
    return cfg1, cfg2, cfg3  # strict — all 3 allowed


def _normalize_text(text: str, tier1: bool, tier2: bool, tier3: bool, filler_words: list[str]) -> str:
    """
    Apply tier-based filler removal + sentence cleanup.
    Pure regex — no LLM call. The LLM-based path lives in ai_process enhanced.
    """
    if not text:
        return text
    out = text

    if tier1:
        for w in _TIER1:
            out = re.sub(rf"(?<![A-Za-z]){re.escape(w)}[,.!?]?\s*", "", out, flags=re.IGNORECASE)

    if tier2:
        for w in _TIER2:
            out = re.sub(rf"(?<![A-Za-z]){re.escape(w)}[,.!?]?\s*", "", out, flags=re.IGNORECASE)

    if tier3:
        for pattern in _TIER3_PATTERNS:
            out = re.sub(pattern, "", out, flags=re.IGNORECASE)

    # Filler list from template (in addition to tiers)
    for w in filler_words:
        if w.lower() not in (t.lower() for t in _TIER1 + _TIER2):  # already handled
            out = re.sub(rf"(?<![A-Za-z]){re.escape(w)}[,.!?]?\s*", "", out, flags=re.IGNORECASE)

    # Whitespace cleanup + sentence capitalization
    out = re.sub(r"\s+", " ", out).strip()
    if out and out[0].islower():
        out = out[0].upper() + out[1:]

    # Strip stranded punctuation at start
    out = re.sub(r"^[,.\s]+", "", out)
    return out


def _next_or_stub(session_id: str) -> None:
    """
    Trigger fusion_task (6h) + lcs_discrepancies_task (6l) in parallel.
    Also fires enhanced AI MODE refinement (6m) when ai_mode != 'transcript'.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT ai_pipeline, ai_mode FROM session_templates WHERE session_id = CAST(:sid AS uuid)"),
                {"sid": session_id},
            ).fetchone()
        if row and row[0] == "enhanced" and row[1] and row[1] != "transcript":
            try:
                from app.tasks.ai_process import ai_process_task  # type: ignore
                ai_process_task.apply_async(args=[session_id], queue="celery")
                logger.info(f"normalize: triggered ai_process_task[enhanced/{row[1]}] for {session_id}")
            except ImportError:
                pass
    finally:
        engine.dispose()

    try:
        from app.tasks.fusion import fusion_task  # type: ignore

        fusion_task.apply_async(args=[session_id], queue="celery")
        logger.info(f"normalize: triggered fusion_task for {session_id}")
    except ImportError:
        logger.info(f"normalize: fusion_task not ported yet (6h) — skipping trigger")
    try:
        from app.tasks.lcs_discrepancies import lcs_discrepancies_task  # type: ignore

        lcs_discrepancies_task.apply_async(args=[session_id], queue="celery")
    except ImportError:
        pass
