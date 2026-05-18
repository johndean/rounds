"""
burn_captions_task — produces a captions-burned-in MP4 in GCS.

Triggered on-demand from /v1/sessions/{id}/exports/captioned_video (or
automatically after session.status=ready for sessions tagged for
captioning). Reads session segments → generates SRT → invokes ffmpeg
with subtitles filter → uploads to GCS → writes artifacts row.

Ports MIC `app/tasks/burn_captions.py` (420 LOC) — condensed for Rounds.
Phase 6p / U143.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.burn_captions",
    max_retries=2,
)
def burn_captions_task(self, session_id: str) -> dict:
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.engines.artifact_transformer import load_session_for_export, to_srt
    from app.tasks.transcribe import _download_from_gcs

    from google.cloud import storage as gcs_lib

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        # Find video source
        with engine.connect() as conn:
            src = conn.execute(
                text(
                    """
                    SELECT gcs_uri FROM sources
                     WHERE session_id = CAST(:sid AS uuid) AND role = 'video'
                     LIMIT 1
                    """
                ),
                {"sid": session_id},
            ).fetchone()
        if not src:
            logger.info(f"burn_captions: no video source for {session_id}")
            return {"session_id": session_id, "skipped": True, "reason": "no_video"}

        sess = load_session_for_export(session_id)
        if not sess.segments:
            return {"session_id": session_id, "skipped": True, "reason": "no_segments"}

        srt_bytes = to_srt(sess)
        with tempfile.TemporaryDirectory() as tmpdir:
            video_local = os.path.join(tmpdir, "input.mp4")
            srt_local = os.path.join(tmpdir, "captions.srt")
            output_local = os.path.join(tmpdir, "output.mp4")
            _download_from_gcs(src[0], video_local)
            with open(srt_local, "wb") as f:
                f.write(srt_bytes)

            # ffmpeg subtitles filter — burn captions in.
            cmd = [
                "ffmpeg", "-i", video_local,
                "-vf", f"subtitles={srt_local}:force_style='FontSize=18,OutlineColour=&H80000000,BorderStyle=3'",
                "-c:a", "copy",
                output_local, "-y", "-loglevel", "error",
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=14400)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:500]}")

            # Upload to GCS
            client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
            bucket = client.bucket(settings.GCS_BUCKET)
            blob_name = f"sessions/{session_id}/captioned/{sess.code}_captioned.mp4"
            bucket.blob(blob_name).upload_from_filename(output_local, content_type="video/mp4")
            gcs_uri = f"gs://{settings.GCS_BUCKET}/{blob_name}"
            file_size = os.path.getsize(output_local)

            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO artifacts (session_id, kind, gcs_uri, bytes, generated_by)
                        VALUES (CAST(:sid AS uuid), 'captioned_video', :uri, :b, 'burn_captions_task')
                        ON CONFLICT (session_id, kind) DO UPDATE
                          SET gcs_uri = EXCLUDED.gcs_uri,
                              bytes   = EXCLUDED.bytes,
                              generated_at = now()
                        """
                    ),
                    {"sid": session_id, "uri": gcs_uri, "b": file_size},
                )

        logger.info(f"burn_captions: session={session_id} → {gcs_uri} ({file_size} bytes)")
        return {"session_id": session_id, "gcs_uri": gcs_uri, "bytes": file_size}

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        raise
    finally:
        engine.dispose()
