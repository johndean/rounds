"""
classify_discrepancies_task — Gemini-based classification of
transcription_discrepancies rows. Non-critical: failure NEVER marks
session as failed (session is already 'ready' when this runs).

Ports MIC `app/tasks/classify_task.py` (179 LOC) with the same custom
on_failure semantics:
  • Override on_failure → log + WS emit but DO NOT transition session
  • Reads org_settings.classify_backend + classify_model
  • Reads session_templates for per-session override (not used yet)
  • Batches in DISCREPANCY_BATCH_SIZE (32 default) chunks

Phase 6l / U124. Closes audit gap 🟠 #16.
"""
from __future__ import annotations

import json
import logging

from celery import Task

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


DISCREPANCY_BATCH_SIZE = 32


_CLASSIFY_PROMPT = """\
You are a strict transcript-classification assistant. For each input
discrepancy, return whether the change from `stt_text` to `ai_text` is
"meaningful" (semantically changes meaning, terminology, dose, or name)
or "noise" (filler removal, capitalization, punctuation only).

Output STRICT JSON, no prose. Shape:
  {"results": [{"id": "<id>", "is_meaningful": true|false, "category": "..."}]}

`category` must be one of:
  medication, terminology, name, number, date, filler, punctuation, style, drift, other.
"""


class _ClassifyTask(RoundsTask):
    """
    Override on_failure — classification is non-critical. Failed classify
    must NEVER mark the session as 'failed'. Log + WS emit only.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # noqa: ARG002, ANN001
        session_id = kwargs.get("session_id") or (args[0] if args else None)
        logger.warning(
            f"classify_discrepancies_task FAILED for session={session_id}: {exc} — "
            f"session status NOT changed (non-critical task)"
        )
        if session_id:
            try:
                from app.engines.ws_bridge import publish_ws_event_sync  # type: ignore

                publish_ws_event_sync(
                    session_id,
                    {"type": "classification_failed", "reason": str(exc)},
                )
            except ImportError:
                pass


@celery_app.task(
    bind=True,
    base=_ClassifyTask,
    name="rounds.tasks.classify_discrepancies",
    max_retries=3,
)
def classify_discrepancies_task(self, session_id: str) -> dict:
    """
    Load unclassified discrepancies → call Gemini in batches → write verdicts.
    Idempotent — already-classified rows are skipped.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.engines.llm_client import LLMError, classify_discrepancies

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, ai_text, stt_text, category
                      FROM transcription_discrepancies
                     WHERE session_id = CAST(:sid AS uuid)
                       AND is_meaningful IS NULL
                    """
                ),
                {"sid": session_id},
            ).fetchall()
            backend_row = conn.execute(
                text("SELECT value FROM org_settings WHERE key = 'classify_backend'")
            ).fetchone()
            model_row = conn.execute(
                text("SELECT value FROM org_settings WHERE key = 'classify_model'")
            ).fetchone()

        if not rows:
            logger.info(f"classify: no unclassified discrepancies for {session_id}")
            return {"classified": 0}

        backend = (backend_row[0] if backend_row else None) or "gemini-dev"
        model = (model_row[0] if model_row else None) or settings.GEMINI_CLASSIFY_MODEL
        if isinstance(backend, str) and backend.startswith('"'):
            backend = json.loads(backend)
        if isinstance(model, str) and model.startswith('"'):
            model = json.loads(model)

        items = [
            {"id": str(r[0]), "ai_text": r[1] or "", "stt_text": r[2] or "",
             "category_hint": r[3] or "other"}
            for r in rows
        ]
        batches = [items[i:i + DISCREPANCY_BATCH_SIZE]
                   for i in range(0, len(items), DISCREPANCY_BATCH_SIZE)]
        logger.info(f"classify: session={session_id} items={len(items)} batches={len(batches)} "
                    f"backend={backend} model={model}")

        classified_count = 0
        for batch_idx, batch in enumerate(batches):
            payload = json.dumps({"items": batch})
            try:
                result = classify_discrepancies(
                    _CLASSIFY_PROMPT, payload,
                    backend="vertex" if backend == "vertex" else "gemini",
                    model_id=model,
                )
            except LLMError as e:
                logger.warning(f"classify batch {batch_idx + 1} failed ({e.category}): {e}")
                continue

            results = result.get("results") or []
            with engine.begin() as conn:
                for r in results:
                    conn.execute(
                        text(
                            """
                            UPDATE transcription_discrepancies
                               SET is_meaningful   = :im,
                                   category        = COALESCE(:cat, category),
                                   classifier_model = :model,
                                   classified_at   = now()
                             WHERE id = CAST(:id AS uuid)
                            """
                        ),
                        {
                            "im":     bool(r.get("is_meaningful", False)),
                            "cat":    r.get("category"),
                            "model":  model,
                            "id":     r.get("id"),
                        },
                    )
                    classified_count += 1

        logger.info(f"classify: session={session_id} classified={classified_count}/{len(items)}")
        return {
            "session_id": session_id,
            "classified": classified_count,
            "total":      len(items),
            "backend":    backend,
            "model":      model,
        }

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        raise
    finally:
        engine.dispose()
