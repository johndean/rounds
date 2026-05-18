"""
4-signal alignment engine.

For each transcript segment, score it against every slide_time_range and
pick the dominant slide. The 4 signals (LOCKED weights, audit §6):

  ALIGN_WEIGHT_SEMANTIC   = 0.35   — token overlap with slide bullets/text
  ALIGN_WEIGHT_COVERAGE   = 0.25   — fraction of segment inside slide range
  ALIGN_WEIGHT_TEMPORAL   = 0.25   — distance to slide center (gaussian-ish)
  ALIGN_WEIGHT_SEQUENTIAL = 0.15   — adjacency to prior segment's slide
  ALIGN_SEQUENTIAL_PENALTY= 0.8    — penalty for non-adjacent jumps

Dominance: top score / runner-up. dominance < 0.6 → status='uncertain',
slide_id=NULL. IIL drift flag set when temporal signal is high but
semantic is low — slide is in the right time window but content drift.

Closes audit gaps 🔴 #17, 🟠 #15. Phase 6i / U108-U112.
"""
from __future__ import annotations

import logging
import math
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


def _semantic_score(segment_tokens: set[str], slide_tokens: set[str]) -> float:
    if not segment_tokens or not slide_tokens:
        return 0.0
    return len(segment_tokens & slide_tokens) / max(1, len(segment_tokens | slide_tokens))


def _coverage_score(seg_start: float, seg_end: float, slide_start: float, slide_end: float) -> float:
    """Fraction of the segment's duration that falls inside the slide range."""
    overlap_start = max(seg_start, slide_start)
    overlap_end = min(seg_end, slide_end)
    overlap = max(0.0, overlap_end - overlap_start)
    seg_dur = max(0.001, seg_end - seg_start)
    return min(1.0, overlap / seg_dur)


def _temporal_score(seg_mid: float, slide_start: float, slide_end: float) -> float:
    """Gaussian-ish proximity to slide center. 1.0 = centered."""
    center = (slide_start + slide_end) / 2.0
    half = max(1.0, (slide_end - slide_start) / 2.0)
    distance = abs(seg_mid - center)
    return math.exp(-0.5 * (distance / half) ** 2)


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

    seg_tokens = _tokens(seg.text)
    seg_mid = (seg.start_time + seg.end_time) / 2.0

    scores: list[tuple[float, SlideRangeInput, dict]] = []
    for sr in slide_ranges:
        slide_tokens = _tokens(sr.full_text + " " + sr.bullets)
        sem = _semantic_score(seg_tokens, slide_tokens)
        cov = _coverage_score(seg.start_time, seg.end_time, sr.soft_start, sr.soft_end)
        tem = _temporal_score(seg_mid, sr.start_time, sr.end_time)
        seq = 1.0 if prev_slide_number is None else (
            1.0 if sr.slide_number == prev_slide_number or sr.slide_number == prev_slide_number + 1
            else sequential_penalty
        )
        total = (
            w_semantic * sem
            + w_coverage * cov
            + w_temporal * tem
            + w_sequential * seq
        )
        scores.append((total, sr, {
            "semantic":   round(sem, 3),
            "coverage":   round(cov, 3),
            "temporal":   round(tem, 3),
            "sequential": round(seq, 3),
        }))

    # Pick winner + runner-up
    scores.sort(key=lambda s: -s[0])
    winner_total, winner_sr, winner_signals = scores[0]
    runner_total = scores[1][0] if len(scores) > 1 else 0.0

    dominance = winner_total / max(0.01, winner_total + runner_total)
    uncertain = dominance < 0.6
    # Drift flag: high temporal score (correct time window) but low semantic
    drift_flag = (
        winner_signals["temporal"] >= 0.7
        and winner_signals["semantic"] < 0.2
    )
    confidence = max(0.0, min(1.0, winner_total))
    if drift_flag:
        confidence = max(0.0, confidence - drift_confidence_penalty)

    return AlignmentRecord(
        segment_id=seg.segment_id,
        slide_id=None if uncertain else winner_sr.slide_id,
        confidence=round(confidence, 3),
        signals=winner_signals,
        drift_flag=drift_flag,
        anchor_hit=winner_signals["temporal"] >= 0.85,
        uncertain_flag=uncertain,
        status="uncertain" if uncertain else "assigned",
    )


# ─── Pre-ready gate ─────────────────────────────────────────────────────


class GateFailure(Exception):
    """5-assertion gate failed before aligning→ready."""


def run_pre_ready_gate(
    alignments: list[AlignmentRecord],
    segment_count: int,
    slide_count: int,
) -> None:
    """
    5 assertions before allowing aligning → ready:
      1. alignments count = segment count
      2. < 20% of alignments uncertain (else require review)
      3. assigned alignments have non-null slide_id
      4. drift_flag count < 25% of total
      5. every confidence in [0,1]
    """
    if len(alignments) != segment_count:
        raise GateFailure(f"gate: alignments={len(alignments)} != segments={segment_count}")
    uncertain = sum(1 for a in alignments if a.uncertain_flag)
    if alignments and uncertain / len(alignments) > 0.2:
        raise GateFailure(
            f"gate: uncertain ratio {uncertain}/{len(alignments)} > 20% — needs human review"
        )
    drift = sum(1 for a in alignments if a.drift_flag)
    if alignments and drift / len(alignments) > 0.25:
        raise GateFailure(f"gate: drift ratio {drift}/{len(alignments)} > 25%")
    for a in alignments:
        if a.status == "assigned" and not a.slide_id:
            raise GateFailure(f"gate: assigned alignment has no slide_id: {a.segment_id}")
        if not (0.0 <= a.confidence <= 1.0):
            raise GateFailure(f"gate: confidence={a.confidence} out of range for {a.segment_id}")
    # slide_count just available for future assertions; not used currently.
