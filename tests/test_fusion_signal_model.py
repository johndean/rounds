"""
Fusion signal model — MIC verbatim parity.

Phase 7j zero-gap parity: verifies the visual-driven, summed-3-signal
candidate model (not the parity-3 per-signal candidate model).
"""
from __future__ import annotations

from app.engines.fusion import (
    AnchorSignal,
    SemanticShift,
    VisualSignal,
    _round_to_half,
    run_fusion,
)


# ─── Helpers ───────────────────────────────────────────────────────────────


def _visual(t: float, strength: float = 0.5, idx: int = 0) -> VisualSignal:
    return VisualSignal(timestamp=t, strength=strength, frame_idx=idx)


def _anchor(t: float, conf: float = 0.9, visual_confirmed: bool = True, phrase: str = "next slide") -> AnchorSignal:
    return AnchorSignal(timestamp=t, confidence=conf, phrase=phrase, visual_confirmed=visual_confirmed)


def _semantic(t: float, score: float = 0.6) -> SemanticShift:
    return SemanticShift(timestamp=t, shift_score=score)


# ─── Round-to-half lock ────────────────────────────────────────────────────


def test_round_to_half():
    assert _round_to_half(10.27) == 10.5
    assert _round_to_half(10.0) == 10.0
    assert _round_to_half(10.74) == 10.5
    assert _round_to_half(10.76) == 11.0


# ─── Single-signal candidates ──────────────────────────────────────────────


def test_visual_only_strong_enough_to_pass_threshold():
    """A strong-enough visual signal alone clears 0.35 threshold."""
    res = run_fusion(
        session_id="s1",
        visual_signals=[_visual(10.0, strength=0.9)],
        anchor_signals=[],
        semantic_shifts=[],
        total_duration=60.0,
    )
    # 0.5 * 0.9 = 0.45 > 0.35 → 1 boundary, 1 range
    assert len(res.boundaries) == 1
    assert len(res.slide_time_ranges) == 1
    assert res.boundaries[0].fusion_score > 0.35


def test_visual_too_weak_alone():
    """Visual=0.4 → score=0.2 < 0.35 → rejected."""
    res = run_fusion(
        session_id="s1",
        visual_signals=[_visual(10.0, strength=0.4)],
        anchor_signals=[],
        semantic_shifts=[],
        total_duration=60.0,
    )
    assert len(res.boundaries) == 0


# ─── Signal gating ─────────────────────────────────────────────────────────


def test_signal_gate_kills_semantic_when_visual_weak_and_no_anchor():
    """
    Visual=0.01 (below 8/255 threshold), no anchor, semantic=0.9.
    Section 2 invariant: semantic CANNOT trigger boundary alone.
    Score = 0.5*0.01 + 0.3*0 + 0.2*0 (semantic gated to 0) = 0.005 → reject.
    """
    res = run_fusion(
        session_id="s1",
        visual_signals=[_visual(10.0, strength=0.01)],
        anchor_signals=[],
        semantic_shifts=[_semantic(10.0, score=0.9)],
        total_duration=60.0,
    )
    assert len(res.boundaries) == 0, "semantic alone must not trigger boundary"


def test_signal_gate_allows_semantic_when_anchor_confirmed():
    """Confirmed anchor at same timestamp → semantic NOT gated."""
    res = run_fusion(
        session_id="s1",
        visual_signals=[_visual(10.0, strength=0.01)],  # below visual threshold
        anchor_signals=[_anchor(10.0, conf=0.9, visual_confirmed=True)],
        semantic_shifts=[_semantic(10.0, score=0.9)],
        total_duration=60.0,
    )
    # Score = 0.5*0.01 + 0.3*0.9 + 0.2*0.9 = 0.005 + 0.27 + 0.18 = 0.455 → accept
    assert len(res.boundaries) == 1


# ─── Summed-score model (MIC verbatim) ─────────────────────────────────────


