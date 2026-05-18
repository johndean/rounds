"""
Validate-and-repair loop — MIC verbatim contract.

Phase 7j zero-gap parity: validates the deterministic 2-attempt repair
loop with raw_text fallback. The fallback is the clinical-safety
invariant — broken normalizations must NEVER ship; the human reviewer
sees raw STT instead.
"""
from __future__ import annotations

from unittest.mock import patch

from app.iil.normalization import NormalizedResult
from app.iil.validation import (
    MAX_REPAIR_ATTEMPTS,
    _check1_content_words,
    _check3_tier1_removed,
    _repair_restore_words,
    validate_and_repair,
)


def _words(*tokens: str) -> list[dict]:
    """Helper — build a words list of {word, start_time, end_time} dicts."""
    return [
        {"word": t, "start_time": float(i), "end_time": float(i) + 0.5, "confidence": 0.95}
        for i, t in enumerate(tokens)
    ]


def _template() -> dict:
    return {
        "filler_policy":        "strict",
        "structure_extraction": True,
        "key_points":           False,
        "tone":                 "professional",
        "terminology":          "veterinary",
        "rewrite":              "light",
    }


def _iil_cfg() -> dict:
    return {"enabled": True, "tier1": True, "tier2": True, "tier3": True}


# ─── Check functions in isolation ───────────────────────────────────────────


def test_check1_passes_when_content_words_preserved():
    result = NormalizedResult(
        segment_id="seg1",
        raw_text="Give meloxicam fifteen milligrams",
        normalized_text="Give meloxicam fifteen milligrams",
        filler_count=0,
        compression_ratio=1.0,
    )
    words = _words("Give", "meloxicam", "fifteen", "milligrams")
    res = _check1_content_words(result, words)
    assert res.status == "pass"


def test_check1_fails_when_drug_name_dropped():
    """Drug name silently dropped — the clinically-critical failure mode."""
    result = NormalizedResult(
        segment_id="seg1",
        raw_text="Give meloxicam fifteen milligrams",
        normalized_text="Give fifteen milligrams",  # meloxicam dropped
        filler_count=0,
        compression_ratio=0.75,
    )
    words = _words("Give", "meloxicam", "fifteen", "milligrams")
    res = _check1_content_words(result, words)
    assert res.status == "fail"
    assert "meloxicam" in res.reason


def test_check3_fails_when_tier1_remains():
    result = NormalizedResult(
        segment_id="seg1",
        raw_text="um, give meloxicam",
        normalized_text="um give meloxicam",  # leftover um
        filler_count=0,
        compression_ratio=1.0,
    )
    res = _check3_tier1_removed(result)
    assert res.status == "fail"
    assert "um" in res.reason


def test_check3_passes_when_clean():
    result = NormalizedResult(
        segment_id="seg1",
        raw_text="um, give meloxicam",
        normalized_text="give meloxicam",
        filler_count=1,
        compression_ratio=0.7,
    )
    res = _check3_tier1_removed(result)
    assert res.status == "pass"


# ─── Repair-restore-words ───────────────────────────────────────────────────


def test_repair_restore_appends_missing_drug_name():
    """Restore meloxicam back into the normalized text from words[] SSOT."""
    result = NormalizedResult(
        segment_id="seg1",
        raw_text="give meloxicam fifteen mg",
        normalized_text="give fifteen mg",  # meloxicam dropped
        filler_count=0,
        compression_ratio=0.75,
    )
    words = _words("give", "meloxicam", "fifteen", "mg")
    repaired = _repair_restore_words(result, words, "give meloxicam fifteen mg", "")
    assert "meloxicam" in repaired.normalized_text.lower()


def test_repair_restore_skips_tier1():
    """Tier 1 fillers stay removed even on repair."""
    result = NormalizedResult(
        segment_id="seg1",
        raw_text="um give meloxicam",
        normalized_text="give meloxicam",  # tier1 stripped, no content lost
        filler_count=1,
        compression_ratio=0.75,
    )
    words = _words("um", "give", "meloxicam")
    repaired = _repair_restore_words(result, words, "um give meloxicam", "")
    # um stays removed — _repair_restore_words skips TIER1_WORDS
    assert "um" not in repaired.normalized_text.lower().split()


# ─── End-to-end validate_and_repair ─────────────────────────────────────────


