"""
Fusion engine — combines visual + anchor + semantic signals into
slide_time_ranges with confidence scores.

LOCKED weights (audit §6, never tune without explicit approval):
  FUSION_WEIGHT_VISUAL    = 0.5
  FUSION_WEIGHT_ANCHOR    = 0.3
  FUSION_WEIGHT_SEMANTIC  = 0.2
  FUSION_BOUNDARY_THRESHOLD = 0.35

LOCKED Section 2 signal-gating invariant (closes 🟠 #23):
  IF visual_change < threshold AND anchor_confirmed == False:
      semantic signal CANNOT trigger a boundary alone

LOCKED Section 2 timestamp lock (closes 🟡 #24):
  Boundary timestamps are rounded to 0.5s precision after fusion — replay
  reproducibility relies on this.

Phase 7i (parity-3) — closes the 🟠 fusion gaps from the re-audit.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VisualSignal:
    timestamp: float
    strength: float
    frame_idx: int


@dataclass
class AnchorSignal:
    timestamp: float
    confirmed: bool
    visual_validated: bool
    semantic_score: float
    phrase: str = ""               # added in #83 for fusion debugging
    confidence: float = 0.0


@dataclass
class SemanticShift:
    timestamp: float
    shift_score: float


@dataclass
class SlideTimeRange:
    slide_id: Optional[str]
    slide_number: int
    start_time: float
    end_time: float
    slide_soft_start: float
    slide_soft_end: float
    confidence: float
    sources: dict = field(default_factory=dict)
    status: str = "assigned"


@dataclass
class FusionResult:
    slide_time_ranges: list[SlideTimeRange]
    input_hash: str
    inputs_dump: dict
    output_dump: dict


def _round_to_half(t: float) -> float:
    """Round timestamp to 0.5s precision — locked invariant (#24)."""
    return round(t * 2) / 2


def _signal_gate_passes(
    visual_change: float,
    anchor_confirmed: bool,
    visual_threshold: float,
) -> bool:
    """
    Signal-gating invariant (Section 2):
      IF visual_change < threshold AND anchor_confirmed == False:
          semantic CANNOT trigger boundary alone → return False
    """
    return not (visual_change < visual_threshold and not anchor_confirmed)


def run_fusion(
    session_id: str,
    slide_count: int,
    visual_signals: list[VisualSignal],
    anchor_signals: list[AnchorSignal],
    semantic_shifts: list[SemanticShift],
    total_duration: float,
    *,
    w_visual: float = 0.5,
    w_anchor: float = 0.3,
    w_semantic: float = 0.2,
    boundary_threshold: float = 0.35,
    soft_window: float = 5.0,
    visual_threshold: float = 8.0 / 255.0,
    anchor_window: float = 5.0,
) -> FusionResult:
    """
    Compute slide_time_ranges for `slide_count` slides over `total_duration`.

    Returns a FusionResult ready to write to slide_time_ranges + replay_log.
    """
    if slide_count <= 0 or total_duration <= 0:
        return FusionResult(slide_time_ranges=[], input_hash="", inputs_dump={}, output_dump={})

    # Pre-index anchors and semantics for gating logic.
    anchor_confirmed_times = [
        a.timestamp for a in anchor_signals if a.confirmed and a.visual_validated
    ]

    def _anchor_confirmed_near(t: float) -> bool:
        return any(abs(at - t) <= anchor_window for at in anchor_confirmed_times)

    candidates: list[tuple[float, float, dict]] = []  # (score, timestamp, sources)

    # Visual-driven candidates (always allowed — primary signal).
    for v in visual_signals:
        sources = {"visual": v.strength, "anchor": 0.0, "semantic": 0.0}
        score = w_visual * v.strength
        candidates.append((score, v.timestamp, sources))

    # Anchor-driven candidates (only confirmed anchors are usable).
    for a in anchor_signals:
        if not a.confirmed:
            continue
        strength = 1.0 if a.visual_validated else 0.6
        sources = {"visual": 0.0, "anchor": strength, "semantic": a.semantic_score}
        score = w_anchor * strength + w_semantic * a.semantic_score
        candidates.append((score, a.timestamp, sources))

    # Semantic-driven candidates — GATED by Section 2 invariant.
    # Semantic alone cannot trigger a boundary unless either visual ≥ threshold
    # or a confirmed anchor exists nearby.
    for s in semantic_shifts:
        # Find any nearby visual signal strength.
        nearby_visual = max(
            (v.strength for v in visual_signals if abs(v.timestamp - s.timestamp) <= anchor_window),
            default=0.0,
        )
        if not _signal_gate_passes(nearby_visual, _anchor_confirmed_near(s.timestamp), visual_threshold):
            continue  # gated — semantic cannot trigger alone
        sources = {"visual": 0.0, "anchor": 0.0, "semantic": s.shift_score}
        score = w_semantic * s.shift_score
        candidates.append((score, s.timestamp, sources))

    # Deduplicate candidates within 2s windows by keeping the highest score.
    candidates.sort(key=lambda c: -c[0])
    selected: list[tuple[float, float, dict]] = []
    for cand in candidates:
        if cand[0] < boundary_threshold:
            continue
        if any(abs(cand[1] - s[1]) < 2.0 for s in selected):
            continue
        selected.append(cand)
        if len(selected) >= slide_count - 1:
            break
    selected.sort(key=lambda c: c[1])

    # Lock timestamps to 0.5s precision (Section 2 invariant — #24).
    locked: list[tuple[float, float, dict]] = []
    seen_ts: set[float] = set()
    for score, ts, sources in selected:
        snapped = _round_to_half(ts)
        if snapped in seen_ts:
            continue
        seen_ts.add(snapped)
        locked.append((score, snapped, sources))
    selected = locked

    boundaries = [0.0] + [c[1] for c in selected] + [total_duration]
    # Pad if under-detected.
    while len(boundaries) - 1 < slide_count:
        gaps = [(boundaries[i + 1] - boundaries[i], i) for i in range(len(boundaries) - 1)]
        gaps.sort(reverse=True)
        gap, idx = gaps[0]
        mid = _round_to_half((boundaries[idx] + boundaries[idx + 1]) / 2.0)
        if mid in boundaries:
            mid = (boundaries[idx] + boundaries[idx + 1]) / 2.0
        boundaries.insert(idx + 1, mid)

    boundaries = sorted(boundaries[:slide_count + 1])

    slide_ranges: list[SlideTimeRange] = []
    selected_sources = {c[1]: c[2] for c in selected}
    for i in range(slide_count):
        start = boundaries[i]
        end = boundaries[i + 1]
        soft_start = max(0.0, start - soft_window)
        soft_end = min(total_duration, end + soft_window)
        boundary_score = 0.0
        for c in selected:
            if abs(c[1] - start) < 1.0 or abs(c[1] - end) < 1.0:
                boundary_score = max(boundary_score, c[0])
        confidence = max(0.3, min(1.0, boundary_score / (w_visual + w_anchor + w_semantic)))
        sources = selected_sources.get(start) or {"visual": 0.0, "anchor": 0.0, "semantic": 0.0}
        slide_ranges.append(SlideTimeRange(
            slide_id=None,
            slide_number=i,
            start_time=_round_to_half(start),
            end_time=_round_to_half(end),
            slide_soft_start=_round_to_half(soft_start),
            slide_soft_end=_round_to_half(soft_end),
            confidence=round(confidence, 3),
            sources=sources,
            status="assigned",
        ))

    inputs_dump = {
        "session_id":         session_id,
        "slide_count":        slide_count,
        "total_duration":     total_duration,
        "visual_count":       len(visual_signals),
        "anchor_count":       len(anchor_signals),
        "semantic_count":     len(semantic_shifts),
        "weights":            {"visual": w_visual, "anchor": w_anchor, "semantic": w_semantic},
        "boundary_threshold": boundary_threshold,
        "soft_window":        soft_window,
        "visual_threshold":   visual_threshold,
    }
    input_hash = hashlib.sha256(json.dumps(inputs_dump, sort_keys=True).encode()).hexdigest()
    output_dump = {
        "boundaries_selected": [{"ts": c[1], "score": c[0]} for c in selected],
        "ranges":              [
            {"slide": r.slide_number, "start": r.start_time, "end": r.end_time,
             "confidence": r.confidence}
            for r in slide_ranges
        ],
    }

    return FusionResult(
        slide_time_ranges=slide_ranges,
        input_hash=input_hash,
        inputs_dump=inputs_dump,
        output_dump=output_dump,
    )


# ─── Fusion pre-aligning gate ────────────────────────────────────────────────


class GateFailure(Exception):
    """5-assertion gate failed before fusing → aligning."""


def run_fusion_gate(
    slide_ranges: list[SlideTimeRange],
    total_duration: float,
    slide_count: int,
    segments: Optional[list[dict]] = None,
) -> None:
    """
    5-assertion gate before fusing → aligning. Ports MIC §8 verbatim (#26):
      GATE_1 boundary_count   — 2 ≤ count ≤ max(2, len(segments)//10) (when segments given)
                                else exact match with slide_count
      GATE_2 spacing_stddev   — boundary spacing stddev < total_duration * 0.5
      GATE_3 timeline_coverage — every segment falls inside ≥1 soft-window (when segments given)
      GATE_4 no_overlap        — slide_ranges do not overlap
      GATE_5 no_gaps_over_1s   — gaps between consecutive slide_ranges ≤ 1s

    Raises GateFailure on violation.
    """
    boundary_count = len(slide_ranges)
    seg_count = len(segments) if segments else 0

    # GATE_1
    if segments:
        if not (2 <= boundary_count <= max(2, seg_count // 10)):
            raise GateFailure(
                f"GATE_1 boundary_count: {boundary_count} not in [2, {max(2, seg_count // 10)}]"
            )
    else:
        if boundary_count != slide_count:
            raise GateFailure(f"GATE_1 boundary_count: {boundary_count} != slide_count {slide_count}")

    # GATE_2 spacing_stddev
    if boundary_count >= 2:
        starts = sorted(r.start_time for r in slide_ranges)
        spacings = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
        mean = sum(spacings) / len(spacings)
        variance = sum((s - mean) ** 2 for s in spacings) / len(spacings)
        stddev = math.sqrt(variance)
        if stddev >= total_duration * 0.5:
            raise GateFailure(
                f"GATE_2 spacing_stddev: {stddev:.2f} ≥ {total_duration * 0.5:.2f}"
            )
    else:
        raise GateFailure(f"GATE_2 spacing_stddev: only {boundary_count} boundary — insufficient")

    # GATE_3 timeline_coverage
    if segments:
        covered = 0
        for seg in segments:
            mid = (seg["start_time"] + seg["end_time"]) / 2.0
            for r in slide_ranges:
                if r.slide_soft_start <= mid <= r.slide_soft_end:
                    covered += 1
                    break
        if covered != seg_count:
            raise GateFailure(
                f"GATE_3 timeline_coverage: {covered}/{seg_count} segments inside a window"
            )

    # GATE_4 no_overlap
    sorted_ranges = sorted(slide_ranges, key=lambda r: r.start_time)
    for i in range(len(sorted_ranges) - 1):
        if sorted_ranges[i].end_time > sorted_ranges[i + 1].start_time + 0.01:
            raise GateFailure(
                f"GATE_4 no_overlap: slide {sorted_ranges[i].slide_number} overlaps next"
            )

    # GATE_5 no_gaps_over_1s
    for i in range(len(sorted_ranges) - 1):
        gap = sorted_ranges[i + 1].start_time - sorted_ranges[i].end_time
        if gap > 1.0:
            raise GateFailure(
                f"GATE_5 no_gaps_over_1s: {gap:.2f}s gap after slide {sorted_ranges[i].slide_number}"
            )
