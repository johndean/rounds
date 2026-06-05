"""
Tests for the small pure-function helpers in app/tasks/sop_tasks.py:
``_html_to_text``, ``_mask_email``, ``_deadline_lock_key``.

These are isolated from the Celery task / DB layer and run as pure
function tests — no DB fixture required.

Phase 7.4 (2026-06-05) added this file alongside the regression fix
for ``_html_to_text`` failing to decode ``&#x27;`` (apostrophe in hex
form, which ``html.escape(..., quote=True)`` emits).
"""
import hashlib

import pytest

from app.tasks.sop_tasks import _deadline_lock_key, _html_to_text, _mask_email


class TestHtmlToText:
    """Crude HTML to plain-text helper used for the email plain-text
    alternative part."""

    def test_empty_input_returns_empty(self):
        assert _html_to_text("") == ""
        assert _html_to_text(None) == ""  # type: ignore[arg-type]

    def test_strips_simple_tags(self):
        assert _html_to_text("<p>Hello</p>") == "Hello"
        assert _html_to_text("<strong>bold</strong>") == "bold"

    def test_br_becomes_newline(self):
        assert "\n" in _html_to_text("Line 1<br>Line 2")
        assert "\n" in _html_to_text("Line 1<br/>Line 2")
        assert "\n" in _html_to_text("Line 1<BR>Line 2")

    def test_decodes_apostrophe_from_hex_form(self):
        """REGRESSION: html.escape(s, quote=True) emits &#x27; for
        apostrophes — NOT &#39; (the decimal form). The pre-Phase-7.4
        decode chain only handled &#39; and corrupted every deadline
        email whose session_title contained an apostrophe (e.g.
        "ACVIM's Forum" rendered as "ACVIM&#x27;s Forum" in text)."""
        assert _html_to_text("<p>ACVIM&#x27;s Forum</p>") == "ACVIM's Forum"
        assert _html_to_text("<p>Don&#x27;t miss</p>") == "Don't miss"

    def test_decodes_apostrophe_from_decimal_form(self):
        """Belt-and-suspenders: both numeric forms decode now via
        html.unescape, so older templates that used &#39; still work."""
        assert _html_to_text("<p>ACVIM&#39;s Forum</p>") == "ACVIM's Forum"

    def test_decodes_named_entities(self):
        assert _html_to_text("&amp;") == "&"
        assert _html_to_text("&lt;tag&gt;") == "<tag>"
        assert _html_to_text("&quot;quoted&quot;") == '"quoted"'
        assert _html_to_text("&nbsp;") == ""  # whitespace collapses

    def test_decodes_extended_entities_now_handled_by_html_unescape(self):
        """Phase 7.4 switched to html.unescape, which handles named
        entities like &mdash; / &rsquo; / &hellip; / &rarr; that the
        previous 6-entity regex chain did not."""
        assert _html_to_text("VIN&mdash;Rounds") == "VIN—Rounds"
        assert _html_to_text("It&rsquo;s here") == "It’s here"
        assert _html_to_text("Open session&rarr;") == "Open session→"

    def test_collapses_extra_whitespace(self):
        result = _html_to_text("<p>Hello</p>\n\n\n\n<p>World</p>")
        assert "\n\n\n" not in result  # 3+ blank lines collapse to 2

    def test_strips_attributes(self):
        result = _html_to_text('<a href="https://example.com" class="x">link</a>')
        assert result == "link"
        assert "href" not in result

    def test_seed_template_body_renders_to_clean_text(self):
        # Smoke test against the migration 051 overdue-template shape.
        html_body = (
            "<p>Hi Jane,</p>"
            "<p>Session <strong>ACVIM&#x27;s Forum</strong> (SS-123) is "
            "<strong>5.0h past SLA</strong>.</p>"
            "<p><a href='https://rounds.vin/#/e/abc/sop'>Open session &rarr;</a></p>"
        )
        text = _html_to_text(html_body)
        assert "ACVIM's Forum" in text
        assert "&#x27;" not in text
        assert "&rarr;" not in text
        assert "→" in text  # decoded arrow


class TestMaskEmail:
    """Email recipient masking for audit_events.summary (privacy)."""

    def test_long_local_part_masks_middle(self):
        assert _mask_email("jane.doe@vin.com") == "jan***@vin.com"

    def test_short_local_part_masks_entirely(self):
        assert _mask_email("ab@vin.com") == "***@vin.com"
        assert _mask_email("a@vin.com") == "***@vin.com"
        # Exactly 3 chars is still fully masked
        assert _mask_email("abc@vin.com") == "***@vin.com"

    def test_invalid_email_returns_sentinel(self):
        assert _mask_email("") == "***"
        assert _mask_email("not-an-email") == "***"

    def test_domain_preserved_verbatim(self):
        # Operators can still see WHICH domain the email goes to even
        # though the local-part is masked.
        assert _mask_email("very.long.name@some.domain.example") == \
            "ver***@some.domain.example"


class TestDeadlineLockKey:
    """Postgres advisory-lock key derivation for the deadline-email
    throttle. Must be deterministic across worker processes (Python's
    built-in hash() is per-process randomized and can't be used)."""

    def test_deterministic_same_input_same_key(self):
        k1 = _deadline_lock_key("abc-def", "prep")
        k2 = _deadline_lock_key("abc-def", "prep")
        assert k1 == k2

    def test_different_session_different_key(self):
        k1 = _deadline_lock_key("session-a", "prep")
        k2 = _deadline_lock_key("session-b", "prep")
        assert k1 != k2

    def test_different_stage_different_key(self):
        k1 = _deadline_lock_key("session-a", "prep")
        k2 = _deadline_lock_key("session-a", "medical")
        assert k1 != k2

    def test_key_fits_postgres_bigint_positive_range(self):
        # pg_advisory_xact_lock takes a bigint (signed 64-bit). Negative
        # values are allowed but we mask to positive for predictability.
        k = _deadline_lock_key("abc", "prep")
        assert 0 <= k <= 0x7FFFFFFFFFFFFFFF

    def test_matches_documented_algorithm(self):
        # Pin the specific algorithm so changing it requires updating
        # both this test and the docstring. Future migrations of the
        # lock key derivation must remain deterministic across
        # codebase versions or in-flight throttle records misalign.
        session_id = "test-session"
        stage = "prep"
        expected_h = hashlib.md5(f"{session_id}::{stage}".encode("utf-8")).digest()
        expected = int.from_bytes(expected_h[:8], "big") & 0x7FFFFFFFFFFFFFFF
        assert _deadline_lock_key(session_id, stage) == expected
