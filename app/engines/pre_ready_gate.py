"""
Pre-ready gate — 5 named assertions before aligning → ready transition.

Verbatim port of MIC `app/engines/pre_ready_gate.py` (78 LOC).

  GATE_1 — Coverage: canonical output exists for every segment
  GATE_2 — Completeness: no required field is null on any segment
  GATE_3 — Timestamps: start_time < end_time, no overlapping segments
  GATE_4 — Template: template_id present and matches session_templates.template_id
  GATE_5 — IIL: if iil_config.enabled=true, normalized_text must not be null

Any failure → GateFailure raised → align_task writes status='review' on the
alignment rows + records the failure in validation_results with verdict
'ESCALATE'.

Phase 7b / U111.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class GateFailure(Exception):
    gate_id: str
    segment_id: Optional[str] = None
    reason: str = ""

    def __str__(self) -> str:
        seg = f" on segment {self.segment_id}" if self.segment_id else ""
        return f"Gate {self.gate_id} failed{seg}: {self.reason}"


_REQUIRED_FIELDS = {
    "segment_id", "start_time", "end_time", "text",
    "confidence", "status", "template_id",
    # slide_id may be null when status='uncertain'
}


def run_pre_ready_gate(
    segments: list[dict],
    iil_config: dict,
    session_template_id: str,
) -> bool:
    """
    Run all 5 pre-ready gate assertions. Raises GateFailure on first failure.

    `segments` is a list of dicts with at minimum the keys in _REQUIRED_FIELDS
    plus optional `slide_id`, `normalized_text`, `template_id`. Caller builds
    these dicts from the alignment + normalization_results join.
    """
    # GATE 1 — Coverage
    if not segments:
        raise GateFailure("GATE_1", None, "No segments — canonical output missing")

    sorted_segs = sorted(segments, key=lambda s: s.get("start_time", 0.0))

    for seg in sorted_segs:
        seg_id = seg.get("segment_id", "<unknown>")

        # GATE 2 — Completeness
        for field in _REQUIRED_FIELDS:
            if seg.get(field) is None and field != "slide_id":
                raise GateFailure("GATE_2", seg_id, f"Required field '{field}' is null")

        # GATE 4 — Template alignment
        if seg.get("template_id") != session_template_id:
            raise GateFailure(
                "GATE_4", seg_id,
                f"template_id mismatch: segment='{seg.get('template_id')}', "
                f"session='{session_template_id}'",
            )

        # GATE 5 — IIL
        if iil_config.get("enabled", False) and seg.get("normalized_text") is None:
            raise GateFailure("GATE_5", seg_id, "IIL enabled but normalized_text is null")

    # GATE 3 — Timestamps + no overlaps
    for i, seg in enumerate(sorted_segs):
        seg_id = seg.get("segment_id", "<unknown>")
        if seg["start_time"] >= seg["end_time"]:
            raise GateFailure(
                "GATE_3", seg_id,
                f"start_time ({seg['start_time']}) >= end_time ({seg['end_time']})",
            )
        if i > 0:
            prev = sorted_segs[i - 1]
            if seg["start_time"] < prev["end_time"]:
                raise GateFailure(
                    "GATE_3", seg_id,
                    f"Segment overlaps with previous: {prev['end_time']} > {seg['start_time']}",
                )

    return True
