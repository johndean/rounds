"""
app/utils/help_compliance.py — CC-Rounds compliance SSOT (backend).

Phase 4 of the Help Center port (plan 2026-06-05-009 §9.1). MIRROR of
frontend src/utils/helpCompliance.ts. The two files MUST stay byte-
identical on threshold values — tests/test_help_compliance.py pins
both sides to a hardcoded expected table; drift fails CI.

"CC-Rounds" thresholds are intentionally LOOSER than MIC's CC5.2:

  | Threshold        | Help (rounds) | FAQ (rounds) | MIC CC5.2  |
  | ---------------- | ------------- | ------------ | ---------- |
  | MIN_STEPS        | 3             | 2            | 5 / 3      |
  | MIN_WORDS        | 200           | 80           | 300 / 150  |
  | SUMMARY_MIN      | 180           | 60           | 351 / 100  |
  | SUMMARY_MAX      | none          | 300          | none / 400 |
  | WORD_CEILING     | 1000          | 1000         | 1500       |
  | SUMMARY_TARGET   | (180, 400)    | (120, 280)   | (351, 600) |

Rationale: rounds starts with ~70 seed articles + 10 FAQs (vs MIC's 53
hand-tuned articles), so the floor needs to be lower so existing
content publishes without artificial padding. We tighten thresholds in
a follow-up after the corpus stabilizes (per plan §9.1).

A single predicate `is_faq_category()` drives all type logic. The
function checks the literal substring "faq" in the lower-cased
category, matching the seed-data category prefix `faq:*`. Changing the
predicate without coordinating the migration seed + frontend mirror
breaks the routing logic.

Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md ยง9.1
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


# ── Thresholds (LOCKED) ───────────────────────────────────────────────
HELP_MIN_STEPS = 3
HELP_MIN_WORDS = 200
HELP_SUMMARY_MIN = 180
HELP_SUMMARY_MAX: Optional[int] = None  # no max for Help

FAQ_MIN_STEPS = 2
FAQ_MIN_WORDS = 80
FAQ_SUMMARY_MIN = 60
FAQ_SUMMARY_MAX = 300

WORD_CEILING = 1000  # for the percent-progress meter (saturates here)

# Target ranges used by the Fix-CC-Rounds bulk AI rewrite to tell Gemini
# where to land. The min must be >= SUMMARY_MIN; the max should be ~2.2x
# SUMMARY_MIN so the rewrite has room to breathe without ballooning.
HELP_SUMMARY_TARGET = (180, 400)
FAQ_SUMMARY_TARGET = (120, 280)


def is_faq_category(category: Optional[str]) -> bool:
    """SSOT predicate for FAQ vs Help routing.

    Frontend mirror: see ``isFaqCategory`` in ``frontend/src/utils/helpCompliance.ts``.
    """
    return "faq" in (category or "").lower()


class ComplianceResult(TypedDict):
    """Shape returned by ``compute_compliance``."""
    isFaq:      bool
    wordCount:  int
    summaryLen: int
    stepCount:  int
    wordsOk:    bool
    summaryOk:  bool
    stepsOk:    bool
    allPass:    bool
    pct:        int


def compute_compliance(article: Any) -> ComplianceResult:
    """Pure function — no side effects.

    Accepts either a dict (e.g. from the row serializer in app/api/help.py)
    or an object with attributes (HelpArticle ORM, Pydantic, etc.). Steps
    may be Pydantic models, dicts, or strings.

    Mirror of ``computeCompliance`` in
    ``frontend/src/utils/helpCompliance.ts``.
    """

    def _get(key: str, default: Any = None) -> Any:
        if isinstance(article, dict):
            return article.get(key, default)
        return getattr(article, key, default)

    category = _get("category", "") or ""
    summary = _get("summary", "") or ""
    steps = _get("steps", []) or []

    word_count = 0
    for s in steps:
        if hasattr(s, "body"):
            body = s.body
        elif isinstance(s, dict):
            body = s.get("body", "")
        else:
            body = ""
        word_count += len([w for w in (body or "").split() if w])

    step_count = len(steps)
    summary_len = len(summary)
    is_faq = is_faq_category(category)

    if is_faq:
        words_ok = word_count >= FAQ_MIN_WORDS
        summary_ok = FAQ_SUMMARY_MIN <= summary_len <= FAQ_SUMMARY_MAX
        steps_ok = step_count >= FAQ_MIN_STEPS
    else:
        words_ok = word_count >= HELP_MIN_WORDS
        if HELP_SUMMARY_MAX is None:
            summary_ok = summary_len >= HELP_SUMMARY_MIN
        else:
            summary_ok = HELP_SUMMARY_MIN <= summary_len <= HELP_SUMMARY_MAX
        steps_ok = step_count >= HELP_MIN_STEPS

    all_pass = words_ok and summary_ok and steps_ok
    pct = min(100, round((word_count / WORD_CEILING) * 100))

    return {
        "isFaq":      is_faq,
        "wordCount":  word_count,
        "summaryLen": summary_len,
        "stepCount":  step_count,
        "wordsOk":    words_ok,
        "summaryOk":  summary_ok,
        "stepsOk":    steps_ok,
        "allPass":    all_pass,
        "pct":        pct,
    }
