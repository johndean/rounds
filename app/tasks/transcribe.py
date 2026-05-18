"""
Transcribe task — Cloud STT (chunked) → segments rows.

Ports MIC `app/tasks/transcribe.py` (chunked backend). Reads the video/audio
source from GCS, splits it into N-minute WAV chunks via ffmpeg, transcribes
each chunk with Google Speech-to-Text long_running_recognize in parallel,
merges word-level timestamps, then groups consecutive words into segments
using a simple silence-and-length heuristic.

Output contract (per row in `segments`):
  - seq        : 1-based sequence
  - start_ms   : int milliseconds from session start
  - end_ms     : int milliseconds
  - text       : human-readable segment text
  - confidence : avg of word confidences
  - flags      : []  (downstream tasks add medication/filler/uncertain etc.)
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Optional

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


# Segmenter constants — keep simple; downstream slide-alignment + AI MODE
# can re-segment later. These match a "lecture pacing" default.
_SEGMENT_MAX_SECONDS = 12.0
_SEGMENT_SILENCE_GAP_SECONDS = 0.65


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.transcribe",
    max_retries=3,
)
def transcribe_task(self, session_id: str) -> dict:  # noqa: ARG001  (bind=True needs self)
    from sqlalchemy import create_engine, text

    from app.config import settings

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM segments WHERE session_id = CAST(:sid AS uuid) LIMIT 1"),
                {"sid": session_id},
            ).fetchone()
            if existing:
                logger.info(f"transcribe: skip — segments already exist for {session_id}")
                return {"skipped": True, "session_id": session_id}

            source = conn.execute(
                text(
                    """
                    SELECT gcs_uri FROM sources
                    WHERE session_id = CAST(:sid AS uuid)
                      AND role IN ('video', 'audio', 'audio_enhance')
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
            if not source:
                raise RuntimeError(f"transcribe: no video/audio source for {session_id}")

        gcs_uri = source[0]
        backend = settings.TRANSCRIPTION_BACKEND
        logger.info(f"transcribe: session={session_id} backend={backend} uri={gcs_uri}")

        if backend == "google_stt_chunked":
            words = _backend_google_stt_chunked(gcs_uri)
        elif backend == "google_stt":
            words = _backend_google_stt(gcs_uri)
        else:
            raise RuntimeError(f"unknown TRANSCRIPTION_BACKEND: {backend}")

        segments = _group_words_to_segments(words)
        if not segments:
            raise RuntimeError("transcribe: STT returned 0 words — refusing to mark session ready")

        duration_sec = int(round(max((s["end_ms"] for s in segments), default=0) / 1000.0))
        word_count = sum(len(s["text"].split()) for s in segments)

        with engine.begin() as conn:
            for seg in segments:
                conn.execute(
                    text(
                        """
                        INSERT INTO segments
                            (session_id, seq, start_ms, end_ms, text, confidence, flags)
                        VALUES
                            (CAST(:sid AS uuid), :seq, :st, :et, :tx, :conf, '[]'::jsonb)
                        ON CONFLICT (session_id, seq) DO NOTHING
                        """
                    ),
                    {
                        "sid": session_id,
                        "seq": seg["seq"],
                        "st": seg["start_ms"],
                        "et": seg["end_ms"],
                        "tx": seg["text"],
                        "conf": seg["confidence"],
                    },
                )
            conn.execute(
                text(
                    """
                    UPDATE sessions
                       SET duration_sec  = :dur,
                           word_count    = :wc,
                           segment_count = :sc,
                           updated_at    = now()
                     WHERE id = CAST(:sid AS uuid)
                    """
                ),
                {
                    "sid": session_id,
                    "dur": duration_sec,
                    "wc": word_count,
                    "sc": len(segments),
                },
            )

        logger.info(f"transcribe: session={session_id} wrote {len(segments)} segments / {word_count} words")

        # Trigger anchor_task — reads frame_task's Redis output (or empty if
        # frame hasn't finished) and writes confirmed AnchorHit[] for fusion.
        try:
            from app.tasks.anchor_task import anchor_task

            anchor_task.apply_async(args=[session_id], queue="celery")
        except Exception as anchor_err:  # noqa: BLE001
            logger.warning(f"transcribe: failed to trigger anchor_task: {anchor_err}")

        return {"session_id": session_id, "segment_count": len(segments), "word_count": word_count}

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            logger.warning(f"transcribe failed (attempt {attempt + 1}): {exc} — retrying")
            self.retry_with_backoff(exc, attempt)
        # Terminal — RoundsTask.on_failure runs after this re-raise.
        raise
    finally:
        engine.dispose()


