"""
LCS-based word diff between raw STT and normalized text.

Used by `lcs_discrepancies_task` (Phase 6l) to produce a row in
`transcription_discrepancies` for every word-level divergence. The
classify_task then asks Gemini whether each diff is meaningful or noise.

Algorithm: standard dynamic-programming LCS, then walk the LCS to emit
delete/insert/replace operations as Diff entries.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WordDiff:
    """One word-level diff between STT and normalized text."""
    stt:        str | None     # original STT token (None = pure insert)
    ai:         str | None     # normalized token (None = pure delete)
    position:   int            # token index in original
    category:   str            # heuristic: medication / terminology / filler / punctuation / drift / low_confidence / other


_FILLER_TOKENS = {"um", "uh", "er", "ah", "hm", "mm", "you", "know", "basically", "like"}
_PUNCT_TOKENS = {".", ",", "!", "?", ";", ":", "-"}


def _classify_heuristic(stt: str | None, ai: str | None) -> str:
    """Cheap rule-based category. Gemini will refine via classify_task."""
    if stt is None and ai is not None:
        return "filler" if ai.lower() in _FILLER_TOKENS else "other"
    if ai is None and stt is not None:
        s = stt.lower()
        if s in _FILLER_TOKENS:
            return "filler"
        if s in _PUNCT_TOKENS:
            return "punctuation"
        return "other"
    if stt and ai:
        if stt.lower() == ai.lower():
            return "punctuation"  # case/punctuation-only diff
        if stt[:1].isupper() or ai[:1].isupper():
            return "terminology"
        if any(ch.isdigit() for ch in stt + ai):
            return "medication"
        return "drift"
    return "other"


def diff_words(stt_words: list[str], ai_words: list[str]) -> list[WordDiff]:
    """
    Return a list of WordDiff entries describing how STT differs from
    normalized AI text. Tokens that match are omitted — only diffs appear.
    """
    n, m = len(stt_words), len(ai_words)
    if n == 0 and m == 0:
        return []

    # DP table for LCS lengths
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if stt_words[i - 1].lower() == ai_words[j - 1].lower():
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # Walk backwards to extract diffs
    diffs: list[WordDiff] = []
    i, j = n, m
    while i > 0 and j > 0:
        if stt_words[i - 1].lower() == ai_words[j - 1].lower():
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            diffs.append(WordDiff(
                stt=stt_words[i - 1],
                ai=None,
                position=i - 1,
                category=_classify_heuristic(stt_words[i - 1], None),
            ))
            i -= 1
        else:
            diffs.append(WordDiff(
                stt=None,
                ai=ai_words[j - 1],
                position=i,
                category=_classify_heuristic(None, ai_words[j - 1]),
            ))
            j -= 1
    while i > 0:
        diffs.append(WordDiff(
            stt=stt_words[i - 1], ai=None, position=i - 1,
            category=_classify_heuristic(stt_words[i - 1], None),
        ))
        i -= 1
    while j > 0:
        diffs.append(WordDiff(
            stt=None, ai=ai_words[j - 1], position=0,
            category=_classify_heuristic(None, ai_words[j - 1]),
        ))
        j -= 1

    diffs.reverse()
    return diffs
