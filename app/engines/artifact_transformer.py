"""
Artifact transformer — produces docx / srt / vtt / txt / zip from a
session's segments + slides + speakers + normalization.

Ports MIC `app/engines/artifact_transformer.py` (540 LOC). Each public
function returns raw bytes for the caller to stream out via FastAPI.

Phase 6p / U141-U142. Closes audit gap 🟠 #11.
"""
from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SegmentForExport:
    seq: int
    start_ms: int
    end_ms: int
    text: str
    slide_index: int | None
    slide_title: str | None
    speaker_name: str | None


@dataclass
class SlideForExport:
    slide_index: int
    title: str
    full_text: str
    bullets: list[str]


@dataclass
class SessionForExport:
    code: str
    title: str
    presenter: str | None
    duration_sec: int | None
    segments: list[SegmentForExport]
    slides: list[SlideForExport]


# ─── Helpers ────────────────────────────────────────────────────────────


def _fmt_srt_time(ms: int) -> str:
    hours = ms // 3_600_000
    ms %= 3_600_000
    mins = ms // 60_000
    ms %= 60_000
    secs = ms // 1000
    millis = ms % 1000
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def _fmt_vtt_time(ms: int) -> str:
    hours = ms // 3_600_000
    ms %= 3_600_000
    mins = ms // 60_000
    ms %= 60_000
    secs = ms // 1000
    millis = ms % 1000
    return f"{hours:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


# ─── Public exporters ───────────────────────────────────────────────────


def to_txt(session: SessionForExport) -> bytes:
    lines: list[str] = [
        f"# {session.title}".strip(),
        f"Code: {session.code}",
    ]
    if session.presenter:
        lines.append(f"Presenter: {session.presenter}")
    lines.append("")
    last_slide = None
    for seg in session.segments:
        if seg.slide_index != last_slide and seg.slide_title:
            lines.append("")
            lines.append(f"## Slide {seg.slide_index}: {seg.slide_title}")
            lines.append("")
            last_slide = seg.slide_index
        if seg.speaker_name:
            lines.append(f"{seg.speaker_name}: {seg.text}")
        else:
            lines.append(seg.text)
    return ("\n".join(lines) + "\n").encode("utf-8")


def to_srt(session: SessionForExport) -> bytes:
    chunks: list[str] = []
    for i, seg in enumerate(session.segments, start=1):
        chunks.append(str(i))
        chunks.append(f"{_fmt_srt_time(seg.start_ms)} --> {_fmt_srt_time(seg.end_ms)}")
        chunks.append((seg.text or "").strip())
        chunks.append("")
    return "\n".join(chunks).encode("utf-8")


def to_vtt(session: SessionForExport) -> bytes:
    chunks: list[str] = ["WEBVTT", ""]
    for seg in session.segments:
        chunks.append(f"{_fmt_vtt_time(seg.start_ms)} --> {_fmt_vtt_time(seg.end_ms)}")
        chunks.append((seg.text or "").strip())
        chunks.append("")
    return "\n".join(chunks).encode("utf-8")


def to_docx(session: SessionForExport) -> bytes:
    from docx import Document

    doc = Document()
    doc.add_heading(session.title or session.code, level=1)
    if session.presenter:
        doc.add_paragraph(f"Presenter: {session.presenter}")
    doc.add_paragraph(f"Code: {session.code}")
    doc.add_paragraph()

    last_slide = None
    for seg in session.segments:
        if seg.slide_index != last_slide and seg.slide_title:
            doc.add_heading(f"Slide {seg.slide_index}: {seg.slide_title}", level=2)
            last_slide = seg.slide_index
        para = doc.add_paragraph()
        if seg.speaker_name:
            run = para.add_run(f"{seg.speaker_name}: ")
            run.bold = True
        para.add_run(seg.text or "")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def to_zip(session: SessionForExport) -> bytes:
    """Bundle docx + srt + vtt + txt + slide bullets into a single zip."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{session.code}.txt", to_txt(session))
        zf.writestr(f"{session.code}.srt", to_srt(session))
        zf.writestr(f"{session.code}.vtt", to_vtt(session))
        zf.writestr(f"{session.code}.docx", to_docx(session))
        # Slides as a structured JSON-ish text bundle.
        slide_lines: list[str] = [f"# {session.title} — slide outline", ""]
        for s in session.slides:
            slide_lines.append(f"## Slide {s.slide_index + 1}: {s.title}")
            for bullet in s.bullets:
                slide_lines.append(f"- {bullet}")
            slide_lines.append("")
        zf.writestr(f"{session.code}_slides.txt", "\n".join(slide_lines).encode("utf-8"))
    return buf.getvalue()


# ─── Data loader ────────────────────────────────────────────────────────


def load_session_for_export(session_id: str) -> SessionForExport:
    """Fetch everything a session export needs in a single read."""
    from sqlalchemy import create_engine, text

    from app.config import settings

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            sess = conn.execute(
                text(
                    """
                    SELECT code, title, presenter, duration_sec
                      FROM sessions WHERE id = CAST(:sid AS uuid)
                    """
                ),
                {"sid": session_id},
            ).fetchone()
            if not sess:
                raise RuntimeError(f"export: session {session_id} not found")

            segments = conn.execute(
                text(
                    """
                    SELECT seg.seq, seg.start_ms, seg.end_ms, seg.text,
                           sl.slide_index, sl.title,
                           sp.name AS speaker_name
                      FROM segments seg
                      LEFT JOIN slides sl   ON sl.id = seg.slide_id
                      LEFT JOIN speakers sp ON sp.id = seg.speaker_id
                     WHERE seg.session_id = CAST(:sid AS uuid)
                     ORDER BY seg.seq ASC
                    """
                ),
                {"sid": session_id},
            ).fetchall()

            slides_rows = conn.execute(
                text(
                    """
                    SELECT sl.slide_index, sl.title, sl.full_text,
                           coalesce(array_agg(b.text ORDER BY b.position) FILTER (WHERE b.text IS NOT NULL), '{}')
                      FROM slides sl
                      LEFT JOIN bullets b ON b.slide_id = sl.id
                     WHERE sl.session_id = CAST(:sid AS uuid)
                     GROUP BY sl.slide_index, sl.title, sl.full_text
                     ORDER BY sl.slide_index ASC
                    """
                ),
                {"sid": session_id},
            ).fetchall()
    finally:
        engine.dispose()

    return SessionForExport(
        code=sess[0],
        title=sess[1] or sess[0],
        presenter=sess[2],
        duration_sec=sess[3],
        segments=[
            SegmentForExport(
                seq=r[0], start_ms=r[1] or 0, end_ms=r[2] or 0,
                text=r[3] or "", slide_index=r[4],
                slide_title=r[5], speaker_name=r[6],
            )
            for r in segments
        ],
        slides=[
            SlideForExport(
                slide_index=r[0], title=r[1] or f"Slide {r[0] + 1}",
                full_text=r[2] or "", bullets=list(r[3] or []),
            )
            for r in slides_rows
        ],
    )
