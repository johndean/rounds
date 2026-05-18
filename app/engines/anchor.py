"""
anchor engine — detects confirmed anchors from semantic + visual signals.

Anchor rule (LOCKED, CLAUDE.md §7):
  An anchor is CONFIRMED only when:
    visual_change within ±ANCHOR_CROSS_VALIDATE_WINDOW (5s default)
    OR semantic_shift > 0.3
  Otherwise: speculative — not used as a boundary signal.

Used by:
  • anchor_task (Phase 6e) — stores AnchorHit list in Redis
  • fusion_task  (Phase 6h) — feeds the LOCKED weight-3 anchor signal
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SemanticShift:
    """One semantic-shift signal at a segment boundary."""
    timestamp: float
    shift_score: float    # 0-1, token-overlap-based dissimilarity


@dataclass
class AnchorHit:
    """One confirmed-or-speculative anchor."""
    timestamp: float
    confirmed: bool       # True iff cross-validation rule passed
    visual_validated: bool
    semantic_score: float


def detect_anchors(
    visual_timestamps: list[float],
    semantic_shifts: list[SemanticShift],
    cross_validate_window: float = 5.0,
    semantic_threshold: float = 0.3,
) -> list[AnchorHit]:
    """
    Combine visual + semantic signals into anchor hits.

    Per CLAUDE.md §7: confirmed if visual within ±window OR semantic > threshold.
    Speculative hits are emitted with confirmed=False so the fusion engine
    can decide whether to use them as soft signals.
    """
    hits: list[AnchorHit] = []
    visual_sorted = sorted(visual_timestamps)

    for shift in semantic_shifts:
        within_window = any(
            abs(v - shift.timestamp) <= cross_validate_window
            for v in visual_sorted
        )
        meets_semantic = shift.shift_score > semantic_threshold
        confirmed = within_window or meets_semantic
        hits.append(
            AnchorHit(
                timestamp=shift.timestamp,
                confirmed=confirmed,
                visual_validated=within_window,
                semantic_score=shift.shift_score,
            )
        )

    # Also emit anchor hits at visual changes that have no nearby semantic
    # signal — these are pure-visual confirmed anchors (slide transitions
    # during silent moments).
    for v in visual_sorted:
        has_semantic = any(abs(s.timestamp - v) <= cross_validate_window for s in semantic_shifts)
        if not has_semantic:
            hits.append(
                AnchorHit(
                    timestamp=v,
                    confirmed=True,
                    visual_validated=True,
                    semantic_score=0.0,
                )
            )

    hits.sort(key=lambda h: h.timestamp)
    return hits


def compute_semantic_shifts(segments: list[tuple[str, float]]) -> list[SemanticShift]:
    """
    Compute adjacent-segment semantic shifts via token-overlap dissimilarity.

    `segments` is [(text, end_time_seconds), ...] in chronological order.
    Returns one SemanticShift per boundary between consecutive segments,
    timestamped at the boundary (end of segment i, start of segment i+1).
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
        shifts.append(
            SemanticShift(
                timestamp=segments[i - 1][1],
                shift_score=float(score),
            )
        )
        prev_tokens = curr_tokens
    return shifts