def test_terminal_failure_falls_back_to_raw_text():
    """
    Clinical-safety invariant: if 2 repair attempts can't make the checks
    pass, normalized_text reverts to raw_text (raw STT verbatim).

    Use a normalize() mock that always leaves a TIER1 filler in place
    AND drops the same content word — so check1 + check3 both keep failing
    even after _repair_restore_words runs (since check3 isn't fixed by
    restore-words, and the re-normalize keeps returning the same broken
    output).
    """
    raw = "um Give the patient meloxicam every twelve hours."

    # Normalize keeps the "um" filler AND drops "meloxicam" every time —
    # neither repair can rescue this:
    #   • _repair_restore_words appends meloxicam (fixes check1)
    #   • re-normalize keeps "um" (check3 stays failing)
    # On the SECOND attempt, check3 still fails → fall through to terminal.
    def _broken_normalize(**kwargs):
        return NormalizedResult(
            segment_id=kwargs["segment_id"],
            raw_text=raw,
            normalized_text="um patient every twelve hours.",
            filler_count=0,
            compression_ratio=0.7,
        )

    with patch("app.iil.validation.normalize", side_effect=_broken_normalize):
        nr = validate_and_repair(
            segment_id="seg1",
            words=_words("um", "Give", "patient", "meloxicam", "every", "twelve", "hours"),
            raw_text=raw,
            slide_context="",
            template_config=_template(),
            iil_config=_iil_cfg(),
        )

    assert nr.normalized_text == raw, "terminal failure must fall back to raw_text"
    assert nr.repair_attempts == MAX_REPAIR_ATTEMPTS == 2
    assert nr.repair_applied is False
    assert nr.validation_checks == {
        "check1": "fail",
        "check2": "fail",
        "check3": "fail",
        "check4": "fail",
    }


def test_clean_segment_passes_first_attempt():
    """All four checks pass first time → no repair needed."""

    def _good_normalize(**kwargs):
        return NormalizedResult(
            segment_id=kwargs["segment_id"],
            raw_text="Give patient fifteen milligrams meloxicam every twelve hours.",
            normalized_text="Give patient fifteen milligrams meloxicam every twelve hours.",
            filler_count=0,
            compression_ratio=1.0,
        )

    with patch("app.iil.validation.normalize", side_effect=_good_normalize):
        nr = validate_and_repair(
            segment_id="seg1",
            words=_words("Give", "patient", "fifteen", "milligrams", "meloxicam", "every", "twelve", "hours"),
            raw_text="Give patient fifteen milligrams meloxicam every twelve hours.",
            slide_context="meloxicam dosage NSAID",
            template_config=_template(),
            iil_config=_iil_cfg(),
        )

    assert nr.repair_attempts == 0
    assert nr.repair_applied is False
    assert all(s == "pass" for s in nr.validation_checks.values())


def test_check1_repair_succeeds_on_first_attempt():
    """check1 fails first time → _repair_restore_words adds missing words → repaired."""

    call_count = {"n": 0}

    def _first_broken_then_passes(**kwargs):
        # We only re-normalize on check3/check4 failures. check1 failure goes
        # through _repair_restore_words which mutates the result in place,
        # so normalize() should only be called once.
        call_count["n"] += 1
        return NormalizedResult(
            segment_id=kwargs["segment_id"],
            raw_text="Give meloxicam",
            normalized_text="Give",  # meloxicam dropped first time
            filler_count=0,
            compression_ratio=0.5,
        )

    with patch("app.iil.validation.normalize", side_effect=_first_broken_then_passes):
        nr = validate_and_repair(
            segment_id="seg1",
            words=_words("Give", "meloxicam"),
            raw_text="Give meloxicam",
            slide_context="",
            template_config=_template(),
            iil_config=_iil_cfg(),
        )

    # After _repair_restore_words appends meloxicam, the 2nd check pass
    # should succeed.
    assert nr.validation_checks.get("check1") == "repaired"
    assert "meloxicam" in nr.normalized_text.lower()
    # normalize() called once (initial); repair did NOT re-normalize since
    # check1 fix goes through _repair_restore_words.
    assert call_count["n"] == 1


def test_zero_llm_calls():
    """validate_and_repair makes ZERO LLM calls (deterministic by design)."""
    # If any code path tried to import llm_client, this would surface.
    # We assert via observation: nothing in validation.py imports llm_client.
    import app.iil.validation as v
    src = open(v.__file__, encoding="utf-8").read()
    assert "llm_client" not in src
    assert "call_gemini" not in src
    assert "call_vertex" not in src
