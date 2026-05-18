"""
IIL Adaptive Learning Loop — port of MIC `app/iil/adaptive_learning.py`.

Runs after each session lands ready. Updates instructor_profiles with
real feature aggregation (rolling-average filler rate + compression ratio +
frequency-based filler discovery), not the simple bucketing 6q shipped.

Idempotent — safe to re-run on the same session. Non-fatal — failure
logged, never raised. Used by `learn_iil_task` in 7f.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProfileUpdate:
    instructor_id: str
    filler_words: list[str]            # discovered + carried-forward
    avg_filler_rate: float             # rolling-average across all sessions
    avg_compression_ratio: float       # rolling-average across all segments
    sessions_processed: int


def update_instructor_profile(
    session_id: str,
    instructor_id: str,
    session_patterns: list[dict],
    normalization_stats: list[dict],
    current_profile: dict,
) -> ProfileUpdate:
    """
    Idempotent profile update.

    Args:
      session_patterns: per-segment audit blobs from normalize:
        [{"tier1_removed": [...], "tier2_removed": [...], "filler_count": N, ...}]
      normalization_stats: per-segment normalize results:
        [{"filler_count": N, "compression_ratio": F, "raw_text": str}, ...]
      current_profile: {filler_words: [...], avg_filler_rate, avg_compression_ratio, sessions_processed}

    Returns: ProfileUpdate ready for SQL upsert.

    Discovery rule: a filler word is added to the persistent list when its
    frequency (occurrences / total words across this session) exceeds 3%.
    """
    try:
        filler_set: set[str] = set(current_profile.get("filler_words", []))

        # Count filler word frequencies across the session
        total_words = sum(len((s.get("raw_text") or "").split()) for s in normalization_stats)
        filler_counts: dict[str, int] = {}
        for pattern in session_patterns:
            for w in pattern.get("tier1_removed", []) + pattern.get("tier2_removed", []):
                w_lower = w.lower().strip()
                if w_lower:
                    filler_counts[w_lower] = filler_counts.get(w_lower, 0) + 1
        if total_words > 0:
            for word, count in filler_counts.items():
                if count / total_words > 0.03:
                    filler_set.add(word)

        # Rolling averages over this session
        if normalization_stats:
            session_filler_rate = (
                sum(s.get("filler_count", 0) for s in normalization_stats)
                / max(total_words, 1)
            )
            session_compression = sum(
                s.get("compression_ratio", 1.0) for s in normalization_stats
            ) / len(normalization_stats)
        else:
            session_filler_rate = 0.0
            session_compression = 1.0

        prior_n = current_profile.get("sessions_processed", 0)
        prior_filler = current_profile.get("avg_filler_rate", 0.0) or 0.0
        prior_compression = current_profile.get("avg_compression_ratio", 1.0) or 1.0

        # Running average — new_avg = (prior * n + current) / (n + 1)
        new_n = prior_n + 1
        new_filler = (prior_filler * prior_n + session_filler_rate) / new_n
        new_compression = (prior_compression * prior_n + session_compression) / new_n

        return ProfileUpdate(
            instructor_id=instructor_id,
            filler_words=sorted(filler_set),
            avg_filler_rate=round(new_filler, 4),
            avg_compression_ratio=round(new_compression, 4),
            sessions_processed=new_n,
        )

    except Exception as exc:  # noqa: BLE001
        logger.warning(f"adaptive_learning: non-fatal failure for {instructor_id}: {exc}")
        return ProfileUpdate(
            instructor_id=instructor_id,
            filler_words=current_profile.get("filler_words", []),
            avg_filler_rate=current_profile.get("avg_filler_rate", 0.0) or 0.0,
            avg_compression_ratio=current_profile.get("avg_compression_ratio", 1.0) or 1.0,
            sessions_processed=current_profile.get("sessions_processed", 0),
        )
