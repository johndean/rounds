"""
Fusion engine — combines visual + anchor + semantic signals into
slide_time_ranges with confidence scores.

Ports MIC's fusion logic. LOCKED weights (audit §6, never tune without
explicit approval):
  FUSION_WEIGHT_VISUAL    = 0.5
  FUSION_WEIGHT_ANCHOR    = 0.3
  FUSION_WEIGHT_SEMANTIC  = 0.2
  FUSION_BOUNDARY_THRESHOLD = 0.35

For each slide (1..N), compute its time range from:
  • Visual change at slide-N transition (frame_task signal)
  • Confirmed anchor near that boundary (anchor_task hit)
  • Semantic shift score
Confidence = weighted sum, clamped to [0,1].
Soft windows ± SOFT_WINDOW_EXPANSION (5s default) give downstream align
room to absorb segment ambiguity.

Closes audit gaps 🔴 #6, #18. Phase 6h / U104-U106.
"""
from __future__ import annotations

import hashlib
import json
import logging
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
) -> FusionResult:
    """
    Compute slide_time_ranges for `slide_count` slides over `total_duration`.

    Returns a FusionResult ready to write to slide_time_ranges + replay_log.
    """
    if slide_count <= 0 or total_duration <= 0:
        return FusionResult(slide_time_ranges=[], input_hash="", inputs_dump={}, output_dump={})

    # ── Find boundary candidates ─────────────────────────────────────────
    # Each candidate has a timestamp + weighted-sum score. Sort by score
    # descending, pick the top N-1 boundaries that beat the threshold and
    # are at least `min_gap` seconds apart.
    candidates: list[tuple[float, float, dict]] = []  # (score, timestamp, sources)

    for v in visual_signals:
        sources = {"visual": v.strength, "anchor": 0.0, "semantic": 0.0}
        score = w_visual * v.strength
        candidates.append((score, v.timestamp, sources))

    for a in anchor_signals:
        if not a.confirmed:
            continue
        strength = 1.0 if a.visual_validated else 0.6
        sources = {"visual": 0.0, "anchor": strength, "semantic": a.semantic_score}
        score = w_anchor * strength + w_semantic * a.semantic_score
        candidates.append((score, a.timestamp, sources))

    for s in semantic_shifts:
        sources = {"visual": 0.0, "anchor": 0.0, "semantic": s.shift_score}
        score = w_semantic * s.shift_score
        candidates.append((score, s.timestamp, sources))

    # Deduplicate candidates within 2-second windows by keeping the highest score.
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

    # Sort selected by timestamp.
    selected.sort(key=lambda c: c[1])

    # ── Build slide_time_ranges ──────────────────────────────────────────
    boundaries = [0.0] + [c[1] for c in selected] + [total_duration]
    # If we under-detected boundaries, pad with proportional ones so we
    # always produce exactly slide_count ranges.
    while len(boundaries) - 1 < slide_count:
        # Insert a proportional boundary at the largest gap.
        gaps = [(boundaries[i+1] - boundaries[i], i) for i in range(len(boundaries) - 1)]
        gaps.sort(reverse=True)
        gap, idx = gaps[0]
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
        # Confidence: did we have signal evidence for this boundary?
        boundary_score = 0.0
        for c in selected:
            if abs(c[1] - start) < 1.0 or abs(c[1] - end) < 1.0:
                boundary_score = max(boundary_score, c[0])
        confidence = max(0.3, min(1.0, boundary_score / (w_visual + w_anchor + w_semantic)))
        sources = selected_sources.get(start) or {"visual": 0.0, "anchor": 0.0, "semantic": 0.0}
        slide_ranges.append(SlideTimeRange(
            slide_id=None,  # caller fills in from slides table
            slide_number=i,
            start_time=round(start, 3),
            end_time=round(end, 3),
            slide_soft_start=round(soft_start, 3),
            slide_soft_end=round(soft_end, 3),
            confidence=round(confidence, 3),
            sources=sources,
            status="assigned",
        ))

    # ── Replay log inputs ────────────────────────────────────────────────
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


class GateFailure(Exception):
    """5-assertion gate failed before fusing → aligning."""


def run_fusion_gate(slide_ranges: list[SlideTimeRange], total_duration: float, slide_count: int) -> None:
    """
    5 assertions before allowing fusing → aligning:
      1. slide_ranges count matches slide_count
      2. Monotonic non-overlapping ranges
      3. First start_time ≈ 0
      4. Last end_time ≈ total_duration
      5. Every confidence in [0, 1]
    Raises GateFailure on violation.
    """
    if len(slide_ranges) != slide_count:
        raise GateFailure(f"gate: range count={len(slide_ranges)} != slide_count={slide_count}")
    last_end = -1.0
    for r in slide_ranges:
        if r.start_time < last_end - 0.01:
            raise GateFailure(f"gate: overlap at slide {r.slide_number}")
        last_end = r.end_time
    if abs(slide_ranges[0].start_time) > 1.0:
        raise GateFailure(f"gate: first start={slide_ranges[0].start_time} should be ~0")
    if abs(slide_ranges[-1].end_time - total_duration) > 5.0:
        raise GateFailure(
            f"gate: last end={slide_ranges[-1].end_time} vs total={total_duration}"
        )
    for r in slide_ranges:
        if not (0.0 <= r.confidence <= 1.0):
            raise GateFailure(f"gate: confidence={r.confidence} out of range at slide {r.slide_number}")
