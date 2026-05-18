"""
Deterministic 4-rule semantic segmenter.

Verbatim port of MIC `app/engines/segmenter.py` (151 LOC). Four rules
applied in exact order to a flat list of WordToken:

  Rule 1: Split on sentence-ending punctuation (. ? !)
  Rule 2: Merge consecutive segments if combined duration < 2 seconds
  Rule 3: Split a segment if duration > 20 seconds
  Rule 4: Split on detected silence pause >= 500ms

Content-deterministic segment ID: SHA256(session_id + str(start_ms)).
Same inputs → same IDs across re-runs → idempotent UPSERT.

Phase 7a / U114.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass
class WordToken:
    word: str
    start_time: float       # seconds
    end_time: float
    confidence: float


@dataclass
class RawSegment:
    segment_id: str         # content-hash from _make_segment_id
    start_time: float
    end_time: float
    text: str
    words: list[WordToken]
    confidence: float = 0.0


def make_segment_id(session_id: str, start_ms: int) -> str:
    """SHA256(session_id + str(start_ms)) — content-deterministic."""
    return hashlib.sha256(f"{session_id}{start_ms}".encode()).hexdigest()


_SENTENCE_END = {".", "?", "!"}
MIN_SEGMENT_DURATION = 2.0     # seconds — Rule 2
MAX_SEGMENT_DURATION = 20.0    # seconds — Rule 3
SILENCE_THRESHOLD = 0.5        # seconds — Rule 4


def _split_rule1(words: list[WordToken]) -> list[list[WordToken]]:
    """Split on sentence-ending punctuation."""
    if not words:
        return []
    groups: list[list[WordToken]] = []
    current: list[WordToken] = []
    for w in words:
        current.append(w)
        if w.word and w.word[-1] in _SENTENCE_END:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _split_rule4(groups: list[list[WordToken]]) -> list[list[WordToken]]:
    """Within each group, split on silence pauses >= SILENCE_THRESHOLD."""
    out: list[list[WordToken]] = []
    for group in groups:
        if not group:
            continue
        current: list[WordToken] = [group[0]]
        for prev, curr in zip(group, group[1:]):
            gap = curr.start_time - prev.end_time
            if gap >= SILENCE_THRESHOLD:
                out.append(current)
                current = [curr]
            else:
                current.append(curr)
        out.append(current)
    return out


def _merge_rule2(groups: list[list[WordToken]]) -> list[list[WordToken]]:
    """Merge consecutive segments whose combined duration < MIN_SEGMENT_DURATION."""
    if not groups:
        return groups
    merged: list[list[WordToken]] = [groups[0]]
    for g in groups[1:]:
        last = merged[-1]
        combined_duration = g[-1].end_time - last[0].start_time
        last_duration = last[-1].end_time - last[0].start_time
        # If either neighbor is below the floor and combined still respects max, merge.
        if (last_duration < MIN_SEGMENT_DURATION
                and combined_duration <= MAX_SEGMENT_DURATION):
            merged[-1] = last + g
        else:
            merged.append(g)
    return merged


def _split_rule3(groups: list[list[WordToken]]) -> list[list[WordToken]]:
    """Split any segment longer than MAX_SEGMENT_DURATION at the largest internal gap."""
    out: list[list[WordToken]] = []
    for g in groups:
        if not g:
            continue
        duration = g[-1].end_time - g[0].start_time
        if duration <= MAX_SEGMENT_DURATION:
            out.append(g)
            continue
        # Find the largest internal gap and split there. Repeat until all sub-segments
        # are within the cap.
        stack = [g]
        while stack:
            grp = stack.pop()
            dur = grp[-1].end_time - grp[0].start_time
            if dur <= MAX_SEGMENT_DURATION or len(grp) < 2:
                out.append(grp)
                continue
            # find max-gap index
            max_gap = -1.0
            max_idx = -1
            for i in range(1, len(grp)):
                gap = grp[i].start_time - grp[i - 1].end_time
                if gap > max_gap:
                    max_gap = gap
                    max_idx = i
            if max_idx < 1:
                out.append(grp)
                continue
            left = grp[:max_idx]
            right = grp[max_idx:]
            stack.append(right)
            stack.append(left)
    return out


def segment_words(session_id: str, words: list[WordToken]) -> list[RawSegment]:
    """
    Apply rules 1→4→2→3 (order chosen to match MIC) and return RawSegments
    with content-deterministic SHA256 IDs.
    """
    if not words:
        return []
    g1 = _split_rule1(words)
    g4 = _split_rule4(g1)
    g2 = _merge_rule2(g4)
    g3 = _split_rule3(g2)

    out: list[RawSegment] = []
    for group in g3:
        if not group:
            continue
        text = " ".join(w.word for w in group).strip()
        if not text:
            continue
        start_time = group[0].start_time
        end_time = group[-1].end_time
        avg_conf = sum(w.confidence for w in group) / max(1, len(group))
        seg_id = make_segment_id(session_id, int(round(start_time * 1000)))
        out.append(RawSegment(
            segment_id=seg_id,
            start_time=start_time,
            end_time=end_time,
            text=text,
            words=group,
            confidence=round(avg_conf, 4),
        ))
    return out
