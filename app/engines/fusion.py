"""
Fusion engine — combines visual + anchor + semantic signals into
slide_time_ranges with confidence scores.

LOCKED weights (audit §6, never tune without explicit approval):
  FUSION_WEIGHT_VISUAL    = 0.5
  FUSION_WEIGHT_ANCHOR    = 0.3
  FUSION_WEIGHT_SEMANTIC  = 0.2
  FUSION_BOUNDARY_THRESHOLD = 0.35

LOCKED Section 2 signal-gating invariant:
  IF visual_change < threshold AND anchor_confirmed == False:
      semantic signal CANNOT trigger a boundary alone

LOCKED Section 2 timestamp lock:
  Boundary timestamps are rounded to 0.5s precision after fusion — replay
  reproducibility relies on this.

Phase 7j (zero-gap parity) — verbatim port of MIC fusion model:
  • One candidate per visual signal (not three per location)
  • Per-candidate score sums all 3 weighted signals
  • Anchor + semantic pulled from rounded-timestamp maps within ±5s
  • NO slide_count parameter, NO proportional padding
  • 3s merge-nearby window, 5s soft-window expansion
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VisualSignal:
    timestamp: float          # raw timestamp from frame diff
    strength: float           # normalized [0,1]
    frame_idx: int


@dataclass
class AnchorSignal:
    timestamp: float
    confidence: float         # [0,1]
    phrase: str               # the matched ANCHORS entry (or "" for pure-signal hits)
    visual_confirmed: bool    # cross-validation rule passed (visual within ±5s OR sem>0.3)


@dataclass
class SemanticShift:
    timestamp: float
    shift_score: float        # [0,1] keyword/token overlap delta


@dataclass
class BoundaryCandidate:
    timestamp: float
    visual_strength: float
    anchor_confidence: float
    semantic_shift: float
    fusion_score: float
    sources: dict             # {visual, anchor, semantic}
    accepted: bool


@dataclass
class SlideTimeRange:
    slide_id: Optional[str]   # positional 1..N from fusion; caller maps to DB slide ids
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
    boundaries: list[BoundaryCandidate]
    input_hash: str
    inputs_dump: dict
    output_dump: dict
    replay_metadata: dict


def _round_to_half(t: float) -> float:
    """Round timestamp to 0.5s precision — locked Section 2 invariant."""
    return round(t * 2) / 2


def _compute_fusion_score(
    visual_strength: float,
    anchor_confidence: float,
    semantic_shift: float,
    *,
    w_visual: float,
    w_anchor: float,
    w_semantic: float,
) -> float:
    """
    Locked fusion score formula (Section 2):
      score = (0.5 × visual_strength) + (0.3 × anchor_confidence) + (0.2 × semantic_shift)
    """
    return (
        w_visual   * visual_strength
        + w_anchor * anchor_confidence
        + w_semantic * semantic_shift
    )


def _signal_gate_passes(
    visual_change: float,
    anchor_confirmed: bool,
    visual_threshold: float,
) -> bool:
    """
    Signal gating invariant (Section 2):
      IF visual_change < threshold AND anchor_confirmed == False:
          semantic CANNOT trigger boundary alone → return False
    """
    return not (visual_change < visual_threshold and not anchor_confirmed)


def _merge_nearby_boundaries(
    candidates: list[BoundaryCandidate],
    merge_window: float,
) -> list[BoundaryCandidate]:
    """
    Consolidate boundaries within `merge_window` — pick max fusion_score per cluster.
    """
    if not candidates:
        return []
    sorted_cands = sorted(candidates, key=lambda c: c.timestamp)
    merged: list[BoundaryCandidate] = []
    cluster: list[BoundaryCandidate] = [sorted_cands[0]]
    for c in sorted_cands[1:]:
        if c.timestamp - cluster[-1].timestamp <= merge_window:
            cluster.append(c)
        else:
            merged.append(max(cluster, key=lambda x: x.fusion_score))
            cluster = [c]
    merged.append(max(cluster, key=lambda x: x.fusion_score))
    return merged


def _lock_boundary_timestamps(
    candidates: list[BoundaryCandidate],
) -> list[BoundaryCandidate]:
    """
    Deterministic boundary lock: round each to 0.5s, sort, deduplicate by snapped ts.
    """
    locked: list[BoundaryCandidate] = []
    seen: set[float] = set()
    for c in sorted(candidates, key=lambda x: x.timestamp):
        t = _round_to_half(c.timestamp)
        if t in seen:
            continue
        seen.add(t)
        locked.append(BoundaryCandidate(
            timestamp=t,
            visual_strength=c.visual_strength,
            anchor_confidence=c.anchor_confidence,
            semantic_shift=c.semantic_shift,
            fusion_score=c.fusion_score,
            sources=c.sources,
            accepted=c.accepted,
        ))
    return locked


def _apply_soft_windows(
    boundaries: list[BoundaryCandidate],
    total_duration: float,
    soft_window: float,
) -> list[SlideTimeRange]:
    """
    Soft window applier: boundary − 5s / next_boundary + 5s.
    Invariants enforced:
      • 100% coverage (last window extends to total_duration)
      • no overlaps (soft_start clamped to prev soft_end)
      • first window starts at 0.0
    """
    if not boundaries:
        return []

    timestamps = [b.timestamp for b in boundaries]
    slide_ranges: list[SlideTimeRange] = []

    for i, b in enumerate(boundaries):
        start = timestamps[i]
        end = timestamps[i + 1] if i + 1 < len(timestamps) else total_duration

        soft_start = max(0.0, start - soft_window)
        soft_end = min(total_duration, end + soft_window)

        # Clamp overlaps with adjacent windows
        if i > 0 and slide_ranges:
            prev_end = slide_ranges[i - 1].slide_soft_end
            if soft_start < prev_end:
                soft_start = prev_end

        slide_ranges.append(SlideTimeRange(
            slide_id=None,
            slide_number=i + 1,
            start_time=_round_to_half(start),
            end_time=_round_to_half(end),
            slide_soft_start=_round_to_half(soft_start),
            slide_soft_end=_round_to_half(soft_end),
            confidence=round(b.fusion_score, 4),
            sources=b.sources,
            status="assigned",
        ))

    # Ensure first window starts at 0
    if slide_ranges:
        slide_ranges[0] = SlideTimeRange(
            slide_id=slide_ranges[0].slide_id,
            slide_number=slide_ranges[0].slide_number,
            start_time=0.0,
            end_time=slide_ranges[0].end_time,
            slide_soft_start=0.0,
            slide_soft_end=slide_ranges[0].slide_soft_end,
            confidence=slide_ranges[0].confidence,
            sources=slide_ranges[0].sources,
            status=slide_ranges[0].status,
        )

    return slide_ranges


def run_fusion(
    session_id: str,
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
    merge_window: float = 3.0,
    anchor_window: float = 5.0,
    visual_threshold: float = 8.0 / 255.0,
) -> FusionResult:
    """
    Main fusion entry point. Phase 1 only — no embedding calls.
    Always writes replay metadata. Iterates visual signals only (MIC verbatim);
    anchor + semantic are pulled from rounded-timestamp maps with ±anchor_window
    cross-validation. Score per candidate sums all three weighted signals.
    """
    # Build input hash for reproducibility.
    input_data = {
        "session_id": session_id,
        "visual":   [asdict(v) for v in visual_signals],
        "anchor":   [asdict(a) for a in anchor_signals],
        "semantic": [asdict(s) for s in semantic_shifts],
    }
    input_hash = hashlib.sha256(json.dumps(input_data, sort_keys=True).encode()).hexdigest()

    if not visual_signals or total_duration <= 0:
        return FusionResult(
            slide_time_ranges=[],
            boundaries=[],
            input_hash=input_hash,
            inputs_dump=input_data,
            output_dump={"boundaries": [], "ranges": []},
            replay_metadata={"boundary_count": 0, "total_duration": total_duration},
        )

    # Build timestamp-indexed maps (rounded to 0.5s lock).
    anchor_map: dict[float, AnchorSignal] = {
        _round_to_half(a.timestamp): a for a in anchor_signals
    }
    semantic_map: dict[float, SemanticShift] = {
        _round_to_half(s.timestamp): s for s in semantic_shifts
    }

    candidates: list[BoundaryCandidate] = []

    for v in visual_signals:
        t = _round_to_half(v.timestamp)

        # Find max anchor_conf within ±anchor_window where visual_confirmed.
        anchor_conf = 0.0
        anchor_confirmed = False
        for a_t, a in anchor_map.items():
            if abs(a_t - t) <= anchor_window and a.visual_confirmed:
                if a.confidence > anchor_conf:
                    anchor_conf = a.confidence
                anchor_confirmed = True

        # Semantic shift at this timestamp (snapped).
        semantic = semantic_map.get(t)
        sem_score = semantic.shift_score if semantic else 0.0

        # Signal gate — semantic cannot trigger alone.
        if not _signal_gate_passes(v.strength, anchor_confirmed, visual_threshold):
            sem_score = 0.0

        score = _compute_fusion_score(
            v.strength, anchor_conf, sem_score,
            w_visual=w_visual, w_anchor=w_anchor, w_semantic=w_semantic,
        )

        if score > boundary_threshold:
            candidates.append(BoundaryCandidate(
                timestamp=t,
                visual_strength=v.strength,
                anchor_confidence=anchor_conf,
                semantic_shift=sem_score,
                fusion_score=score,
                sources={
                    "visual":   v.strength,
                    "anchor":   anchor_conf,
                    "semantic": sem_score,
                },
                accepted=True,
            ))

    # Consolidate, lock, apply soft windows.
    merged = _merge_nearby_boundaries(candidates, merge_window)
    locked = _lock_boundary_timestamps(merged)
    slide_ranges = _apply_soft_windows(locked, total_duration, soft_window)

    inputs_dump = {
        "session_id":         session_id,
        "total_duration":     total_duration,
        "visual_count":       len(visual_signals),
        "anchor_count":       len(anchor_signals),
        "semantic_count":     len(semantic_shifts),
        "weights":            {"visual": w_visual, "anchor": w_anchor, "semantic": w_semantic},
        "boundary_threshold": boundary_threshold,
        "soft_window":        soft_window,
        "merge_window":       merge_window,
        "anchor_window":      anchor_window,
        "visual_threshold":   visual_threshold,
    }
    output_dump = {
        "boundaries":      [
            {"ts": b.timestamp, "score": b.fusion_score, "sources": b.sources}
            for b in locked
        ],
        "ranges":          [
            {"slide": r.slide_number, "start": r.start_time, "end": r.end_time,
             "confidence": r.confidence}
            for r in slide_ranges
        ],
    }
    replay_metadata = {
        "boundary_count": len(locked),
        "total_duration": total_duration,
    }

    return FusionResult(
        slide_time_ranges=slide_ranges,
        boundaries=locked,
        input_hash=input_hash,
        inputs_dump=inputs_dump,
        output_dump=output_dump,
        replay_metadata=replay_metadata,
    )


# ─── Fusion pre-aligning gate ────────────────────────────────────────────────


class GateFailure(Exception):
    """5-assertion gate failed before fusing → aligning."""


def run_fusion_gate(
    slide_ranges: list[SlideTimeRange],
    total_duration: float,
    segments: Optional[list[dict]] = None,
) -> None:
    """
    5-assertion gate before fusing → aligning. MIC verbatim (#26):
      GATE_1 boundary_count  — 2 ≤ count ≤ max(2, len(segments)//10) when segments given
      GATE_2 spacing_stddev  — boundary spacing stddev < total_duration * 0.5
      GATE_3 timeline_coverage — every segment midpoint falls inside ≥1 soft-window
      GATE_4 no_overlap      — slide_ranges do not overlap
      GATE_5 no_gaps_over_1s — gaps between consecutive ranges ≤ 1s

    Raises GateFailure on violation.
    """
    boundary_count = len(slide_ranges)
    seg_count = len(segments) if segments else 0

    if segments:
        if not (2 <= boundary_count <= max(2, seg_count // 10)):
            raise GateFailure(
                f"GATE_1 boundary_count: {boundary_count} not in [2, {max(2, seg_count // 10)}]"
            )
    else:
        if boundary_count < 2:
            raise GateFailure(f"GATE_1 boundary_count: {boundary_count} < 2 (insufficient)")

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
        raise GateFailure(f"GATE_2 spacing_stddev: only {boundary_count} boundary")

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

    sorted_ranges = sorted(slide_ranges, key=lambda r: r.start_time)
    for i in range(len(sorted_ranges) - 1):
        if sorted_ranges[i].end_time > sorted_ranges[i + 1].start_time + 0.01:
            raise GateFailure(
                f"GATE_4 no_overlap: slide {sorted_ranges[i].slide_number} overlaps next"
            )

    for i in range(len(sorted_ranges) - 1):
        gap = sorted_ranges[i + 1].start_time - sorted_ranges[i].end_time
        if gap > 1.0:
            raise GateFailure(
                f"GATE_5 no_gaps_over_1s: {gap:.2f}s gap after slide {sorted_ranges[i].slide_number}"
            )
