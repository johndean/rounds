"""
Rate limit guards — MAX_CONCURRENT_SESSIONS + MAX_QUEUE_LENGTH +
MAX_VIDEO_DURATION_MINUTES + multi-audio size validator.

Used as a dependency on POST /v1/gcs/upload-url + /upload-complete.
Phase 6o / U135-U138. Closes audit gap 🟡 #3 + reactivates memory
`feedback_multi_audio_stt_pollution`.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, status

from app.auth import CurrentUser
from app.config import settings

logger = logging.getLogger(__name__)


_ACTIVE_KEY_TPL = "sessions:active:{user}"
_QUEUE_KEY = "sessions:queue"
_MIN_AUDIO_ENHANCE_BYTES = 100_000   # 100 KB — flags pure-silence corrupt uploads


def _redis():
    import redis as _redis

    return _redis.from_url(settings.REDIS_URL, decode_responses=True)


def check_user_quota(user: CurrentUser) -> None:
    """
    Reject if user has MAX_CONCURRENT_SESSIONS already in flight, or if
    the global queue is past MAX_QUEUE_LENGTH.
    Called by the upload-url endpoint before issuing a signed URL.
    """
    try:
        r = _redis()
        try:
            active_count = r.scard(_ACTIVE_KEY_TPL.format(user=user.email))
            if active_count >= settings.MAX_CONCURRENT_SESSIONS:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code":    "RATE_LIMIT_USER",
                        "message": f"Already at {active_count} concurrent sessions (max {settings.MAX_CONCURRENT_SESSIONS})",
                    },
                )
            queue_len = r.llen(_QUEUE_KEY)
            if queue_len >= settings.MAX_QUEUE_LENGTH:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code":    "RATE_LIMIT_QUEUE",
                        "message": f"Ingest queue at capacity ({queue_len}/{settings.MAX_QUEUE_LENGTH})",
                    },
                )
        finally:
            r.close()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        # Redis unavailable: warn but don't block uploads.
        logger.warning(f"rate_limit: redis check skipped — {exc}")


def reserve_slot(user_email: str, session_id: str) -> None:
    try:
        r = _redis()
        try:
            r.sadd(_ACTIVE_KEY_TPL.format(user=user_email), session_id)
            r.rpush(_QUEUE_KEY, session_id)
        finally:
            r.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"rate_limit reserve_slot failed: {exc}")


def release_slot(user_email: Optional[str], session_id: str) -> None:
    """Release on success or failure. Called from finalize + RoundsTask._fail_session."""
    try:
        r = _redis()
        try:
            if user_email:
                r.srem(_ACTIVE_KEY_TPL.format(user=user_email), session_id)
            # Scan all active sets — handles the case where we don't know the owner.
            for key in r.keys("sessions:active:*"):
                r.srem(key, session_id)
            r.lrem(_QUEUE_KEY, 0, session_id)
        finally:
            r.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"rate_limit release_slot failed: {exc}")


def validate_files(files: list, session_id: str) -> None:
    """
    Validate upload-complete payload. Reject pure-silence enhance audio,
    durations over MAX_VIDEO_DURATION_MINUTES, etc.
    Per memory feedback_multi_audio_stt_pollution.
    """
    for f in files:
        role = (f.role if hasattr(f, "role") else f.get("role")) or "other"
        size = (f.size_bytes if hasattr(f, "size_bytes") else f.get("size_bytes")) or 0
        duration = (f.duration_sec if hasattr(f, "duration_sec") else f.get("duration_sec")) or 0

        if role == "audio_enhance" and size and size < _MIN_AUDIO_ENHANCE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code":    "VALIDATION_FAILED",
                    "message": f"audio_enhance file too small ({size} bytes < {_MIN_AUDIO_ENHANCE_BYTES}). "
                               "Likely silent/empty — would poison STT.",
                    "field":   "size_bytes",
                },
            )
        if role in ("video", "audio") and duration:
            max_s = settings.MAX_VIDEO_DURATION_MINUTES * 60
            if duration > max_s:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code":    "VALIDATION_FAILED",
                        "message": f"Media too long: {duration//60} min > max {settings.MAX_VIDEO_DURATION_MINUTES} min",
                        "field":   "duration_sec",
                    },
                )
