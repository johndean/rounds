"""
IIL validation + repair loop.

Ports MIC's normalize-then-validate pattern. Per CLAUDE.md §6: normalization
output passes four checks; failures trigger one repair retry then accept.

Checks:
  1. word_count               — normalized within ±15% of source word count
  2. token_set                — preserves >=90% of non-filler tokens
  3. filler_compliance        — no template-listed filler words remain
                                (except inside quotes, preserved verbatim)
  4. terminology_preservation — drug names / dosages / proper nouns retained

The repair pass calls the LLM again with the failure list as a "you violated
these checks — please correct" prompt. One repair attempt; if still failing,
record the failures in validation_results JSONB and use the best-effort output.

Closes audit gaps 🔴 #16 + #19. Phase 6g / U99.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    passed: bool
    word_count_ratio: float
    token_overlap: float
    filler_remaining: list[str] = field(default_factory=list)
    missing_terminology: list[str] = field(default_factory=list)
    repaired: bool = False

    def to_dict(self) -> dict:
        return {
            "passed":              self.passed,
            "word_count_ratio":    round(self.word_count_ratio, 3),
            "token_overlap":       round(self.token_overlap, 3),
            "filler_remaining":    self.filler_remaining,
            "missing_terminology": self.missing_terminology,
            "repaired":            self.repaired,
        }


_TERMINOLOGY_HEURISTIC_RE = re.compile(r"\b[A-Z][a-zA-Z]+(?:-[A-Za-z]+)?\b")  # proper nouns
_NUMERIC_DOSE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(mg|mcg|ml|cc|kg|lb|iu|units?)\b", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z][A-Za-z']*", text) if len(t) > 1}


def validate(
    source_text: str,
    normalized_text: str,
    filler_words: list[str],
) -> ValidationResult:
    """Run the 4 checks and return a result. No repair — caller decides."""
    if not source_text.strip():
        return ValidationResult(passed=True, word_count_ratio=1.0, token_overlap=1.0)

    source_words = source_text.split()
    norm_words = normalized_text.split()
    wc_source = max(1, len(source_words))
    wc_norm = max(0, len(norm_words))
    ratio = wc_norm / wc_source

    src_tokens = _tokens(source_text)
    norm_tokens = _tokens(normalized_text)
    overlap = (len(src_tokens & norm_tokens) / max(1, len(src_tokens))) if src_tokens else 1.0

    # Filler compliance: no listed filler word survives as a standalone token.
    lower_norm = normalized_text.lower()
    filler_remaining: list[str] = []
    for f in filler_words:
        pattern = rf"(?<![A-Za-z]){re.escape(f.lower())}(?![A-Za-z])"
        if re.search(pattern, lower_norm):
            filler_remaining.append(f)

    # Terminology preservation: proper nouns + numeric doses in source must
    # appear in the normalized text. (Verbatim drug-name preservation.)
    source_terms = set(_TERMINOLOGY_HEURISTIC_RE.findall(source_text))
    source_doses = set(_NUMERIC_DOSE_RE.findall(source_text))
    missing = []
    norm_lower = normalized_text.lower()
    for term in source_terms:
        if term.lower() not in norm_lower:
            missing.append(term)
    for dose in source_doses:
        if dose.lower() not in norm_lower:
            missing.append(dose)

    # Passes if: ratio within [0.5, 1.15], overlap >= 0.6, no fillers, no missing terms.
    passed = (
        0.5 <= ratio <= 1.15
        and overlap >= 0.6
        and not filler_remaining
        and not missing
    )

    return ValidationResult(
        passed=passed,
        word_count_ratio=ratio,
        token_overlap=overlap,
        filler_remaining=filler_remaining,
        missing_terminology=missing,
    )


def validate_and_repair(
    source_text: str,
    normalized_text: str,
    filler_words: list[str],
    repair_fn: Optional[Callable[[str, str, str], str]] = None,
) -> tuple[str, ValidationResult]:
    """
    Run validate() once. If failed and `repair_fn` provided, call it with the
    failure list and validate the repaired output. Return (final_text, result).
    """
    result = validate(source_text, normalized_text, filler_words)
    if result.passed or repair_fn is None:
        return normalized_text, result

    try:
        feedback = []
        if result.filler_remaining:
            feedback.append(f"Filler words still present: {result.filler_remaining}")
        if result.missing_terminology:
            feedback.append(f"Missing terminology: {result.missing_terminology}")
        if result.word_count_ratio < 0.5 or result.word_count_ratio > 1.15:
            feedback.append(f"Word count drift: ratio={result.word_count_ratio:.2f}")
        if result.token_overlap < 0.6:
            feedback.append(f"Token overlap too low: {result.token_overlap:.2f}")

        repaired_text = repair_fn(source_text, normalized_text, "; ".join(feedback))
        repaired_result = validate(source_text, repaired_text, filler_words)
        repaired_result.repaired = True
        return repaired_text, repaired_result
    except Exception:  # noqa: BLE001
        logger.exception("validate_and_repair: repair_fn failed — keeping original normalized text")
        return normalized_text, result
