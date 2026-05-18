"""
4-signal alignment engine.

For each transcript segment, score it against every slide_time_range and
pick the dominant slide. The 4 signals (LOCKED weights, audit §6):

  ALIGN_WEIGHT_SEMANTIC   = 0.35   — token overlap with slide bullets/text
  ALIGN_WEIGHT_COVERAGE   = 0.25   — fraction of segment inside slide range
  ALIGN_WEIGHT_TEMPORAL   = 0.25   — linear proximity to slide center
  ALIGN_WEIGHT_SEQUENTIAL = 0.15   — adjacency to prior segment's slide
  ALIGN_SEQUENTIAL_PENALTY= 0.8    — penalty for backward jumps

Phase 7i (parity-3) — closes the alignment drift gaps from re-audit:
  • #28 semantic = overlap/slide_tokens (MIC formula), not Jaccard
  • #29 temporal = linear 1.0 − distance/half (MIC), not Gaussian
  • #30 sequential = backward-only penalty (MIC), forward jumps allowed
  • #31 dominance = absolute gap top−runner_up (MIC), not share-of-total
  • #32 drift_flag = best_score<0.6 AND not uncertain (MIC), not (temporal≥0.7∧semantic<0.2)
  • #34 dead duplicate run_pre_ready_gate removed

Pre-ready gate moved to canonical home in engines/pre_ready_gate.py.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SegmentInput:
    segment_id: str
    seq: int
    start_time: float        # seconds
    end_time: float
    text: str


@dataclass
class SlideRangeInput:
    slide_id: str
    slide_number: int
    start_time: float
    end_time: float
    soft_start: float
    soft_end: float
    full_text: str           # slide.full_text or empty string
    bullets: str             # space-joined bullet text or empty


@dataclass
class AlignmentRecord:
    segment_id: str
    slide_id: Optional[str]
    confidence: float
    signals: dict
    drift_flag: bool
    anchor_hit: bool
    uncertain_flag: bool
    status: str              # 'assigned' | 'uncertain' | 'review'


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z][A-Za-z']*", text) if len(t) > 2}


def _semantic_score(segment_text: str, slide_text: str) -> float:
    """
    Phase 1 semantic signal: keyword/token overlap (#28).
    MIC formula: overlap / slide_tokens (NOT Jaccard). Bounded [0,1].
    """
    seg_tokens = _tokens(segment_text)
    slide_tokens = _tokens(slide_text)
    if not seg_tokens or not slide_tokens:
        return 0.0
    overlap = seg_tokens & slide_tokens
    return min(1.0, len(overlap) / max(1, len(slide_tokens)))


def _coverage_score(seg_start: float, seg_end: float, slide_start: float, slide_end: float) -> float:
    """Fraction of the segment's duration that falls inside the slide range."""
    overlap_start = max(seg_start, slide_start)
    overlap_end = min(seg_end, slide_end)
    overlap = max(0.0, overlap_end - overlap_start)
    seg_dur = max(0.001, seg_end - seg_start)
    return min(1.0, overlap / seg_dur)


def _temporal_score(seg_mid: float, slide_start: float, slide_end: float) -> float:
    """
    Temporal proximity (#29) — linear 1.0 − distance/window_half (MIC).
    1.0 = centered.
    """
    center = (slide_start + slide_end) / 2.0
    window_half = (slide_end - slide_start) / 2.0
    if window_half <= 0:
        return 0.0
    distance = abs(seg_mid - center)
    return max(0.0, 1.0 - (distance / window_half))


def _sequential_score(slide_number: int, prev_slide_number: Optional[int], penalty: float) -> float:
    """
    Sequential constraint (#30) — backward jumps only penalized.
    MIC rule: forward or same slide → 1.0. Backward jump → penalty (0.8).
    """
    if prev_slide_number is None:
        return 1.0
    if slide_number >= prev_slide_number:
        return 1.0
    return penalty


def align_segment(
    seg: SegmentInput,
    slide_ranges: list[SlideRangeInput],
    *,
    w_semantic: float = 0.35,
    w_coverage: float = 0.25,
    w_temporal: float = 0.25,
    w_sequential: float = 0.15,
    sequential_penalty: float = 0.8,
    prev_slide_number: Optional[int] = None,
    drift_confidence_penalty: float = 0.3,
) -> AlignmentRecord:
    if not slide_ranges:
        return AlignmentRecord(
            segment_id=seg.segment_id,
            slide_id=None,
            confidence=0.0,
            signals={"semantic": 0.0, "coverage": 0.0, "temporal": 0.0, "sequential": 0.0},
            drift_flag=False,
            anchor_hit=False,
            uncertain_flag=True,
            status="uncertain",
        )

    seg_mid = (seg.start_time + seg.end_time) / 2.0

    scores: list[tuple[float, SlideRangeInput, dict]] = []
    for sr in slide_ranges:
        sem = _semantic_score(seg.text, sr.full_text + " " + sr.bullets)
        cov = _coverage_score(seg.start_time, seg.end_time, sr.soft_start, sr.soft_end)
        tem = _temporal_score(seg_mid, sr.start_time, sr.end_time)
        seqv = _sequential_score(sr.slide_number, prev_slide_number, sequential_penalty)
        total = (
            w_semantic * sem
            + w_coverage * cov
            + w_temporal * tem
            + w_sequential * seqv
        )
        scores.append((total, sr, {
            "semantic":   round(sem, 4),
            "coverage":   round(cov, 4),
            "temporal":   round(tem, 4),
            "sequential": round(seqv, 4),
        }))

    # Pick winner + runner-up
    scores.sort(key=lambda s: -s[0])
    winner_total, winner_sr, winner_signals = scores[0]
    runner_total = scores[1][0] if len(scores) > 1 else 0.0

    # Dominance (#31) — absolute gap MIC-style.
    dominance = winner_total - runner_total
    uncertain = dominance < 0.6

    # Drift detection (#32) — MIC rule: best_score < 0.6 AND assignment is confident.
    drift_flag = False
    confidence = max(0.0, min(1.0, winner_total))
    if confidence < 0.6 and not uncertain:
        drift_flag = True
        confidence = max(0.0, confidence - drift_confidence_penalty)

    if uncertain:
        slide_id = None
        status = "uncertain"
    else:
        slide_id = winner_sr.slide_id
        status = "assigned" if confidence >= 0.6 else "review"

    return AlignmentRecord(
        segment_id=seg.segment_id,
        slide_id=slide_id,
        confidence=round(confidence, 4),
        signals=winner_signals,
        drift_flag=drift_flag,
        anchor_hit=winner_signals["temporal"] >= 0.85,
        uncertain_flag=uncertain,
        status=status,
    )
