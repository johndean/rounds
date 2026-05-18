"""
Anchor engine — phrase detector + cross-validation.

LOCKED Section 7 invariant (CLAUDE.md §7):
  An anchor is CONFIRMED only when:
    • An ANCHORS phrase appears in segment text, AND
    • (visual_change within ±ANCHOR_CROSS_VALIDATE_WINDOW OR semantic_shift > 0.3)
  Otherwise: speculative — not used as a boundary signal in fusion.

Phase 7i: closes 🔴 #81 (ANCHORS phrase list was absent — fusion's
locked 0.3 anchor weight was measuring something else entirely).

Used by:
  • anchor_task (Phase 6e) — scans segments + stores AnchorHit list in Redis
  • fusion_task (Phase 6h) — feeds LOCKED weight-3 anchor signal
"""
from __future__ import annotations

from dataclasses import dataclass


# Locked anchor phrase list (Section 7) — verbatim port from MIC.
ANCHORS: list[str] = [
    "next slide",
    "on this slide",
    "as you can see",
    "moving on",
    "let me show you",
    "here we can see",
    "on the left",
    "on the right",
    "as shown here",
    "turning to",
    "switching to",
    "the next topic",
]


@dataclass
class SemanticShift:
    """One semantic-shift signal at a segment boundary."""
    timestamp: float
    shift_score: float    # 0-1, token-overlap-based dissimilarity


@dataclass
class AnchorHit:
    """One confirmed-or-speculative anchor."""
    timestamp: float
    phrase: str               # the matched ANCHORS entry, or "" for pure-signal hits
    confidence: float         # 0.9 confirmed / 0.3 speculative
    visual_confirmed: bool    # cross-validation rule passed
    speculative: bool         # True = not used as boundary signal


def detect_anchors(
    segments: list[dict],                    # [{start_time, end_time, text}]
    visual_change_timestamps: list[float],
    semantic_shifts: list[SemanticShift] | list[dict],
    *,
    cross_validate_window: float = 5.0,
    semantic_threshold: float = 0.3,
) -> list[AnchorHit]:
    """
    Scan segments for ANCHORS phrases, cross-validate within ±window.

    Each AnchorHit gets confidence=0.9 if cross-validated, else 0.3 (speculative).
    Fusion only uses confidence values from non-speculative hits.
    """
    # Normalize semantic_shifts: accept either SemanticShift dataclasses or dicts.
    shifts_norm: list[tuple[float, float]] = []
    for s in semantic_shifts or []:
        if isinstance(s, SemanticShift):
            shifts_norm.append((s.timestamp, s.shift_score))
        elif isinstance(s, dict):
            shifts_norm.append((s.get("timestamp", 0.0), s.get("shift_score", 0.0)))

    hits: list[AnchorHit] = []
    for seg in segments or []:
        text_str = (seg.get("text") or "").lower()
        if not text_str:
            continue
        seg_mid = (seg.get("start_time", 0.0) + seg.get("end_time", 0.0)) / 2.0
        for phrase in ANCHORS:
            if phrase in text_str:
                visual_near = any(
                    abs(seg_mid - vc) <= cross_validate_window
                    for vc in visual_change_timestamps
                )
                semantic_near = any(
                    abs(seg_mid - ts) <= cross_validate_window and score > semantic_threshold
                    for ts, score in shifts_norm
                )
                confirmed = visual_near or semantic_near
                hits.append(AnchorHit(
                    timestamp=seg_mid,
                    phrase=phrase,
                    confidence=0.9 if confirmed else 0.3,
                    visual_confirmed=confirmed,
                    speculative=not confirmed,
                ))
                break  # one phrase per segment is sufficient

    hits.sort(key=lambda h: h.timestamp)
    return hits


def compute_semantic_shifts(segments: list[tuple[str, float]]) -> list[SemanticShift]:
    """
    Compute adjacent-segment semantic shifts via token-overlap dissimilarity.

    `segments` is [(text, end_time_seconds), ...] in chronological order.
    Returns one SemanticShift per boundary between consecutive segments.
    """
    shifts: list[SemanticShift] = []
    if len(segments) < 2:
        return shifts

    def _tokens(text: str) -> set[str]:
        return {t.lower() for t in text.split() if len(t) > 2}

    prev_tokens = _tokens(segments[0][0])
    for i in range(1, len(segments)):
        curr_tokens = _tokens(segments[i][0])
        if not prev_tokens and not curr_tokens:
            score = 0.0
        else:
            union = prev_tokens | curr_tokens
            intersect = prev_tokens & curr_tokens
            score = 1.0 - (len(intersect) / max(1, len(union)))
        shifts.append(SemanticShift(
            timestamp=segments[i - 1][1],
            shift_score=float(score),
        ))
        prev_tokens = curr_tokens
    return shifts
