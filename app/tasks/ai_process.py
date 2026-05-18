"""
AI MODE — direct-to-LLM ingest path (MIC Pipeline 3).

When `session_templates.ai_pipeline = 'direct'`, the upload pipeline skips
Cloud STT and sends the media file(s) straight to Gemini multimodal. Gemini
returns a formatted transcript with slide markers (`++N*+`) and speaker
labels (`**Name:**`). We parse the response, write segments + slides +
alignments + speakers atomically, then transition `uploading → ready`.

Ports the `_process_direct` half of MIC `app/tasks/ai_process.py:79-300`
into the Rounds schema (start_ms / end_ms / seq / flags JSONB).

Pipeline 2 (enhanced — refines an STT transcript) lives in 6m.
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from typing import Optional

from app.tasks.celery_app import RoundsTask, celery_app

logger = logging.getLogger(__name__)


_FILLER_RX_PATTERN = (
    r'(?<![A-Za-z])(?:um|uh|er|ah|hm+|mm+)\s*[,.]?\s*'
)


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.ai_process",
    max_retries=3,
)
def ai_process_task(self, session_id: str) -> dict:  # noqa: ARG001 — bind=True needs self
    """
    Route to direct/enhanced by `session_templates.ai_pipeline`. Today only
    `direct` is implemented — `enhanced` lands in 6m.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT ai_pipeline, ai_mode, ai_model, prompt_mode, custom_prompt
                      FROM session_templates
                     WHERE session_id = CAST(:sid AS uuid)
                    """
                ),
                {"sid": session_id},
            ).fetchone()
        if not row:
            raise RuntimeError(f"ai_process: no session_templates row for {session_id}")

        ai_pipeline   = row[0]
        ai_mode       = row[1]
        ai_model      = row[2]
        prompt_mode   = row[3]
        custom_prompt = row[4]

        if ai_pipeline == "direct":
            return _process_direct(
                self, engine, session_id, ai_mode, ai_model, prompt_mode, custom_prompt,
            )
        # Enhanced: assume transcribe + normalize have already run; refine via Gemini.
        return _process_enhanced(
            self, engine, session_id, ai_mode, ai_model, prompt_mode, custom_prompt,
        )

    except Exception as exc:  # noqa: BLE001
        attempt = self.request.retries
        if attempt < self.max_retries:
            self.retry_with_backoff(exc, attempt)
        raise
    finally:
        engine.dispose()


# ─── Direct path ────────────────────────────────────────────────────────


def _process_direct(
    self,  # noqa: ARG001
    engine,
    session_id: str,
    ai_mode: str,
    ai_model: str,
    prompt_mode: str,
    custom_prompt: Optional[str],
) -> dict:
    """
    1. Pick the media source (video > audio).
    2. Download media + PDF/PPTX slides from GCS.
    3. Call Gemini multimodal with the right prompt for `ai_mode`.
    4. Parse response → segments + slide markers + speaker labels.
    5. Strip residual fillers (safety net).
    6. Write segments + slides + speakers + alignments atomically.
    7. Transition uploading → ready (skips intermediate stages).
    """
    import re

    from sqlalchemy import text

    from app.config import settings
    from app.engines.llm_client import LLMError, call_gemini_multimodal
    from app.engines.state_machine import transition_session_sync
    from app.engines.ws_bridge import publish_ws_event_sync
    from app.prompts import get_prompt_for_mode, parse_transcript_response

    def _emit(progress: int, substage: str) -> None:
        """Emit a processing_update WS event with progress + substage label."""
        publish_ws_event_sync(session_id, {
            "type":     "processing_update",
            "stage":    "ai_processing",
            "progress": progress,
            "substage": substage,
        })

    _emit(5, "Initializing AI pipeline…")

    # ── 1. Source selection ───────────────────────────────────────────────
    with engine.connect() as conn:
        sources = conn.execute(
            text(
                """
                SELECT gcs_uri, role, content_type
                  FROM sources
                 WHERE session_id = CAST(:sid AS uuid)
                 ORDER BY
                   CASE role
                     WHEN 'video' THEN 0
                     WHEN 'audio' THEN 1
                     WHEN 'audio_enhance' THEN 2
                     WHEN 'slide' THEN 3
                     ELSE 9
                   END
                """
            ),
            {"sid": session_id},
        ).fetchall()

    if not sources:
        raise LLMError(f"ai_process: no sources for session {session_id}", category="storage_error")

    media_source = next((s for s in sources if s[1] in ("video", "audio", "audio_enhance")), None)
    slide_sources = [s for s in sources if s[1] == "slide"]
    if media_source is None:
        raise LLMError(
            f"ai_process: no video/audio source for {session_id}",
            category="validation_error",
        )

    logger.info(
        f"ai_process[direct]: media={media_source[1]}, slides={len(slide_sources)}, "
        f"mode={ai_mode}, model={ai_model}"
    )

    # ── 2. Download for Gemini ────────────────────────────────────────────
    _emit(10, f"Downloading media + {len(slide_sources)} slide file(s)…")
    downloaded: list[tuple[str, str]] = []
    try:
        media_local = _download_from_gcs(media_source[0])
        media_mime = media_source[2] or _guess_mime(media_source[0])
        downloaded.append((media_local, media_mime))

        for s in slide_sources:
            slide_local = _download_from_gcs(s[0])
            slide_mime = s[2] or "application/pdf"
            downloaded.append((slide_local, slide_mime))

        _emit(20, f"Files downloaded ({len(downloaded)})")

        # ── 3. Gemini call ────────────────────────────────────────────────
        system_prompt = get_prompt_for_mode(prompt_mode or ai_mode, custom_prompt)
        _emit(30, f"Uploading to Gemini ({ai_model})…")
        _emit(40, "AI analyzing audio + slides…")
        raw = call_gemini_multimodal(downloaded, system_prompt, model_id=ai_model)

        # ── 4. Parse ──────────────────────────────────────────────────────
        parsed = parse_transcript_response(raw)
        if not parsed:
            raise LLMError("Gemini returned an empty transcript", category="gemini_error")

        _emit(70, f"Transcript received ({len(parsed)} segments)")
        publish_ws_event_sync(session_id, {
            "type":     "metrics_update",
            "segments": len(parsed),
        })

        # ── 5. Filler safety-net ─────────────────────────────────────────
        filler_rx = re.compile(_FILLER_RX_PATTERN, re.IGNORECASE)
        for seg in parsed:
            t = filler_rx.sub("", seg["text"])
            t = re.sub(r"\s+", " ", t).strip()
            if t and t[0].islower():
                t = t[0].upper() + t[1:]
            seg["text"] = t

        # Drop empties created by the cleanup
        parsed = [s for s in parsed if s["text"].strip()]
        if not parsed:
            raise LLMError("Transcript empty after filler cleanup", category="gemini_error")

        # ── 6. Duration + proportional timestamp assignment ──────────────
        duration_sec = _ffprobe_duration(media_local)
        if duration_sec <= 0:
            duration_sec = max(60.0, len(parsed) * 4.0)  # fallback
        max_s = settings.MAX_VIDEO_DURATION_MINUTES * 60
        if duration_sec > max_s:
            raise LLMError(
                f"Video too long ({duration_sec/60:.0f} min). "
                f"Max: {settings.MAX_VIDEO_DURATION_MINUTES} min.",
                category="validation_error",
            )

        total_chars = sum(len(s["text"]) for s in parsed) or 1
        cursor = 0.0
        for seg in parsed:
            proportion = len(seg["text"]) / total_chars
            seg_dur = proportion * duration_sec
            seg["start_time"] = round(cursor, 3)
            seg["end_time"] = round(cursor + seg_dur, 3)
            cursor = seg["end_time"]
        parsed[-1]["end_time"] = round(duration_sec, 3)

    finally:
        for path, _ in downloaded:
            try:
                os.unlink(path)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"cleanup ignored: {e}")

    _emit(85, f"Saving {len(parsed)} segments…")

    # ── 7. Persist segments + slides + speakers + alignments atomically ──
    with engine.begin() as conn:
        # Speakers — one row per unique speaker label.
        speaker_id_by_name: dict[str, str] = {}
        unique_names = list({(s.get("speaker_name") or "Presenter") for s in parsed})
        for name in unique_names:
            row = conn.execute(
                text(
                    """
                    INSERT INTO speakers (session_id, name, role, avatar_color)
                    VALUES (CAST(:sid AS uuid), :n, 'Instructor', '#2563eb')
                    RETURNING id
                    """
                ),
                {"sid": session_id, "n": name},
            ).fetchone()
            if row:
                speaker_id_by_name[name] = str(row[0])

        # Slides — write rows for each distinct slide_marker. If
        # slide_extract_task (6k or current PNG fallback) also writes
        # rows, ON CONFLICT (session_id, slide_index) keeps the richer
        # version. AI MODE direct contributes start/end + title only.
        slide_id_by_marker: dict[int, str] = {}
        markers = sorted({s["slide_marker"] for s in parsed if s.get("slide_marker") is not None})
        for marker in markers:
            slide_idx = marker - 1
            row = conn.execute(
                text(
                    """
                    INSERT INTO slides (session_id, slide_index, title)
                    VALUES (CAST(:sid AS uuid), :idx, :title)
                    ON CONFLICT (session_id, slide_index) DO UPDATE
                      SET title = COALESCE(slides.title, EXCLUDED.title)
                    RETURNING id
                    """
                ),
                {"sid": session_id, "idx": slide_idx, "title": f"Slide {marker}"},
            ).fetchone()
            if row:
                slide_id_by_marker[marker] = str(row[0])

        # Segments — one row per parsed paragraph. Deterministic ID
        # (SHA256 of session+start_ms) so re-runs are idempotent. The
        # `segments` table currently uses UUID id columns — until 6j
        # ports the schema to text IDs, we keep gen_random_uuid here
        # but enforce idempotency through the (session_id, seq) UNIQUE.
        for seq_idx, seg in enumerate(parsed, start=1):
            start_ms = int(round(seg["start_time"] * 1000))
            end_ms = int(round(seg["end_time"] * 1000))
            speaker_name = seg.get("speaker_name") or "Presenter"
            speaker_id = speaker_id_by_name.get(speaker_name)
            slide_id = slide_id_by_marker.get(seg.get("slide_marker") or -1)

            conn.execute(
                text(
                    """
                    INSERT INTO segments
                        (session_id, seq, start_ms, end_ms, text, confidence,
                         flags, slide_id, speaker_id)
                    VALUES
                        (CAST(:sid AS uuid), :seq, :st, :et, :tx, :conf,
                         '[]'::jsonb, :slide_id, :speaker_id)
                    ON CONFLICT (session_id, seq) DO UPDATE
                      SET text       = EXCLUDED.text,
                          start_ms   = EXCLUDED.start_ms,
                          end_ms     = EXCLUDED.end_ms,
                          slide_id   = EXCLUDED.slide_id,
                          speaker_id = EXCLUDED.speaker_id,
                          updated_at = now()
                    """
                ),
                {
                    "sid":        session_id,
                    "seq":        seq_idx,
                    "st":         start_ms,
                    "et":         end_ms,
                    "tx":         seg["text"],
                    "conf":       0.9,
                    "slide_id":   slide_id,
                    "speaker_id": speaker_id,
                },
            )

        # Session metadata
        word_count = sum(len(s["text"].split()) for s in parsed)
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
                "dur": int(round(duration_sec)),
                "wc":  word_count,
                "sc":  len(parsed),
            },
        )

    _emit(95, f"Saved {len(parsed)} segments / {len(slide_id_by_marker)} slides / {len(speaker_id_by_name)} speakers")
    publish_ws_event_sync(session_id, {
        "type":          "metrics_update",
        "segments":      len(parsed),
        "slides_total":  len(slide_id_by_marker),
        "speakers":      len(speaker_id_by_name),
        "duration_sec":  int(round(duration_sec)),
    })

    # ── 8. State transition uploading → ready (AI MODE direct shortcut) ──
    transition_session_sync(
        session_id, "ready",
        actor="ai_process_task",
        reason=f"direct/{ai_mode}/{ai_model}",
    )
    _emit(100, "Ready")

    # Release rate-limit slot (6o) + kick IIL learning (6q).
    try:
        from app.middleware.rate_limit import release_slot
        release_slot(None, session_id)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"ai_process: release_slot failed: {e}")
    try:
        from app.tasks.kp_task import kp_task
        kp_task.apply_async(args=[session_id], queue="celery")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"ai_process: failed to trigger kp_task: {e}")
    # Phase 7g — SOP auto-init at stage 'prep'.
    try:
        from app.tasks.sop_tasks import sop_auto_init_task
        sop_auto_init_task.apply_async(args=[session_id], queue="celery")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"ai_process: failed to trigger sop_auto_init: {e}")

    logger.info(
        f"ai_process[direct]: session={session_id} segments={len(parsed)} "
        f"slides={len(slide_id_by_marker)} speakers={len(speaker_id_by_name)} ready"
    )
    return {
        "session_id":    session_id,
        "segment_count": len(parsed),
        "slide_count":   len(slide_id_by_marker),
        "speaker_count": len(speaker_id_by_name),
        "status":        "ready",
    }


# ─── Enhanced path (Pipeline 2) ─────────────────────────────────────────


def _process_enhanced(
    self,  # noqa: ARG001
    engine,
    session_id: str,
    ai_mode: str,
    ai_model: str,
    prompt_mode: str,
    custom_prompt: Optional[str],
) -> dict:
    """
    Enhanced pipeline: transcribe + normalize have produced segments + text.
    AI MODE here refines each segment via Gemini (e.g. for non-transcript
    modes — summary / key-moments / structured-notes), then writes the
    refined text back. For ai_mode='transcript' this is a no-op since
    normalize already cleaned the text.

    Triggered by ingest_task when ai_pipeline=enhanced AND ai_mode != 'transcript'.
    """
    from sqlalchemy import text

    from app.engines.llm_client import LLMError, call_gemini_text
    from app.prompts import get_prompt_for_mode

    if ai_mode == "transcript":
        logger.info(f"ai_process[enhanced]: ai_mode=transcript — no refinement needed")
        return {"session_id": session_id, "refined": 0, "ai_mode": ai_mode}

    with engine.connect() as conn:
        segs = conn.execute(
            text(
                """
                SELECT id, seq, text FROM segments
                 WHERE session_id = CAST(:sid AS uuid)
                 ORDER BY seq ASC
                """
            ),
            {"sid": session_id},
        ).fetchall()

    if not segs:
        logger.info(f"ai_process[enhanced]: no segments for {session_id}")
        return {"session_id": session_id, "refined": 0}

    # Build the full transcript blob (for single-pass refinement) and call Gemini once.
    full_text = "\n\n".join(s[2] or "" for s in segs)
    system_prompt = get_prompt_for_mode(prompt_mode or ai_mode, custom_prompt)
    user_prompt = "Refine the following transcript:\n\n" + full_text

    try:
        # Use the JSON-output text path; we'll ask for plain text in the prompt.
        # Falling back to the raw response if JSON parse fails — non-fatal.
        raw = call_gemini_text(system_prompt, user_prompt, model_id=ai_model)
    except LLMError as e:
        logger.warning(f"ai_process[enhanced]: Gemini call failed ({e.category}): {e}")
        return {"session_id": session_id, "refined": 0, "error": e.category}

    # Try parsing as JSON {refined: [..]} first; else split blocks back to segments.
    refined_blocks: list[str] = []
    try:
        import json as _json
        data = _json.loads(raw)
        if isinstance(data, dict) and isinstance(data.get("refined"), list):
            refined_blocks = [str(b) for b in data["refined"]]
    except Exception:  # noqa: BLE001
        refined_blocks = [b.strip() for b in raw.split("\n\n") if b.strip()]

    if not refined_blocks:
        logger.warning(f"ai_process[enhanced]: empty refinement output for {session_id}")
        return {"session_id": session_id, "refined": 0}

    # Match refined blocks to segments by index. Truncate or pad as needed.
    n = min(len(segs), len(refined_blocks))
    with engine.begin() as conn:
        for i in range(n):
            conn.execute(
                text("UPDATE segments SET text = :t, updated_at = now() WHERE id = :sid"),
                {"t": refined_blocks[i], "sid": segs[i][0]},
            )
    logger.info(f"ai_process[enhanced]: session={session_id} refined={n}/{len(segs)} ai_mode={ai_mode}")
    return {"session_id": session_id, "refined": n, "ai_mode": ai_mode}


# ─── Template autodetect ────────────────────────────────────────────────


@celery_app.task(
    bind=True,
    base=RoundsTask,
    name="rounds.tasks.template_autodetect",
    max_retries=1,
)
def template_autodetect_task(self, session_id: str) -> dict:
    """
    Non-blocking, non-fatal classification of session content into a template.
    Runs on first 60s of audio. Failure → lecture_v1 + confidence 0.0 (TIL Rule 7).

    Updates session_templates.auto_detected_template_id + confidence. Never
    auto-applies — surfaced as a suggestion in the UI.

    Phase 6m / U128.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        # Phase 6m: confidence=0.0 fallback. Full classifier feature set is
        # OQ-008 (audit reference). Lecture_v1 is the safest default.
        detected_id = "lecture_v1"
        detected_conf = 0.0

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE session_templates
                       SET auto_detected_template_id = :tid,
                           auto_detected_confidence  = :conf
                     WHERE session_id = CAST(:sid AS uuid)
                    """
                ),
                {"tid": detected_id, "conf": detected_conf, "sid": session_id},
            )

        # Emit WS event (no-op until 6n)
        try:
            from app.engines.ws_bridge import publish_ws_event_sync  # type: ignore

            publish_ws_event_sync(
                session_id,
                {"type": "template_autodetect", "template_id": detected_id, "confidence": detected_conf},
            )
        except ImportError:
            pass

        return {"session_id": session_id, "template_id": detected_id, "confidence": detected_conf}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"template_autodetect: non-fatal failure — {exc}")
        return {"session_id": session_id, "template_id": "lecture_v1", "confidence": 0.0}
    finally:
        engine.dispose()


# ─── helpers ────────────────────────────────────────────────────────────


def _download_from_gcs(gcs_uri: str) -> str:
    """Download a GCS object to a tmp file. Caller is responsible for cleanup."""
    from google.cloud import storage as gcs_lib

    from app.config import settings

    assert gcs_uri.startswith("gs://"), gcs_uri
    without = gcs_uri[5:]
    bucket_name, _, blob_name = without.partition("/")
    fd, local_path = tempfile.mkstemp(suffix="_" + os.path.basename(blob_name))
    os.close(fd)
    client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
    client.bucket(bucket_name).blob(blob_name).download_to_filename(local_path)
    return local_path


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


def _guess_mime(gcs_uri: str) -> str:
    ext = gcs_uri.rsplit(".", 1)[-1].lower()
    return {
        "mp4":  "video/mp4", "mov": "video/quicktime", "mkv": "video/x-matroska",
        "webm": "video/webm", "avi": "video/x-msvideo",
        "mp3":  "audio/mpeg", "m4a": "audio/mp4", "wav": "audio/wav", "flac": "audio/flac",
        "pdf":  "application/pdf",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(ext, "application/octet-stream")
