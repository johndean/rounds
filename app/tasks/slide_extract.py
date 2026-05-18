"""
Slide-extract task — PDF/PPTX → slides rows + slide thumbnails in GCS.

Reads the first slide source for the session, rasterizes each page using
`ffmpeg` (works on PDF via poppler-piped images, but cross-platform we
prefer `pdftoppm` which ships with poppler-utils — included in the
Docker image via `poppler-utils`). Each thumbnail is uploaded to
`gs://<bucket>/sessions/<id>/slides/<n>.png` and a `slides` row is
created with `slide_index` (0-based, matches SLIDE_PALETTE) and
`image_uri`.

PPTX is not rasterized in-process (no LibreOffice in the worker image).
The task logs a warning and exits cleanly — alignment still works
against the audio transcript; the right-rail thumbnails simply use the
generic slide placeholder until the user re-uploads as PDF.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="rounds.tasks.slide_extract",
    max_retries=2,
    default_retry_delay=60,
)
def slide_extract_task(self, session_id: str) -> dict:  # noqa: ARG001
    from sqlalchemy import create_engine, text

    from app.config import settings

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM slides WHERE session_id = CAST(:sid AS uuid) LIMIT 1"),
                {"sid": session_id},
            ).fetchone()
            if existing:
                logger.info(f"slide_extract: skip — slides exist for {session_id}")
                return {"skipped": True, "session_id": session_id}

            src = conn.execute(
                text(
                    """
                    SELECT gcs_uri, filename, content_type FROM sources
                    WHERE session_id = CAST(:sid AS uuid) AND role = 'slide'
                    ORDER BY created_at ASC
                    LIMIT 1
                    """
                ),
                {"sid": session_id},
            ).fetchone()

        if not src:
            logger.info(f"slide_extract: no slide source for {session_id} (audio-only session)")
            return {"session_id": session_id, "slide_count": 0}

        gcs_uri, filename, content_type = src
        ext = (filename or "").rsplit(".", 1)[-1].lower()
        is_pdf = ext == "pdf" or (content_type or "").lower() == "application/pdf"

        if not is_pdf:
            logger.warning(
                f"slide_extract: source for {session_id} is {ext}/{content_type} — "
                f"only PDF rasterization is supported in this worker. Skipping."
            )
            return {"session_id": session_id, "slide_count": 0, "skipped_reason": f"unsupported:{ext}"}

        slide_count = _rasterize_pdf_and_persist(session_id, gcs_uri, engine)
        logger.info(f"slide_extract: session={session_id} wrote {slide_count} slides")
        return {"session_id": session_id, "slide_count": slide_count}

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            logger.warning(f"slide_extract failed (attempt {attempt + 1}): {exc} — retrying")
            raise self.retry(exc=exc, countdown=60 * (attempt + 1))
        logger.exception(f"slide_extract: terminal failure for {session_id}")
        # Non-fatal: alignment still works without thumbnails.
        return {"session_id": session_id, "slide_count": 0, "error": str(exc)}
    finally:
        engine.dispose()


def _rasterize_pdf_and_persist(session_id: str, gcs_uri: str, engine) -> int:
    from sqlalchemy import text

    from app.config import settings
    from app.tasks.transcribe import _download_from_gcs

    from google.cloud import storage as gcs_lib

    with tempfile.TemporaryDirectory() as tmpdir:
        local_pdf = os.path.join(tmpdir, "deck.pdf")
        _download_from_gcs(gcs_uri, local_pdf)

        out_prefix = os.path.join(tmpdir, "page")
        # pdftoppm produces page-1.png, page-2.png, ...
        cmd = [
            "pdftoppm",
            "-png",
            "-r", "120",  # 120dpi → ~1280×960 for typical 16:9 deck
            local_pdf,
            out_prefix,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode != 0:
            stderr = result.stderr.decode()[:500]
            raise RuntimeError(f"pdftoppm failed: {stderr}")

        png_files = sorted(
            f for f in os.listdir(tmpdir)
            if f.startswith("page-") and f.endswith(".png")
        )
        if not png_files:
            raise RuntimeError("pdftoppm produced no pages")

        gcs_client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
        bucket = gcs_client.bucket(settings.GCS_BUCKET)

        with engine.begin() as conn:
            for i, name in enumerate(png_files):
                local_path = os.path.join(tmpdir, name)
                blob_name = f"sessions/{session_id}/slides/thumb_{i:03d}.png"
                bucket.blob(blob_name).upload_from_filename(local_path, content_type="image/png")
                image_uri = f"gs://{settings.GCS_BUCKET}/{blob_name}"
                conn.execute(
                    text(
                        """
                        INSERT INTO slides (session_id, slide_index, title, image_uri)
                        VALUES (CAST(:sid AS uuid), :idx, :title, :uri)
                        ON CONFLICT (session_id, slide_index) DO UPDATE
                          SET image_uri = EXCLUDED.image_uri
                        """
                    ),
                    {
                        "sid": session_id,
                        "idx": i,
                        "title": f"Slide {i + 1}",
                        "uri": image_uri,
                    },
                )

        return len(png_files)
