"""
classify_discrepancies_task — Gemini-based classification of
transcription_discrepancies rows. Non-critical: failure NEVER marks
session as failed (session is already 'ready' when this runs).

Ports MIC `app/tasks/classify_task.py` (179 LOC) with the same partial-
result + auto-retry semantics:
  • Override on_failure → log + WS emit but DO NOT transition session
  • Reads org_settings.classify_backend + classify_model
  • Reads session_templates for per-session override (not used yet)
  • Engine layer (llm_client.classify_discrepancies) does the 15-item
    batching, per-batch retry of missing ids, and partial-success return
  • Partial classification (some items still NULL) raises LLMError to
    trigger Celery retry on the remaining items only

Phase 6l / U124. Closes audit gap 🟠 #16 + Phase 5 of audit remediation
(MIC parity for discrepancy batching + fence-strip + per-batch retry).
"""
from __future__ import annotations

import json
import logging
import uuid

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


class _ClassifyTask(RoundsTask):
    """
    Override on_failure — classification is non-critical. A failed classify
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
    Load discrepancies → engine batches + classifies → write verdicts.
    Idempotent — already-classified rows are skipped on subsequent runs.

    Partial classification (some items still NULL after engine returns
    partial) raises LLMError to trigger Celery's 60s/120s/240s backoff
    chain. Each retry re-loads, skips done rows, and tries again.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.engines.llm_client import LLMError, classify_discrepancies
    from app.engines.ws_bridge import publish_ws_event_sync

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, ai_text, stt_text, is_meaningful
                      FROM transcription_discrepancies
                     WHERE session_id = CAST(:sid AS uuid)
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
            logger.info(f"classify: no discrepancies for {session_id}")
            return {"classified": 0, "meaningful": 0, "noise": 0}

        backend = (backend_row[0] if backend_row else None) or "gemini-dev"
        model = (model_row[0] if model_row else None) or settings.GEMINI_CLASSIFY_MODEL
        # org_settings.value is jsonb — unwrap quoted strings
        if isinstance(backend, str) and backend.startswith('"'):
            backend = json.loads(backend)
        if isinstance(model, str) and model.startswith('"'):
            model = json.loads(model)

        use_vertex = (backend == "vertex")

        # Separate already-classified from pending — engine skips dones,
        # but we also need the counts for the partial-retry decision.
        already_classified_ids: set[str] = set()
        items: list[dict] = []
        for r in rows:
            rid = str(r[0])
            ai_text, stt_text, is_meaningful = r[1], r[2], r[3]
            if is_meaningful is not None:
                already_classified_ids.add(rid)
            items.append({"id": rid, "ai_text": ai_text or "", "stt_text": stt_text or ""})

        logger.info(
            f"classify: session={session_id} items={len(items)} "
            f"already_done={len(already_classified_ids)} backend={backend} model={model}"
        )

        verdicts = classify_discrepancies(
            items,
            model_id=model,
            already_classified_ids=already_classified_ids,
            use_vertex=use_vertex,
        )
        if verdicts is None:
            raise LLMError(
                "Gemini classification returned None — all batches failed",
                category="gemini_overloaded",
            )

        # Write verdicts to DB immediately — partial results are valuable.
        meaningful = 0
        noise = 0
        skipped = 0
        with engine.begin() as conn:
            for v in verdicts:
                # Defense-in-depth against malformed verdict ids slipping
                # past the engine's _classify_batch validator.
                try:
                    uuid.UUID(v["id"])
                except (ValueError, KeyError, TypeError):
                    logger.warning(f"classify: skipping malformed verdict id={v.get('id')!r}")
                    skipped += 1
                    continue
                conn.execute(
                    text(
                        """
                        UPDATE transcription_discrepancies
                           SET category         = :cat,
                               is_meaningful    = :meaningful,
                               classifier_model = :model,
                               classified_at    = now()
                         WHERE id = CAST(:id AS uuid)
                        """
                    ),
                    {
                        "id":         v["id"],
                        "cat":        v["category"],
                        "meaningful": bool(v["is_meaningful"]),
                        "model":      model,
                    },
                )
                if v["is_meaningful"]:
                    meaningful += 1
                else:
                    noise += 1
        if skipped:
            logger.warning(f"classify: skipped {skipped} verdict(s) with malformed UUIDs in {session_id}")

        total_classified = len(already_classified_ids) + len(verdicts) - skipped
        total_items = len(items)
        all_done = total_classified >= total_items

        logger.info(
            f"classify: session={session_id} new={len(verdicts)} "
            f"({meaningful} meaningful, {noise} noise) total={total_classified}/{total_items}"
            f"{' COMPLETE' if all_done else ' PARTIAL — retrying remaining'}"
        )

        if all_done:
            publish_ws_event_sync(session_id, {
                "type":       "classification_complete",
                "classified": total_classified,
                "meaningful": meaningful,
                "noise":      noise,
            })
            return {
                "session_id":  session_id,
                "classified":  total_classified,
                "meaningful":  meaningful,
                "noise":       noise,
                "backend":     backend,
                "model":       model,
            }

        # Partial: signal progress, then raise to trigger Celery retry on
        # the remaining un-classified rows.
        publish_ws_event_sync(session_id, {
            "type":       "classification_partial",
            "classified": total_classified,
            "total":      total_items,
        })
        raise LLMError(
            f"Partial classification: {total_classified}/{total_items} done — retrying remaining",
            category="gemini_overloaded",
        )

    except LLMError as exc:
        attempt = self.request.retries
        logger.warning(f"classify: attempt {attempt + 1} failed for {session_id}: {exc}")
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        raise
    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        logger.error(f"classify: unexpected error for {session_id}: {exc}", exc_info=True)
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        raise
    finally:
        engine.dispose()
