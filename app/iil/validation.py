"""
IIL validation + repair loop — verbatim port of MIC `app/iil/validation.py`.

LOCKED contract (closes design-deviation #16 from parity-3 re-audit):

  MAX_REPAIR_ATTEMPTS = 2

  Four named content-based checks:
    check1 — content words (>3 chars, non-TIER1) from words[] preserved in
             normalized_text. Restoration repair on failure.
    check2 — domain terms (>3 chars from slide_context) preserved. Same
             restoration repair on failure.
    check3 — no TIER1_WORDS remain in normalized_text. Re-normalize repair.
    check4 — template-rule consistency (structure_extraction respected).
             Re-normalize repair.

  Repair loop:
    Attempt 1: run normalize() → run checks → if any fail, apply repairs
               by failure type:
                 check1/check2 fail → _repair_restore_words (splice
                   missing words from words[] SSOT, skip TIER1)
                 check3/check4 fail → re-call normalize()
               Mark repaired check_ids as "repaired".
    Attempt 2: same. If still failing, fall through.
    Terminal: result.normalized_text = raw_text (raw STT verbatim).
              validation_checks = all "fail". repair_applied=False.

  Zero LLM calls. Repair is fully deterministic.

The raw_text fallback is the CLINICAL-SAFETY invariant. A drug name or
dosage dropped during normalization must NEVER ship as a silently broken
sentence — MIC ships the raw STT instead so the human reviewer sees the
unedited text and can correct from there.

Phase 7j / parity-4 zero-gap.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.iil.normalization import (
    NormalizedResult,
    TIER1_WORDS,
    _get_domain_terms,
    normalize,
)

logger = logging.getLogger(__name__)


MAX_REPAIR_ATTEMPTS = 2


@dataclass
class CheckResult:
    check_id: str       # "check1" | "check2" | "check3" | "check4"
    status: str         # "pass" | "fail" | "repaired"
    reason: str = ""


# ─── Checks ─────────────────────────────────────────────────────────────────


_CONTENT_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")


def _content_words_from_words(words: list[dict]) -> set[str]:
    """
    Content words from words[] SSOT — alpha-only, length > 3, lowercase,
    excluding TIER1 fillers.
    """
    out: set[str] = set()
    for w in words or []:
        token = (w.get("word") if isinstance(w, dict) else str(w)) or ""
        # Strip punctuation
        stripped = re.sub(r"[^A-Za-z'-]", "", token).lower()
        if len(stripped) > 3 and stripped not in TIER1_WORDS:
            out.add(stripped)
    return out


def _tokens_lower(text: str) -> set[str]:
    return {m.group(0).lower() for m in _CONTENT_WORD_RE.finditer(text or "")}


def _check1_content_words(result: NormalizedResult, words: list[dict]) -> CheckResult:
    """Check 1: content words from words[] preserved in normalized_text."""
    source_content = _content_words_from_words(words)
    if not source_content:
        return CheckResult("check1", "pass", "no content words in source")
    norm_tokens = _tokens_lower(result.normalized_text)
    missing = sorted(w for w in source_content if w not in norm_tokens)
    if missing:
        return CheckResult(
            "check1", "fail",
            f"Content words missing: {missing[:8]}",
        )
    return CheckResult("check1", "pass", "")


def _check2_domain_terms(result: NormalizedResult, slide_context: str) -> CheckResult:
    """Check 2: domain terms (>3 chars from slide_context) preserved."""
    domain = _get_domain_terms(slide_context)
    if not domain:
        return CheckResult("check2", "pass", "no domain terms")
    norm_tokens = _tokens_lower(result.normalized_text)
    raw_tokens = _tokens_lower(result.raw_text or "")
    # Only flag terms that WERE in raw but are NOT in normalized.
    missing = sorted(
        t for t in domain
        if t in raw_tokens and t not in norm_tokens
    )
    if missing:
        return CheckResult(
            "check2", "fail",
            f"Domain terms missing: {missing[:8]}",
        )
    return CheckResult("check2", "pass", "")


def _check3_tier1_removed(result: NormalizedResult) -> CheckResult:
    """Check 3: no TIER1_WORDS remain in normalized_text."""
    tokens = _tokens_lower(result.normalized_text)
    leftover = sorted(t for t in tokens if t in TIER1_WORDS)
    if leftover:
        return CheckResult(
            "check3", "fail",
            f"Tier 1 words still present: {leftover[:8]}",
        )
    return CheckResult("check3", "pass", "")


def _check4_template_rules(
    result: NormalizedResult,
    template_config: dict,
    key_points: list,
) -> CheckResult:
    """
    Check 4: template-rule enforcement.
    If structure_extraction=False, key_points must be empty (or the result
    must not surface them as if extraction was enabled).
    """
    structure = bool((template_config or {}).get("structure_extraction", True))
    if not structure and key_points:
        return CheckResult(
            "check4", "fail",
            f"structure_extraction=False but key_points has {len(key_points)} items",
        )
    return CheckResult("check4", "pass", "")


# ─── Repair: restore words from SSOT ────────────────────────────────────────


def _repair_restore_words(
    result: NormalizedResult,
    words: list[dict],
    raw_text: str,
    slide_context: str,
) -> NormalizedResult:
    """
    CHECK 1/2 repair — restore content words from words[] SSOT that are
    missing from normalized_text. Tier 1 stays removed always (RULE 5).

    Appends restored words to the END of normalized_text (matches MIC).
    """
    from app.iil.normalization import TIER1_WORDS as _T1  # avoid re-bind

    norm_tokens = set(result.normalized_text.lower().split())
    raw_tokens = [
        (w.get("word") if isinstance(w, dict) else str(w)) or ""
        for w in words or []
    ]

    restored: list[str] = []
    for word in raw_tokens:
        if not word:
            continue
        word_lower = word.lower().rstrip(".,?!")
        if word_lower in _T1:
            continue  # Tier 1 stays removed
        if word_lower not in norm_tokens:
            restored.append(word)

    if restored:
        result.normalized_text = (result.normalized_text + " " + " ".join(restored)).strip()

    return result


# ─── Public API ─────────────────────────────────────────────────────────────


def validate_and_repair(
    segment_id: str,
    words: list[dict],
    raw_text: str,
    slide_context: str,
    template_config: dict,
    key_points: Optional[list] = None,
    iil_config: Optional[dict] = None,
) -> NormalizedResult:
    """
    Run normalize() then up to MAX_REPAIR_ATTEMPTS deterministic repairs.

    On terminal failure (still failing after 2 attempts), returns a
    NormalizedResult with `normalized_text = raw_text` and all four checks
    marked "fail". This is the CLINICAL-SAFETY invariant — a broken
    normalization NEVER ships; the human reviewer sees raw STT instead.

    Zero LLM calls.
    """
    key_points = key_points or []

    # Initial normalize.
    result = normalize(
        segment_id=segment_id,
        words=words,
        template_config=template_config or {},
        slide_context=slide_context or "",
        iil_config=iil_config,
    )

    for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
        # Run all 4 checks.
        c1 = _check1_content_words(result, words)
        c2 = _check2_domain_terms(result, slide_context)
        c3 = _check3_tier1_removed(result)
        c4 = _check4_template_rules(result, template_config, key_points)
        checks = [c1, c2, c3, c4]

        if all(c.status == "pass" for c in checks):
            # Success: persist statuses (preserve "repaired" marks from prior attempt).
            for c in checks:
                prev = result.validation_checks.get(c.check_id)
                if prev == "repaired":
                    continue  # keep "repaired" mark — failure was fixed, not absent
                result.validation_checks[c.check_id] = c.status
            return result

        # Apply repairs by failure type.
        any_check12_failed = c1.status == "fail" or c2.status == "fail"
        any_check34_failed = c3.status == "fail" or c4.status == "fail"

        if any_check12_failed:
            result = _repair_restore_words(result, words, raw_text, slide_context)
            if c1.status == "fail":
                result.validation_checks["check1"] = "repaired"
            if c2.status == "fail":
                result.validation_checks["check2"] = "repaired"

        if any_check34_failed:
            result = normalize(
                segment_id=segment_id,
                words=words,
                template_config=template_config or {},
                slide_context=slide_context or "",
                iil_config=iil_config,
            )
            if c3.status == "fail":
                result.validation_checks["check3"] = "repaired"
            if c4.status == "fail":
                result.validation_checks["check4"] = "repaired"

        result.repair_applied = True
        result.repair_attempts = attempt

    # Terminal failure — raw_text fallback (RULE 4, clinical-safety invariant).
    logger.warning(
        f"segment {segment_id}: repair failed after {MAX_REPAIR_ATTEMPTS} attempts — "
        f"using raw_text fallback"
    )
    result.normalized_text = raw_text or ""
    result.repair_applied = False
    result.repair_attempts = MAX_REPAIR_ATTEMPTS
    result.validation_checks = {
        "check1": "fail",
        "check2": "fail",
        "check3": "fail",
        "check4": "fail",
    }
    return result


# ─── Back-compat shim ───────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """
    Legacy shape for any caller that imported the parity-3 numeric-checks
    interface. New code MUST use NormalizedResult.validation_checks.
    """

    passed: bool
    word_count_ratio: float
    token_overlap: float
    filler_remaining: list[str]
    missing_terminology: list[str]
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


def validate(source_text: str, normalized_text: str, filler_words: list[str]) -> ValidationResult:
    """
    Legacy numeric-validator kept for diagnostic endpoints that still call it.
    NOT used by normalize_task — that path uses validate_and_repair above.
    """
    if not source_text or not source_text.strip():
        return ValidationResult(
            passed=True, word_count_ratio=1.0, token_overlap=1.0,
            filler_remaining=[], missing_terminology=[],
        )
    src_words = source_text.split()
    norm_words = normalized_text.split()
    ratio = len(norm_words) / max(1, len(src_words))
    src_tokens = _tokens_lower(source_text)
    norm_tokens = _tokens_lower(normalized_text)
    overlap = len(src_tokens & norm_tokens) / max(1, len(src_tokens)) if src_tokens else 1.0
    lower_norm = normalized_text.lower()
    filler_remaining = []
    for f in filler_words or []:
        if re.search(rf"(?<![A-Za-z]){re.escape(f.lower())}(?![A-Za-z])", lower_norm):
            filler_remaining.append(f)
    passed = (
        0.5 <= ratio <= 1.15
        and overlap >= 0.6
        and not filler_remaining
    )
    return ValidationResult(
        passed=passed,
        word_count_ratio=ratio,
        token_overlap=overlap,
        filler_remaining=filler_remaining,
        missing_terminology=[],
    )
