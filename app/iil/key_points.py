"""
Key Points engine — Phase 5 / MIC §25.

Optional annotation layer. NEVER part of the transcript itself.

LOCKED invariants (closes 🟠 #47 + #49):
  KP-01: Generated from normalized_text, not raw_text.
  KP-02: Segments with slide_id=NULL → key_points=[], available=False.
  KP-03: Segments with status='uncertain' → key_points=[], available=False.
  KP-04: Stored in key_points_annotations — never in segments / normalization_results.
  KP-05: Key points NEVER appear in the text field of any segment row.
  KP-06: Never included in exports by default — operator must explicitly enable.
  KP-07: Maximum 5 key points per segment.
  KP-08: Each key point ≤ 12 words.
  KP-09: Content only from normalized_text or assigned slide.bullets.

Phase 7i (parity-3) — verbatim port of MIC `app/iil/key_points.py`.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


MAX_KEY_POINTS = 5          # KP-07
MAX_KP_WORDS = 12           # KP-08


@dataclass
class KeyPointsResult:
    segment_id: str
    key_points: list[str]               # KP-07 max 5; KP-08 each ≤ 12 words
    explanation: str
    available: bool
    extraction_confidence: float


def extract_key_points(
    segment_id: str,
    normalized_text: Optional[str],     # KP-01
    slide_id: Optional[str],            # KP-02 — None → unavailable
    status: str,                        # KP-03 — uncertain → unavailable
    slide_bullets: list[str],           # KP-09 — allowed content source
    structure_extraction: bool = True,
) -> KeyPointsResult:
    """
    Extract key points per KP-01..KP-09. Returns available=False when
    activation gate or content conditions require it.
    """
    if not structure_extraction:
        return _unavailable(segment_id)

    if slide_id is None:
        return _unavailable(segment_id)

    if status == "uncertain":
        return _unavailable(segment_id)

    if not normalized_text:
        return _unavailable(segment_id)

    candidates = _extract_candidates(normalized_text, slide_bullets)

    points: list[str] = []
    for candidate in candidates:
        words = candidate.split()
        if len(words) > MAX_KP_WORDS:
            candidate = " ".join(words[:MAX_KP_WORDS])
        if candidate and candidate not in points:
            points.append(candidate)
        if len(points) >= MAX_KEY_POINTS:
            break

    confidence = (
        min(1.0, len(points) / max(MAX_KEY_POINTS, 1) + 0.2) if points else 0.0
    )

    return KeyPointsResult(
        segment_id=segment_id,
        key_points=points,
        explanation=f"Extracted {len(points)} key point(s) from normalized transcript and slide context.",
        available=bool(points),
        extraction_confidence=round(confidence, 4),
    )


def _unavailable(segment_id: str) -> KeyPointsResult:
    return KeyPointsResult(
        segment_id=segment_id,
        key_points=[],
        explanation="",
        available=False,
        extraction_confidence=0.0,
    )


def _extract_candidates(normalized_text: str, slide_bullets: list[str]) -> list[str]:
    candidates: list[str] = []

    # Slide bullets first (high-quality source).
    for bullet in slide_bullets or []:
        clean = (bullet or "").strip().rstrip(".")
        if clean and len(clean.split()) >= 3:
            candidates.append(_capitalize(clean))

    # Normalized text — split on sentence boundaries.
    sentences = re.split(r"[.!?]+", normalized_text or "")
    for sent in sentences:
        sent = sent.strip()
        if len(sent.split()) >= 4:
            kp = _extract_leading_phrase(sent)
            if kp and kp not in candidates:
                candidates.append(kp)

    return candidates


def _extract_leading_phrase(sentence: str) -> str:
    """Heuristic: take up to 12 words, trim at preposition/conjunction."""
    STOP_WORDS = {"and", "or", "but", "because", "although", "when", "where", "which", "that"}
    words = sentence.split()[:MAX_KP_WORDS]
    trimmed: list[str] = []
    for w in words:
        if w.lower() in STOP_WORDS and trimmed:
            break
        trimmed.append(w)
    result = " ".join(trimmed).rstrip(",;:")
    return _capitalize(result) if len(result.split()) >= 3 else ""


def _capitalize(s: str) -> str:
    return s[0].upper() + s[1:] if s else s
