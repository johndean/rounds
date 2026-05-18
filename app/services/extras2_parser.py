"""
extras2.txt session-manifest parser.

Verbatim port of MIC `app/services/extras2_parser.py` (403 LOC). Pure
regex — zero LLM dependency. Returns a ParsedManifest; never raises.

Closes audit gap 🔴 #4. Phase 6f / U94.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Output dataclasses ───────────────────────────────────────────────────


@dataclass
class SpeakerRecord:
    role: str             # moderator | primary | guest
    name: str
    credentials: Optional[str] = None
    bio: Optional[str] = None
    sort_order: int = 0


@dataclass
class SlideResourceRecord:
    slide_number: int
    label: Optional[str]
    url: str
    sort_order: int = 0


@dataclass
class ParsedManifest:
    code: Optional[str] = None
    title_long: Optional[str] = None
    title_short: Optional[str] = None
    ce_broker_id: Optional[str] = None
    class_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    publishing_links: dict = field(default_factory=dict)
    polls: Optional[str] = None
    polls_parsed: list[dict] = field(default_factory=list)
    speakers: list[SpeakerRecord] = field(default_factory=list)
    slide_resources: list[SlideResourceRecord] = field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────────────────


_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _first_match(pattern: str, text: str, flags: int = 0, group: int = 1) -> Optional[str]:
    m = re.search(pattern, text, flags)
    if not m:
        return None
    try:
        return m.group(group).strip()
    except IndexError:
        return None


def _extract_speaker_name_from_bio(bio: str) -> tuple[Optional[str], Optional[str]]:
    if not bio:
        return None, None
    m = re.match(r"(?:Dr\.\s+)?([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){1,3})", bio.strip())
    if not m:
        return None, None
    return m.group(1).strip(), None


def _extract_credentials_near_bio(bio: str, full_text: str, speaker_name: Optional[str]) -> Optional[str]:
    if not speaker_name:
        return None
    pattern = rf"{re.escape(speaker_name)},\s+([A-Z][A-Za-z]*\.?(?:,\s+[A-Z][A-Za-z]*\.?)*)"
    m = re.search(pattern, full_text, re.MULTILINE)
    if not m:
        return None
    creds = m.group(1).strip().rstrip(",")
    if len(creds) > 120:
        return None
    return creds


def _parse_publishing_links(text: str) -> dict:
    out: dict = {}
    zoom_line = _first_match(r"^\s*Zoom\s*=\s*(.+?)\s*$", text, re.MULTILINE)
    if zoom_line:
        rec = _first_match(
            r"(https?://[^\s]*zoom[^\s]*/rec/(?:share|play)/\S+)",
            zoom_line, re.IGNORECASE,
        )
        out["zoom"] = rec or _first_match(r"(https?://\S+)", zoom_line) or zoom_line.split()[0]
    session_pg = _first_match(r"^\s*Session pg\s*=\s*(\S+)", text, re.MULTILINE)
    if session_pg:
        out["session_page"] = session_pg
    intranet = _first_match(r"^\s*Intranet\s*=\s*(\S+)", text, re.MULTILINE)
    if intranet:
        out["intranet"] = intranet
    pod = _first_match(r"(https?://\S*podbean\.com/\S+)", text)
    if pod:
        out["podbean"] = pod
    vc_block = re.search(r"VINCAST\s*\n(.*?)(?:\n\s*\n|\Z)", text, re.DOTALL | re.IGNORECASE)
    if vc_block:
        url = _first_match(r"(https?://\S+)", vc_block.group(1))
        if url:
            out["vincast"] = url
    mb_block = re.search(r"Message board thread:\s*\n(.*?)(?:\n\s*\n|\Z)", text, re.DOTALL | re.IGNORECASE)
    if mb_block:
        url = _first_match(r"(https?://\S+)", mb_block.group(1))
        if url:
            out["mb_thread"] = url
    slides = _first_match(r"^\s*slides link\s*\n\s*(\S+)", text, re.MULTILINE | re.IGNORECASE)
    if slides:
        if not re.match(r"^https?://", slides, re.IGNORECASE):
            slides = "https://www.vin.com/" + slides.lstrip("/")
        out["slides"] = slides
    return out


def _parse_slide_resources(text: str) -> list[SlideResourceRecord]:
    out: list[SlideResourceRecord] = []
    region_match = re.search(r"(^@\d+[\s\S]*?)(?:\n\*\*|\Z)", text, re.MULTILINE)
    if not region_match:
        return out
    region = region_match.group(1)
    chunk_re = re.compile(r"@(\d+)\s*\n(.*?)(?=\n@\d+\s*\n|\Z)", re.DOTALL)
    order = 0
    for m in chunk_re.finditer(region):
        slide_num = int(m.group(1))
        body = m.group(2).strip()
        if not body:
            continue
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            urls = list(_URL_RE.finditer(line))
            if not urls:
                continue
            prev_end = 0
            carried_label: Optional[str] = None
            for url_match in urls:
                url = url_match.group(0).rstrip(",.;")
                preceding = line[prev_end:url_match.start()].strip(" -—:\t")
                label = preceding or carried_label
                if preceding:
                    carried_label = preceding
                out.append(SlideResourceRecord(
                    slide_number=slide_num, label=label, url=url, sort_order=order,
                ))
                order += 1
                prev_end = url_match.end()
    return out


def _parse_speakers(text: str) -> list[SpeakerRecord]:
    speakers: list[SpeakerRecord] = []
    mod_name = _first_match(r"^\s*\*?Moderator\s*=\s*(.+?)\s*$", text, re.MULTILINE)
    if mod_name:
        speakers.append(SpeakerRecord(role="moderator", name=mod_name, sort_order=0))
    bio_match = re.search(r"^\s*Bio\s*\n(.+?)(?=\n\s*\n|\Z)", text, re.DOTALL | re.MULTILINE)
    bio = bio_match.group(1).strip() if bio_match else None
    if bio:
        name, _ = _extract_speaker_name_from_bio(bio)
        credentials = _extract_credentials_near_bio(bio, text, name)
        if name:
            speakers.append(SpeakerRecord(
                role="primary", name=name, credentials=credentials, bio=bio, sort_order=1,
            ))
    return speakers


def _parse_tags(text: str) -> list[str]:
    line = _first_match(r"^\s*Tags:\s*(.+?)\s*$", text, re.MULTILINE)
    if not line:
        return []
    return [p.strip() for p in re.split(r",", line) if p.strip()]


def _parse_polls(text: str) -> Optional[str]:
    m = re.search(r"^\s*Polls\s*\n(.*?)(?=\n\s*\n|\Z)", text, re.DOTALL | re.MULTILINE)
    if not m:
        return None
    val = m.group(1).strip()
    return val or None


_POLLS_HEADER_RE = re.compile(
    r"^Slide\s+(\d+)\s*-\s*Poll\s+Question\s+#(\d+)\s*$", re.MULTILINE,
)
_POLLS_OPTION_RE = re.compile(r"^(\d+)\s*\((\d+)%\)\s+(.+?)\s*$")


def parse_polls_section(text: Optional[str]) -> list[dict]:
    if not text or not text.strip() or text.strip().lower() == "n/a":
        return []
    headers = list(_POLLS_HEADER_RE.finditer(text))
    if not headers:
        return []
    polls: list[dict] = []
    for i, h in enumerate(headers):
        slide_n = int(h.group(1))
        q_n = int(h.group(2))
        region_start = h.end()
        region_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        region = text[region_start:region_end]
        question = ""
        options: list[dict] = []
        question_set = False
        for ln in region.splitlines():
            stripped = ln.strip()
            if not stripped:
                continue
            if not question_set:
                question = stripped
                question_set = True
                continue
            m = _POLLS_OPTION_RE.match(stripped)
            if m:
                options.append({
                    "count":   int(m.group(1)),
                    "percent": int(m.group(2)),
                    "label":   m.group(3).strip(),
                })
        polls.append({
            "idx":      len(polls),
            "slide_n":  slide_n,
            "q_n":      q_n,
            "question": question,
            "options":  options,
            "status":   "extracted",
        })
    return polls


def parse_extras2(raw_text: str) -> ParsedManifest:
    """
    Parse an extras2.txt manifest. Always returns a ParsedManifest — never raises.
    Missing / unrecognized fields become None or [].
    """
    if not raw_text or not raw_text.strip():
        return ParsedManifest()
    try:
        m = ParsedManifest()
        m.code         = _first_match(r"^\s*session code\s*=\s*(\S+)", raw_text, re.MULTILINE)
        m.title_long   = _first_match(r"^\s*long title\s*=\s*(.+?)\s*$", raw_text, re.MULTILINE)
        m.title_short  = _first_match(r"^\s*short title\s*=\s*(.+?)\s*$", raw_text, re.MULTILINE)
        m.ce_broker_id = _first_match(r"CE Broker approved\s+([A-Z0-9\-]+)", raw_text)
        m.class_id     = _first_match(r"(VINR\d+-\d+)", raw_text)
        m.tags             = _parse_tags(raw_text)
        m.publishing_links = _parse_publishing_links(raw_text)
        m.polls            = _parse_polls(raw_text)
        m.polls_parsed     = parse_polls_section(raw_text)
        m.speakers         = _parse_speakers(raw_text)
        m.slide_resources  = _parse_slide_resources(raw_text)
        return m
    except Exception:
        logger.exception("extras2 parser failed — returning empty manifest")
        return ParsedManifest()
