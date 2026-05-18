"""
burn_captions_task — produces a captions-burned-in MP4 in GCS.

Triggered on-demand from /v1/sessions/{id}/captions/burn with optional
style_config JSON (see style_config_to_ass for the 14 accepted keys).
Frontend listens for `captioned_video_ready` WS event with signed URL.

Failure is NON-CRITICAL: caption-burn errors do NOT mark the session
as failed. The session pipeline is normal — only the export artifact
didn't produce. Errors emit `captioned_video_failed` WS event.

Ports MIC `app/tasks/burn_captions.py` verbatim including:
  • _BurnCaptionsTask base class with on_failure override (#62)
  • style_config_to_ass — 14-key translator (#58)
  • caption_source selector 'ai'|'stt' (#59)
  • Signed download URL generation (#60)
  • Progress events at 5/15/30/40/85/95/100 (#61)
  • Versioned artifact with is_current pattern (#63)
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import uuid as uuid_lib
from datetime import timedelta

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Style translator — UI JSON → ffmpeg ASS force_style string
# ─────────────────────────────────────────────────────────────────────────────

# ASS Alignment codes (numpad layout):
#  Bottom:  1(BL)   2(BC)   3(BR)
#  Middle:  9(ML)  10(MC)  11(MR)
#  Top:     5(TL)   6(TC)   7(TR)
_ALIGNMENT_CODES = {
    ("bottom", "left"):   1,
    ("bottom", "center"): 2,
    ("bottom", "right"):  3,
    ("middle", "left"):   9,
    ("middle", "center"): 10,
    ("middle", "right"):  11,
    ("top",    "left"):   5,
    ("top",    "center"): 6,
    ("top",    "right"):  7,
}


def _hex_to_ass_bgr(hex_color: str, alpha_opaque: bool = True) -> str:
    """Convert #RRGGBB → ASS &HAABBGGRR& literal (BGR byte order, AA: 00=opaque)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    rr, gg, bb = h[0:2], h[2:4], h[4:6]
    aa = "00" if alpha_opaque else "FF"
    return f"&H{aa}{bb}{gg}{rr}&".upper()


def style_config_to_ass(style: dict | None) -> str:
    """
    Translate CaptionStyleDialog payload to ffmpeg force_style=... string.
    Safe defaults on missing/invalid keys.

    Accepted keys: font_family, font_size, text_color, outline_color,
    outline_thickness, shadow, background, bold, italic, vertical_position
    ('top'|'middle'|'bottom'), horizontal_align ('left'|'center'|'right'),
    margin.
    """
    s = style or {}
    font_family       = str(s.get("font_family", "Arial"))[:50]
    font_size         = max(8,  min(96, int(s.get("font_size", 24))))
    text_color        = str(s.get("text_color", "#FFFFFF"))
    outline_color     = str(s.get("outline_color", "#000000"))
    outline_thickness = max(0,  min(4,  int(s.get("outline_thickness", 1))))
    shadow            = bool(s.get("shadow", True))
    background        = bool(s.get("background", False))
    bold              = bool(s.get("bold", False))
    italic            = bool(s.get("italic", False))
    vpos              = s.get("vertical_position", "bottom")
    halign            = s.get("horizontal_align", "center")
    margin            = max(0, min(200, int(s.get("margin", 40))))

    alignment = _ALIGNMENT_CODES.get((vpos, halign), 2)  # default bottom-center
    border_style = 3 if background else 1               # 1=outline+shadow, 3=opaque box

    primary_colour = _hex_to_ass_bgr(text_color)
    outline_colour = _hex_to_ass_bgr(outline_color)
    back_colour    = _hex_to_ass_bgr(text_color, alpha_opaque=False)

    parts = [
        f"Fontname={font_family}",
        f"Fontsize={font_size}",
        f"PrimaryColour={primary_colour}",
        f"OutlineColour={outline_colour}",
        f"BackColour={back_colour}",
        f"Bold={-1 if bold else 0}",
        f"Italic={-1 if italic else 0}",
        f"Outline={outline_thickness}",
        f"Shadow={1 if shadow else 0}",
        f"Alignment={alignment}",
        f"MarginV={margin}",
        f"MarginL={margin}",
        f"MarginR={margin}",
        f"BorderStyle={border_style}",
    ]
    return ",".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# GCS helpers
# ─────────────────────────────────────────────────────────────────────────────


def _download_video_from_gcs(gcs_uri: str) -> str:
    from google.cloud import storage as gcs_lib
    from app.config import settings

    assert gcs_uri.startswith("gs://")
    bucket_name, _, blob_name = gcs_uri[5:].partition("/")
    ext = os.path.splitext(blob_name)[1] or ".mp4"
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    local_path = tmp.name
    tmp.close()
    client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
    bucket = client.bucket(bucket_name)
    bucket.blob(blob_name).download_to_filename(local_path)
    logger.info(f"burn_captions: downloaded {gcs_uri} ({os.path.getsize(local_path)} bytes)")
    return local_path