def test_summed_score_combines_all_three_signals():
    """Score should sum 0.5·v + 0.3·a + 0.2·s — not pick the max of three."""
    res = run_fusion(
        session_id="s1",
        visual_signals=[_visual(10.0, strength=0.6)],
        anchor_signals=[_anchor(10.0, conf=0.8, visual_confirmed=True)],
        semantic_shifts=[_semantic(10.0, score=0.7)],
        total_duration=60.0,
    )
    assert len(res.boundaries) == 1
    # 0.5*0.6 + 0.3*0.8 + 0.2*0.7 = 0.30 + 0.24 + 0.14 = 0.68
    assert abs(res.boundaries[0].fusion_score - 0.68) < 0.001


def test_anchor_cross_validate_window():
    """Anchor at t=14.5 (visual_confirmed) → inside ±5s of t=10 → contributes."""
    res = run_fusion(
        session_id="s1",
        visual_signals=[_visual(10.0, strength=0.4)],  # 0.5*0.4 = 0.20 alone
        anchor_signals=[_anchor(14.5, conf=0.9, visual_confirmed=True)],
        semantic_shifts=[],
        total_duration=60.0,
    )
    # 0.20 + 0.3*0.9 = 0.47 > 0.35 → accept
    assert len(res.boundaries) == 1


def test_anchor_outside_cross_validate_window_does_not_contribute():
    """Anchor at t=16 → outside ±5s of t=10 → does not contribute."""
    res = run_fusion(
        session_id="s1",
        visual_signals=[_visual(10.0, strength=0.4)],
        anchor_signals=[_anchor(16.0, conf=0.9, visual_confirmed=True)],
        semantic_shifts=[],
        total_duration=60.0,
    )
    # 0.5*0.4 = 0.20 < 0.35 → reject
    assert len(res.boundaries) == 0


# ─── No-padding behavior ───────────────────────────────────────────────────


def test_no_proportional_padding():
    """
    Fusion must NOT pad boundaries to a slide_count target. It returns
    however many boundaries clear the threshold.
    """
    # 2 strong visual signals + no other → exactly 2 boundaries.
    res = run_fusion(
        session_id="s1",
        visual_signals=[
            _visual(10.0, strength=0.9, idx=0),
            _visual(30.0, strength=0.9, idx=1),
        ],
        anchor_signals=[],
        semantic_shifts=[],
        total_duration=120.0,
    )
    assert len(res.boundaries) == 2
    # No "slide_count=5 → pad with 3 proportional" trickery.


def test_timestamp_lock_to_half_second():
    """Boundary timestamps are snapped to 0.5s precision."""
    res = run_fusion(
        session_id="s1",
        visual_signals=[_visual(10.27, strength=0.9)],
        anchor_signals=[],
        semantic_shifts=[],
        total_duration=60.0,
    )
    assert res.boundaries[0].timestamp == 10.5


# ─── Soft windows ──────────────────────────────────────────────────────────


def test_first_window_starts_at_zero():
    """First slide_time_range always starts at 0.0."""
    res = run_fusion(
        session_id="s1",
        visual_signals=[_visual(10.0, strength=0.9), _visual(30.0, strength=0.9, idx=1)],
        anchor_signals=[],
        semantic_shifts=[],
        total_duration=60.0,
    )
    assert res.slide_time_ranges[0].start_time == 0.0


# ─── Replay metadata ───────────────────────────────────────────────────────


def test_replay_metadata_populated():
    """Every fusion run writes input_hash + replay_metadata."""
    res = run_fusion(
        session_id="s1",
        visual_signals=[_visual(10.0, strength=0.9)],
        anchor_signals=[],
        semantic_shifts=[],
        total_duration=60.0,
    )
    assert len(res.input_hash) == 64  # sha256 hex
    assert res.replay_metadata["boundary_count"] == 1
    assert res.replay_metadata["total_duration"] == 60.0