# ─── STT backends ────────────────────────────────────────────────────────


def _backend_google_stt(gcs_uri: str) -> list[dict]:
    from google.cloud import speech

    client = speech.SpeechClient()
    audio = speech.RecognitionAudio(uri=gcs_uri)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
        enable_word_time_offsets=True,
        enable_automatic_punctuation=True,
    )
    operation = client.long_running_recognize(config=config, audio=audio)
    response = operation.result(timeout=3600)
    words = []
    for result in response.results:
        alt = result.alternatives[0]
        for w in alt.words:
            words.append(
                {
                    "word": w.word,
                    "start_time": w.start_time.total_seconds(),
                    "end_time": w.end_time.total_seconds(),
                    "confidence": float(alt.confidence) if alt.confidence else 0.85,
                }
            )
    return words


def _backend_google_stt_chunked(gcs_uri: str) -> list[dict]:
    import concurrent.futures

    from google.cloud import speech
    from google.cloud import storage as gcs_lib

    from app.config import settings

    chunk_seconds = settings.TRANSCRIPTION_CHUNK_MINUTES * 60

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video_input")
        _download_from_gcs(gcs_uri, video_path)

        duration = _ffprobe_duration(video_path)
        if duration <= 0:
            raise RuntimeError(f"ffprobe could not read duration for {gcs_uri}")

        chunk_count = max(1, int(duration // chunk_seconds) + (1 if duration % chunk_seconds > 0 else 0))
        chunk_paths: list[tuple[int, float, str]] = []
        for i in range(chunk_count):
            start = i * chunk_seconds
            chunk_path = os.path.join(tmpdir, f"chunk_{i:04d}.wav")
            cmd = [
                "ffmpeg", "-i", video_path,
                "-ss", str(start), "-t", str(chunk_seconds),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                chunk_path, "-y", "-loglevel", "error",
            ]
            subprocess.run(cmd, capture_output=True, timeout=900, check=True)
            chunk_paths.append((i, float(start), chunk_path))

        logger.info(f"chunked: duration={duration:.1f}s chunks={chunk_count}")

        gcs_client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
        bucket = gcs_client.bucket(settings.GCS_BUCKET)
        chunk_uris: list[tuple[int, float, str]] = []
        for i, offset, chunk_path in chunk_paths:
            blob_name = f"_tmp_chunks/{os.path.basename(chunk_path)}"
            bucket.blob(blob_name).upload_from_filename(chunk_path)
            chunk_uris.append((i, offset, f"gs://{settings.GCS_BUCKET}/{blob_name}"))

        stt_client = speech.SpeechClient()
        stt_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_word_time_offsets=True,
            enable_automatic_punctuation=True,
        )

        def _do_chunk(chunk: tuple[int, float, str]) -> tuple[int, list[dict]]:
            idx, offset, uri = chunk
            audio = speech.RecognitionAudio(uri=uri)
            operation = stt_client.long_running_recognize(config=stt_config, audio=audio)
            response = operation.result(timeout=3600)
            out: list[dict] = []
            for result in response.results:
                alt = result.alternatives[0]
                conf = float(alt.confidence) if alt.confidence else 0.85
                for w in alt.words:
                    out.append(
                        {
                            "word": w.word,
                            "start_time": w.start_time.total_seconds() + offset,
                            "end_time": w.end_time.total_seconds() + offset,
                            "confidence": conf,
                        }
                    )
            return idx, out

        results: dict[int, list[dict]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(12, chunk_count)) as pool:
            for f in concurrent.futures.as_completed({pool.submit(_do_chunk, c): c for c in chunk_uris}):
                idx, ws = f.result()
                results[idx] = ws

        for _, _, uri in chunk_uris:
            blob_name = uri.replace(f"gs://{settings.GCS_BUCKET}/", "")
            try:
                bucket.blob(blob_name).delete()
            except Exception as cleanup_err:
                logger.debug(f"chunk cleanup ignored: {cleanup_err}")

    all_words: list[dict] = []
    for i in range(chunk_count):
        all_words.extend(results.get(i, []))
    all_words.sort(key=lambda w: w["start_time"])
    return all_words


# ─── helpers ─────────────────────────────────────────────────────────────


def _download_from_gcs(gcs_uri: str, local_path: str) -> None:
    from google.cloud import storage as gcs_lib

    from app.config import settings

    assert gcs_uri.startswith("gs://"), gcs_uri
    without = gcs_uri[5:]
    bucket_name, _, blob_name = without.partition("/")
    client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
    client.bucket(bucket_name).blob(blob_name).download_to_filename(local_path)


def _ffprobe_duration(path: str) -> float:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    if result.returncode != 0:
        return 0.0
    try:
        return float(result.stdout.decode().strip())
    except ValueError:
        return 0.0


def _group_words_to_segments(words: list[dict]) -> list[dict]:
    """
    Lightweight segmenter. Splits on:
      - long silence (> _SEGMENT_SILENCE_GAP_SECONDS)
      - max length (> _SEGMENT_MAX_SECONDS)
      - terminal punctuation (period / question / exclamation)
    Each segment row carries averaged word confidence.
    """
    if not words:
        return []

    segments: list[dict] = []
    seq = 1
    bucket: list[dict] = []
    seg_start: Optional[float] = None
    prev_end: Optional[float] = None

    def _flush(last_word_end: float) -> None:
        nonlocal seq, bucket, seg_start
        if not bucket or seg_start is None:
            bucket = []
            seg_start = None
            return
        text = " ".join(w["word"] for w in bucket).strip()
        if not text:
            bucket = []
            seg_start = None
            return
        avg_conf = sum(w["confidence"] for w in bucket) / len(bucket)
        segments.append(
            {
                "seq": seq,
                "start_ms": int(round(seg_start * 1000)),
                "end_ms": int(round(last_word_end * 1000)),
                "text": text,
                "confidence": round(avg_conf, 4),
            }
        )
        seq += 1
        bucket = []
        seg_start = None

    for w in words:
        if seg_start is None:
            seg_start = w["start_time"]
        gap = (w["start_time"] - prev_end) if prev_end is not None else 0.0
        length = w["end_time"] - seg_start
        boundary = False
        if gap > _SEGMENT_SILENCE_GAP_SECONDS:
            boundary = True
        elif length > _SEGMENT_MAX_SECONDS:
            boundary = True
        if boundary and bucket:
            _flush(prev_end if prev_end is not None else w["start_time"])
            seg_start = w["start_time"]

        bucket.append(w)
        prev_end = w["end_time"]

        if w["word"].endswith((".", "?", "!")) and length > 2.0:
            _flush(w["end_time"])

    if bucket:
        _flush(prev_end if prev_end is not None else 0.0)

    return segments


def _mark_session_failed(session_id: str, reason: str) -> None:
    from app.engines.state_machine import ConflictError, transition_session_sync

    try:
        transition_session_sync(session_id, "failed", actor="transcribe_task", reason=reason)
    except ConflictError as e:
        # Already terminal — log and continue. Failure cleanup must not raise.
        logger.warning(f"transcribe: cannot mark {session_id} failed: {e}")
    logger.error(f"session {session_id} marked failed: {reason}")