def _upload_to_gcs(local_path: str, gcs_uri: str) -> None:
    from google.cloud import storage as gcs_lib
    from app.config import settings

    bucket_name, _, blob_name = gcs_uri[5:].partition("/")
    client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
    client.bucket(bucket_name).blob(blob_name).upload_from_filename(local_path, content_type="video/mp4")


def _generate_signed_url(gcs_uri: str, hours: int = 24) -> str:
    from google.cloud import storage as gcs_lib
    from app.config import settings

    bucket_name, _, blob_name = gcs_uri[5:].partition("/")
    client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
    return client.bucket(bucket_name).blob(blob_name).generate_signed_url(
        version="v4",
        expiration=timedelta(hours=hours),
        method="GET",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Custom task base — override on_failure so caption errors don't kill session
# ─────────────────────────────────────────────────────────────────────────────


from celery import Task


class _BurnCaptionsTask(Task):
    """
    Override on_failure — burn-in is non-critical. NEVER mark the session
    as 'failed' on burn failure. The session is normal; only the export
    artifact didn't produce. Emit a WS event the UI can surface.
    """

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # noqa: ARG002, ANN001
        session_id = kwargs.get("session_id") or (args[0] if args else None)
        logger.warning(
            f"burn_captions_task FAILED for session {session_id}: {exc} "
            f"— session status NOT changed (export is non-critical)"
        )
        if session_id:
            try:
                from app.engines.ws_bridge import publish_ws_event_sync
                publish_ws_event_sync(session_id, {
                    "type": "captioned_video_failed",
                    "reason": str(exc)[:500],
                })
            except Exception as e:  # noqa: BLE001
                logger.warning(f"burn_captions: WS emit failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Celery task
# ─────────────────────────────────────────────────────────────────────────────


@celery_app.task(
    bind=True,
    base=_BurnCaptionsTask,
    name="rounds.tasks.burn_captions",
    max_retries=2,
    time_limit=3600,       # 1h hard kill — big videos
    soft_time_limit=3300,  # 55m soft warning
)
def burn_captions_task(self, session_id: str, style_config: dict | None = None) -> dict:
    """
    Burn SRT captions into the session's source video using ffmpeg.
    Steps:
      1. Resolve video source
      2. Generate SRT (caption_source='ai' uses cleaned segments; 'stt' uses words)
      3. Download video, write SRT, run ffmpeg
      4. Upload to gs://<bucket>/sessions/<id>/captioned/<uuid>.mp4
      5. Mark prior captioned artifacts as not current; insert new versioned row
      6. Publish captioned_video_ready WS with signed URL
    """
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.engines.ws_bridge import publish_ws_event_sync

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    def _emit(progress: int, substage: str) -> None:
        publish_ws_event_sync(session_id, {
            "type": "captioned_video_progress",
            "progress": progress,
            "substage": substage,
        })

    _emit(5, "Resolving video source…")

    style_config = style_config or {}
    caption_source = (style_config or {}).get("caption_source", "ai")

    try:
        with engine.connect() as conn:
            src = conn.execute(
                text(
                    """
                    SELECT gcs_uri FROM sources
                     WHERE session_id = CAST(:sid AS uuid) AND role = 'video'
                     ORDER BY created_at ASC LIMIT 1
                    """
                ),
                {"sid": session_id},
            ).fetchone()
            if not src or not src[0]:
                raise RuntimeError(f"No video source found for session {session_id}")
            video_gcs_uri = src[0]

            # ── Build SRT (caption_source: 'ai'=cleaned segment text, 'stt'=word-level) ──
            if caption_source == "stt":
                rows = conn.execute(
                    text(
                        """
                        SELECT w.word, w.start_ms, w.end_ms
                          FROM words w
                          JOIN segments s ON s.id = w.segment_id
                         WHERE s.session_id = CAST(:sid AS uuid)
                         ORDER BY w.start_ms ASC
                        """
                    ),
                    {"sid": session_id},
                ).fetchall()
                srt_text = _build_srt_from_words([{"word": r[0], "start": r[1] / 1000.0, "end": r[2] / 1000.0} for r in rows])
                if not srt_text.strip():
                    rows = conn.execute(
                        text("SELECT text, start_ms, end_ms FROM segments WHERE session_id = CAST(:sid AS uuid) ORDER BY start_ms"),
                        {"sid": session_id},
                    ).fetchall()
                    srt_text = _build_srt_from_segments([(r[0], r[1] / 1000.0, r[2] / 1000.0) for r in rows])
            else:
                rows = conn.execute(
                    text("SELECT text, start_ms, end_ms FROM segments WHERE session_id = CAST(:sid AS uuid) ORDER BY start_ms"),
                    {"sid": session_id},
                ).fetchall()
                srt_text = _build_srt_from_segments([(r[0], r[1] / 1000.0, r[2] / 1000.0) for r in rows])

        if not srt_text.strip():
            raise RuntimeError(f"Session {session_id} has no transcript content to caption")

        _emit(15, "Downloading source video…")
        local_video = _download_video_from_gcs(video_gcs_uri)

        _emit(30, "Writing caption file…")
        srt_path = local_video + ".srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_text)

        output_path = local_video + ".captioned.mp4"
        force_style = style_config_to_ass(style_config)
        safe_style = force_style.replace("'", r"\'")
        safe_srt = srt_path.replace(":", r"\:").replace("'", r"\'")
        vf = f"subtitles={safe_srt}:force_style='{safe_style}'"

        _emit(40, "Rendering captions into video (this takes a while)…")
        cmd = [
            "ffmpeg", "-y",
            "-i", local_video,
            "-vf", vf,
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_path,
        ]
        logger.info(f"burn_captions: running ffmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3300)
        if result.returncode != 0:
            tail = (result.stderr or "")[-800:]
            raise RuntimeError(f"ffmpeg failed (exit {result.returncode}): {tail}")

        out_bytes = os.path.getsize(output_path)
        _emit(85, f"Uploading captioned video ({out_bytes // 1_000_000} MB)…")

        out_blob = f"sessions/{session_id}/captioned/{uuid_lib.uuid4()}.mp4"
        out_gcs_uri = f"gs://{settings.GCS_BUCKET}/{out_blob}"
        _upload_to_gcs(output_path, out_gcs_uri)

        _emit(95, "Recording artifact…")

        new_artifact_id = str(uuid_lib.uuid4())
        with engine.begin() as conn:
            # Mark prior captioned artifacts not current
            conn.execute(
                text(
                    """
                    UPDATE artifacts
                       SET is_current = FALSE
                     WHERE session_id = CAST(:sid AS uuid) AND kind = 'captioned_video'
                    """
                ),
                {"sid": session_id},
            )
            # Insert new versioned row
            conn.execute(
                text(
                    """
                    INSERT INTO artifacts (
                        id, session_id, kind, version, is_current,
                        gcs_uri, bytes, style_config, generated_by, generated_at
                    ) VALUES (
                        CAST(:id AS uuid), CAST(:sid AS uuid), 'captioned_video',
                        coalesce((SELECT max(version)+1 FROM artifacts
                                   WHERE session_id = CAST(:sid AS uuid)
                                     AND kind = 'captioned_video'), 1),
                        TRUE, :uri, :b, CAST(:style AS jsonb),
                        'burn_captions_task', now()
                    )
                    """
                ),
                {
                    "id":    new_artifact_id,
                    "sid":   session_id,
                    "uri":   out_gcs_uri,
                    "b":     out_bytes,
                    "style": json.dumps(style_config or {}),
                },
            )

        signed_url = _generate_signed_url(out_gcs_uri, hours=24)

        _emit(100, "Done")
        publish_ws_event_sync(session_id, {
            "type": "captioned_video_ready",
            "artifact_id": new_artifact_id,
            "download_url": signed_url,
            "byte_size": out_bytes,
        })

        # Cleanup tmp files
        for p in (local_video, srt_path, output_path):
            try:
                os.unlink(p)
            except OSError:
                pass

        return {
            "artifact_id": new_artifact_id,
            "gcs_uri":     out_gcs_uri,
            "signed_url":  signed_url,
            "bytes":       out_bytes,
        }
    finally:
        engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# SRT builders (inline — avoid circular import with artifact_transformer)
# ─────────────────────────────────────────────────────────────────────────────


def _srt_timestamp(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _build_srt_from_segments(segs: list[tuple[str, float, float]]) -> str:
    out: list[str] = []
    for i, (text_str, start, end) in enumerate(segs, start=1):
        if not text_str or end <= start:
            continue
        out.append(str(i))
        out.append(f"{_srt_timestamp(start)} --> {_srt_timestamp(end)}")
        out.append((text_str or "").strip())
        out.append("")
    return "\n".join(out)


def _build_srt_from_words(words: list[dict]) -> str:
    """Group words into ~3-second cues."""
    cues: list[tuple[str, float, float]] = []
    cur_words: list[str] = []
    cur_start: float | None = None
    cur_end: float = 0.0
    for w in words:
        if cur_start is None:
            cur_start = w["start"]
        cur_words.append(w["word"])
        cur_end = w["end"]
        if cur_end - cur_start >= 3.0:
            cues.append((" ".join(cur_words), cur_start, cur_end))
            cur_words = []
            cur_start = None
    if cur_words and cur_start is not None:
        cues.append((" ".join(cur_words), cur_start, cur_end))
    return _build_srt_from_segments(cues)
