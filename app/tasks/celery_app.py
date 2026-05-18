"""
Celery app + RoundsTask base class.

Ports MIC's `MICTask(Task)` with:
  • on_failure: categorize → transition session to failed → release rate-limit counter → WS emit
  • retry_with_backoff: exponential 60/120/240s + jitter (settings.CELERY_RETRY_JITTER)
  • _categorize_exception: maps raw exception text to stable category strings
    (gemini_overloaded | gemini_quota | gemini_config | storage_error | stt_error | unknown)
    + user-facing messages for the failure card.

Every Rounds task subclasses RoundsTask via `base=RoundsTask`.
"""
from __future__ import annotations

import logging
import random
from typing import Optional

from celery import Celery, Task

from app.config import settings

logger = logging.getLogger(__name__)


celery_app = Celery(
    "rounds",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.ingest",
        "app.tasks.transcribe",
        "app.tasks.slide_extract",
        "app.tasks.align",
        "app.tasks.finalize",
        "app.tasks.ai_process",
        "app.tasks.frame_task",
        "app.tasks.anchor_task",
        "app.tasks.normalize",
        "app.tasks.fusion",
        "app.tasks.lcs_discrepancies",
        "app.tasks.classify_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=settings.CELERY_RETRY_BACKOFF_BASE,
    task_max_retries=settings.CELERY_MAX_RETRIES,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_default_queue="celery",
)


_CATEGORY_MESSAGES: dict[str, str] = {
    "gemini_overloaded": "Gemini is overloaded right now. This usually clears in a few minutes — try again.",
    "gemini_quota":      "Gemini API quota exceeded. Check billing on Google Cloud Console.",
    "gemini_config":     "Gemini API key is missing or invalid. Contact your administrator.",
    "gemini_error":      "The AI service returned an error. Try again or contact support.",
    "storage_error":     "Couldn't read your uploaded file from storage. Please re-upload.",
    "stt_error":         "Speech-to-text failed. Please try again or contact support.",
    "validation_error":  "Your upload failed validation. Check the file size and try again.",
    "unknown":           "Something went wrong. Try again, or contact support if it persists.",
}


class RoundsTask(Task):
    """
    Base task class — all Rounds Celery tasks inherit this.
    Enforces: categorized failure handling, retry discipline with jitter.
    """

    abstract = True
    max_retries = settings.CELERY_MAX_RETRIES  # 3
    _backoff_base = settings.CELERY_RETRY_BACKOFF_BASE  # 60s

    # ─── Failure handling ───────────────────────────────────────────────
    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:  # noqa: ARG002, ANN001
        """Final failure (retries exhausted or non-retryable). Mark session failed + emit WS."""
        session_id = kwargs.get("session_id") or (args[0] if args else None)
        category, user_message = self._categorize_exception(exc)
        if session_id:
            try:
                self._fail_session(session_id, str(exc), category=category, user_message=user_message)
            except Exception as inner:  # noqa: BLE001
                logger.error(f"_fail_session failed for {session_id}: {inner}")
        logger.error(f"Task {self.name} terminal failure for session={session_id}: {exc}", exc_info=True)

    @staticmethod
    def _categorize_exception(exc: Exception) -> tuple[str, str]:
        """Map a task exception to (category, user_message). Stable strings the frontend can branch on."""
        try:
            from app.engines.llm_client import LLMError

            if isinstance(exc, LLMError):
                cat = getattr(exc, "category", "gemini_error")
                return cat, _CATEGORY_MESSAGES.get(cat, _CATEGORY_MESSAGES["gemini_error"])
        except ImportError:
            pass

        text = str(exc).lower()
        if "gs://" in text or "storage" in text or "bucket" in text or "blob" in text:
            return "storage_error", _CATEGORY_MESSAGES["storage_error"]
        if "stt" in text or "speech" in text or "transcrib" in text or "ffmpeg" in text:
            return "stt_error", _CATEGORY_MESSAGES["stt_error"]
        if "validation" in text or "validate" in text:
            return "validation_error", _CATEGORY_MESSAGES["validation_error"]
        return "unknown", _CATEGORY_MESSAGES["unknown"]

    def _fail_session(
        self, session_id: str, reason: str,
        category: str = "unknown",
        user_message: str = "Something went wrong.",
    ) -> None:
        """Transition to failed via state machine. Release rate-limit counter. Emit WS."""
        from app.engines.state_machine import ConflictError, transition_session_sync

        try:
            transition_session_sync(
                session_id,
                "failed",
                actor=f"task:{self.name}",
                reason=f"[{category}] {reason}",
            )
        except ConflictError as e:
            logger.warning(f"_fail_session: cannot transition {session_id} to failed: {e}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"_fail_session: unexpected error for {session_id}: {e}")

        # Release rate-limit slot (6o).
        try:
            from app.middleware.rate_limit import release_slot

            release_slot(None, session_id)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"_fail_session: release_slot failed for {session_id}: {e}")

        # Emit WS event (no-op until 6n).
        try:
            from app.engines.ws_bridge import publish_ws_event_sync  # type: ignore

            publish_ws_event_sync(
                session_id,
                {
                    "type":         "session_failed",
                    "reason":       reason,
                    "category":     category,
                    "user_message": user_message,
                },
            )
        except ImportError:
            pass
        except Exception as e:  # noqa: BLE001
            logger.warning(f"_fail_session: WS emit failed for {session_id}: {e}")

    # ─── Retry helper ───────────────────────────────────────────────────
    def retry_with_backoff(self, exc, attempt: int) -> None:
        """
        Exponential backoff with optional jitter — 60/120/240s.

        Raises Celery's `Retry` exception (via `self.retry`) which Celery
        intercepts to reschedule the task. Caller pattern:

            try:
                ...
            except Exception as exc:
                attempt = self.request.retries
                if attempt < self.max_retries:
                    self.retry_with_backoff(exc, attempt)
                raise
        """
        delay = self._backoff_base * (2 ** attempt)
        if settings.CELERY_RETRY_JITTER:
            delay += random.uniform(0, delay * 0.1)
        raise self.retry(exc=exc, countdown=int(delay))
