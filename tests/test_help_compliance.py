"""
Tests for Phase 4 of the Help Center port — CC-Rounds compliance SSOT.

Pins the threshold table to its current values so any unintentional
drift between the backend (app/utils/help_compliance.py) and the
frontend (frontend/src/utils/helpCompliance.ts) is caught at CI.

Plus unit coverage for compute_compliance + is_faq_category against
the Help and FAQ paths, edge cases (empty steps, mid-range summary,
oversized FAQ summary).

Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §9.1
"""
from __future__ import annotations

import pytest


# ─── Threshold pinning (CI guard against drift) ────────────────────────


def test_thresholds_match_audit():
    """Anchor the rounds-specific CC-Rounds thresholds. If any value here
    is changed, the matching constant in
    frontend/src/utils/helpCompliance.ts MUST change in the same commit.
    """
    from app.utils import help_compliance as cc

    expected = {
        "HELP_MIN_STEPS":      3,
        "HELP_MIN_WORDS":      200,
        "HELP_SUMMARY_MIN":    180,
        "HELP_SUMMARY_MAX":    None,
        "FAQ_MIN_STEPS":       2,
        "FAQ_MIN_WORDS":       80,
        "FAQ_SUMMARY_MIN":     60,
        "FAQ_SUMMARY_MAX":     300,
        "WORD_CEILING":        1000,
        "HELP_SUMMARY_TARGET": (180, 400),
        "FAQ_SUMMARY_TARGET":  (120, 280),
    }

    for name, want in expected.items():
        got = getattr(cc, name)
        assert got == want, f"CC-Rounds threshold {name} drifted: expected {want!r}, got {got!r}"


# ─── is_faq_category ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "category, expected",
    [
        ("faq:editor", True),
        ("faq:auth",   True),
        ("FAQ:foo",    True),
        ("page:editor", False),
        ("general",    False),
        ("",           False),
        (None,         False),
        # Edge: substring match — "interface_faq" would match (FAQ is in
        # the lowercased category), but we don't ship such categories.
        ("interface_faq", True),
    ],
)
def test_is_faq_category(category, expected):
    from app.utils.help_compliance import is_faq_category
    assert is_faq_category(category) is expected


# ─── compute_compliance — Help (non-FAQ) ───────────────────────────────


def _help_article(*, summary: str, steps: int) -> dict:
    # "ten words " * 35 = 70 words per step. With 3 steps that's 210
    # words, just over HELP_MIN_WORDS=200.
    return {
        "category": "page:editor",
        "summary": summary,
        "steps": [{"title": f"step {i}", "body": "ten words " * 35} for i in range(steps)],
    }


def test_help_passing_article():
    """Summary >= 180 chars, 3+ steps each >= ~50 words → all OK."""
    from app.utils.help_compliance import compute_compliance
    a = _help_article(summary="x" * 200, steps=3)
    cc = compute_compliance(a)
    assert cc["isFaq"] is False
    assert cc["summaryOk"] is True
    assert cc["wordsOk"] is True
    assert cc["stepsOk"] is True
    assert cc["allPass"] is True
    assert 0 <= cc["pct"] <= 100


def test_help_fails_short_summary():
    from app.utils.help_compliance import compute_compliance
    a = _help_article(summary="x" * 50, steps=3)
    cc = compute_compliance(a)
    assert cc["summaryOk"] is False
    assert cc["allPass"] is False


def test_help_fails_too_few_steps():
    from app.utils.help_compliance import compute_compliance
    a = _help_article(summary="x" * 200, steps=2)
    cc = compute_compliance(a)
    assert cc["stepsOk"] is False
    assert cc["allPass"] is False


def test_help_fails_too_few_words():
    from app.utils.help_compliance import compute_compliance
    a = {
        "category": "page:editor",
        "summary": "x" * 200,
        "steps": [{"title": "s", "body": "one word"} for _ in range(3)],
    }
    cc = compute_compliance(a)
    assert cc["wordsOk"] is False
    assert cc["allPass"] is False


def test_help_no_summary_max_cap():
    """HELP_SUMMARY_MAX is None — a 5000-char summary still passes."""
    from app.utils.help_compliance import compute_compliance
    a = _help_article(summary="x" * 5000, steps=3)
    cc = compute_compliance(a)
    assert cc["summaryOk"] is True


# ─── compute_compliance — FAQ ──────────────────────────────────────────


def _faq_article(*, summary: str, steps: int) -> dict:
    # "ten words " * 25 = 50 words per step. With 2 steps that's 100
    # words, over FAQ_MIN_WORDS=80.
    return {
        "category": "faq:auth",
        "summary": summary,
        "steps": [{"title": f"s{i}", "body": "ten words " * 25} for i in range(steps)],
    }


def test_faq_passing_article():
    from app.utils.help_compliance import compute_compliance
    a = _faq_article(summary="x" * 100, steps=2)
    cc = compute_compliance(a)
    assert cc["isFaq"] is True
    assert cc["summaryOk"] is True
    assert cc["wordsOk"] is True
    assert cc["stepsOk"] is True
    assert cc["allPass"] is True


def test_faq_fails_summary_too_long():
    """FAQ has a max of 300; 500-char summary fails."""
    from app.utils.help_compliance import compute_compliance
    a = _faq_article(summary="x" * 500, steps=2)
    cc = compute_compliance(a)
    assert cc["summaryOk"] is False
    assert cc["allPass"] is False


def test_faq_passes_minimum_summary():
    """Exactly at FAQ_SUMMARY_MIN (60) passes."""
    from app.utils.help_compliance import compute_compliance
    a = _faq_article(summary="x" * 60, steps=2)
    cc = compute_compliance(a)
    assert cc["summaryOk"] is True


def test_faq_fails_below_summary_min():
    from app.utils.help_compliance import compute_compliance
    a = _faq_article(summary="x" * 50, steps=2)
    cc = compute_compliance(a)
    assert cc["summaryOk"] is False


# ─── Edge cases ──────────────────────────────────────────────────────


def test_empty_article():
    """Nothing populated → everything fails (sane defaults)."""
    from app.utils.help_compliance import compute_compliance
    cc = compute_compliance({"category": "general", "summary": "", "steps": []})
    assert cc["wordsOk"] is False
    assert cc["summaryOk"] is False
    assert cc["stepsOk"] is False
    assert cc["allPass"] is False
    assert cc["pct"] == 0


def test_compute_compliance_handles_pydantic_like_steps():
    """Steps may arrive as Pydantic models — duck-typed via .body access."""
    from app.utils.help_compliance import compute_compliance

    class StepLike:
        def __init__(self, title: str, body: str) -> None:
            self.title = title
            self.body = body

    article = {
        "category": "page:editor",
        "summary": "x" * 200,
        "steps": [StepLike(title=f"s{i}", body="ten words " * 35) for i in range(3)],
    }
    cc = compute_compliance(article)
    assert cc["stepCount"] == 3
    assert cc["wordsOk"] is True


def test_pct_saturates_at_word_ceiling():
    from app.utils.help_compliance import compute_compliance, WORD_CEILING
    huge = "word " * (WORD_CEILING * 5)
    article = {
        "category": "page:editor",
        "summary": "x" * 200,
        "steps": [{"title": "s", "body": huge}],
    }
    cc = compute_compliance(article)
    assert cc["pct"] == 100
