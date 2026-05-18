"""
frame_task — visual slide-boundary detection via FFmpeg + OpenCV.

Ports MIC `app/tasks/frame_task.py` (301 LOC) with the same algorithm:
  • FFmpeg extracts 1fps JPEGs from the GCS video
  • cv2.absdiff between consecutive grayscale frames → mean_diff series
  • 3-frame persistence filter — a candidate boundary at frame i needs
    mean_diff[i], [i+1], [i+2] all > VISUAL_CHANGE_THRESHOLD
  • Histogram stability check — Bhattacharyya distance > 0.05 confirms
    a real content change (filters out flicker / lighting shifts)

Redis state:
  rounds:frame:{session_id}         JSON list[VisualSignal] (TTL 24h)
  rounds:frame:done:{session_id}    "1" — check-before-execute guard

LOCKED settings (audit §6):
  FRAME_SAMPLE_FPS = 2  (sample rate)
  VISUAL_CHANGE_THRESHOLD = 8.0  (mean absolute pixel diff threshold)
  _HIST_BHATT_THRESHOLD = 0.05  (histogram dissimilarity threshold)

Does NOT trigger next task. anchor_task is triggered by transcribe_task,
which reads frame_task output from Redis at that point.
"""
from __future__ import annotations

import glob
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


_REDIS_SIGNALS_KEY = "rounds:frame:{session_id}"
_REDIS_DONE_KEY    = "rounds:frame:done:{session_id}"
_REDIS_TTL         = 86400
_HIST_BHATT_THRESHOLD = 0.05


@dataclass
class VisualSignal:
    """One detected visual change. Timestamp in seconds from session start."""
    timestamp: float
    strength: float       # 0-1, mean_diff / 255
    frame_idx: int


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.frame",
    max_retries=3,
)
def frame_task(self, session_id: str) -> dict:
    """
    Extract 1fps JPEGs from the session's video source, run the 3-step
    visual change detection, store VisualSignal[] in Redis.
    Skip if done flag already set.
    """
    import redis as _redis

    from sqlalchemy import create_engine, text

    from app.config import settings

    r = _redis.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        done_key = _REDIS_DONE_KEY.format(session_id=session_id)
        if r.exists(done_key):
            logger.info(f"frame_task: skip — done flag set for {session_id}")
            return {"skipped": True, "session_id": session_id}

        sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        engine = create_engine(sync_url)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT gcs_uri FROM sources
                         WHERE session_id = CAST(:sid AS uuid)
                           AND role IN ('video','audio','audio_enhance')
                         ORDER BY CASE role
                                    WHEN 'video' THEN 0
                                    WHEN 'audio' THEN 1
                                    ELSE 2
                                  END
                         LIMIT 1
                        """
                    ),
                    {"sid": session_id},
                ).fetchone()
                if not row:
                    raise RuntimeError(f"frame_task: no media source for {session_id}")
                gcs_uri = row[0]
        finally:
            engine.dispose()

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video_input")
            _download_from_gcs(gcs_uri, video_path)

            # Audio-only sessions have no frames — skip cleanly.
            if not _has_video_stream(video_path):
                logger.info(f"frame_task: {session_id} is audio-only — no visual signals")
                _store_signals(r, session_id, [])
                return {"session_id": session_id, "signals": 0, "frames": 0}

            duration = _probe_duration(video_path)
            max_s = settings.MAX_VIDEO_DURATION_MINUTES * 60
            if duration and duration > max_s:
                raise RuntimeError(
                    f"Video too long ({duration/60:.0f} min). "
                    f"Max: {settings.MAX_VIDEO_DURATION_MINUTES} min."
                )

            frame_pattern = os.path.join(tmpdir, "frame_%06d.jpg")
            _run_ffmpeg_fps(video_path, frame_pattern, settings.FRAME_SAMPLE_FPS)

            frame_paths = sorted(glob.glob(os.path.join(tmpdir, "frame_*.jpg")))
            if not frame_paths:
                logger.warning(f"frame_task: no frames extracted for {session_id}")
                _store_signals(r, session_id, [])
                return {"session_id": session_id, "signals": 0, "frames": 0}

            signals = _detect_visual_changes(
                frame_paths=frame_paths,
                fps=settings.FRAME_SAMPLE_FPS,
                threshold=settings.VISUAL_CHANGE_THRESHOLD,
            )

        signal_dicts = [asdict(s) for s in signals]
        _store_signals(r, session_id, signal_dicts)
        logger.info(
            f"frame_task: session={session_id} frames={len(frame_paths)} signals={len(signals)}"
        )
        return {
            "session_id":       session_id,
            "frames_processed": len(frame_paths),
            "signals_detected": len(signals),
        }

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        raise
    finally:
        try:
            r.close()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"redis close ignored: {e}")


# ─── helpers ────────────────────────────────────────────────────────────


def _download_from_gcs(gcs_uri: str, local_path: str) -> None:
    from google.cloud import storage as gcs_lib

    from app.config import settings

    assert gcs_uri.startswith("gs://"), gcs_uri
    without = gcs_uri[5:]
    bucket_name, _, blob_name = without.partition("/")
    client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
    client.bucket(bucket_name).blob(blob_name).download_to_filename(local_path)


def _probe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1",
         path],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def _has_video_stream(path: str) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet",
         "-select_streams", "v:0",
         "-show_entries", "stream=codec_type",
         "-of", "default=noprint_wrappers=1:nokey=1",
         path],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip() == "video"


def _run_ffmpeg_fps(video_path: str, pattern: str, fps: int) -> None:
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        pattern, "-y", "-loglevel", "error",
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=7200)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:500]}")


def _detect_visual_changes(
    frame_paths: list[str], fps: int, threshold: float,
) -> list[VisualSignal]:
    import cv2
    import numpy as np

    mean_diffs: list[float] = []
    gray_frames: list = []
    prev_gray = None
    for path in frame_paths:
        frame = cv2.imread(path)
        if frame is None:
            mean_diffs.append(0.0)
            gray_frames.append(prev_gray if prev_gray is not None else np.zeros((1, 1), dtype=np.uint8))
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_frames.append(gray)
        if prev_gray is not None:
            mean_diffs.append(float(cv2.absdiff(prev_gray, gray).mean()))
        else:
            mean_diffs.append(0.0)
        prev_gray = gray

    n = len(mean_diffs)
    accepted: set[int] = set()
    # 3-frame persistence filter
    for i in range(n - 2):
        if mean_diffs[i] > threshold and mean_diffs[i + 1] > threshold and mean_diffs[i + 2] > threshold:
            accepted.add(i)

    signals: list[VisualSignal] = []
    for i in sorted(accepted):
        if i == 0 or i >= len(gray_frames):
            continue
        prev_g = gray_frames[i - 1]
        curr_g = gray_frames[i]
        hist_prev = cv2.calcHist([prev_g], [0], None, [256], [0, 256])
        hist_curr = cv2.calcHist([curr_g], [0], None, [256], [0, 256])
        cv2.normalize(hist_prev, hist_prev, alpha=1.0, beta=0.0, norm_type=cv2.NORM_L1)
        cv2.normalize(hist_curr, hist_curr, alpha=1.0, beta=0.0, norm_type=cv2.NORM_L1)
        bhatt = cv2.compareHist(hist_prev, hist_curr, cv2.HISTCMP_BHATTACHARYYA)
        if bhatt > _HIST_BHATT_THRESHOLD:
            signals.append(
                VisualSignal(
                    timestamp=float(i) / fps,
                    strength=min(1.0, mean_diffs[i] / 255.0),
                    frame_idx=i,
                )
            )
    return signals


def _store_signals(r, session_id: str, signals: list) -> None:
    r.setex(_REDIS_SIGNALS_KEY.format(session_id=session_id), _REDIS_TTL, json.dumps(signals))
    r.setex(_REDIS_DONE_KEY.format(session_id=session_id), _REDIS_TTL, "1")


def load_visual_signals_from_redis(session_id: str) -> list[VisualSignal]:
    """Read VisualSignal[] from Redis. Returns [] if frame_task hasn't run."""
    import redis as _redis

    from app.config import settings

    r = _redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        raw = r.get(_REDIS_SIGNALS_KEY.format(session_id=session_id))
        if not raw:
            return []
        return [VisualSignal(**d) for d in json.loads(raw)]
    finally:
        try:
            r.close()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"redis close ignored: {e}")
