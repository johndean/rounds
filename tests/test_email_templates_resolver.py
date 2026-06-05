"""
Tests for sync resolver helpers in app/api/email_templates.py.

Covers ``substitute_variables`` (pure function — DB-free) and the
behavior contract of ``resolve_template_sync`` shape (DB tests deferred
until a sync test connection fixture lands; the SQL is structurally
identical to the async route which is exercised elsewhere).

Phase 7.1 (2026-06-04). Helper exists; not yet adopted by
_maybe_send_deadline_email — see Phase 7.2.
"""
import pytest

from app.api.email_templates import substitute_variables, substitute_variables_text


class TestSubstituteVariables:
    """Pure-function substitution of `{{ var }}` placeholders."""

    def test_simple_substitution(self):
        assert substitute_variables(
            "Hello {{ name }}", {"name": "World"}
        ) == "Hello World"

    def test_multiple_substitutions(self):
        assert substitute_variables(
            "{{ a }} {{ b }} {{ c }}",
            {"a": "1", "b": "2", "c": "3"},
        ) == "1 2 3"

    def test_repeated_variable(self):
        assert substitute_variables(
            "{{ x }} and {{ x }} again", {"x": "Y"}
        ) == "Y and Y again"

    def test_no_whitespace_in_braces(self):
        assert substitute_variables(
            "Hello {{name}}", {"name": "World"}
        ) == "Hello World"

    def test_extra_whitespace_in_braces(self):
        assert substitute_variables(
            "Hello {{  name  }}", {"name": "World"}
        ) == "Hello World"

    def test_missing_variable_becomes_empty_string(self):
        # Important: should NOT raise — partial dicts must be safe.
        assert substitute_variables(
            "Hello {{ name }}", {}
        ) == "Hello "

    def test_none_variable_becomes_empty_string(self):
        assert substitute_variables(
            "Hello {{ name }}", {"name": None}
        ) == "Hello "

    def test_no_placeholders_returns_unchanged(self):
        assert substitute_variables(
            "no placeholders here", {"name": "ignored"}
        ) == "no placeholders here"

    def test_empty_string_returns_empty(self):
        assert substitute_variables("", {"a": "b"}) == ""

    def test_none_template_returns_empty(self):
        assert substitute_variables(None, {"a": "b"}) == ""  # type: ignore[arg-type]

    def test_integer_value_coerces_to_string(self):
        assert substitute_variables(
            "Count: {{ n }}", {"n": 42}
        ) == "Count: 42"

    def test_float_value_coerces_to_string(self):
        assert substitute_variables(
            "Hours: {{ h }}", {"h": 1.5}
        ) == "Hours: 1.5"

    def test_substituted_values_are_html_escaped(self):
        # Substituted values are HTML-escaped to block XSS via
        # operator-controlled inputs (session title, code, etc.).
        # Replaces the pre-2026-06-05 "does not escape" pin.
        assert substitute_variables(
            "<p>Hi {{ name }}</p>", {"name": "<b>bold</b>"}
        ) == "<p>Hi &lt;b&gt;bold&lt;/b&gt;</p>"

    def test_html_escape_blocks_attribute_breakout_xss(self):
        # quote=True escapes both " and ' so values are safe inside
        # href="..." OR href='...' attributes.
        result = substitute_variables(
            '<a href="{{ url }}">link</a>',
            {"url": 'evil" onclick="alert(1)'},
        )
        assert result == '<a href="evil&quot; onclick=&quot;alert(1)">link</a>'

    def test_html_escape_blocks_tag_breakout_xss(self):
        # The classic "title contains </strong><script>" payload from
        # the Phase 7.2 verification finding (HIGH severity).
        result = substitute_variables(
            "<p>Session: <strong>{{ title }}</strong></p>",
            {"title": '</strong><a href="https://phish.example">Click</a><strong>'},
        )
        assert "<a href=" not in result
        assert "&lt;a href=" in result
        assert result == (
            "<p>Session: <strong>"
            "&lt;/strong&gt;&lt;a href=&quot;https://phish.example&quot;&gt;Click&lt;/a&gt;&lt;strong&gt;"
            "</strong></p>"
        )

    def test_template_markup_itself_is_not_escaped(self):
        # The template's surrounding HTML is preserved as-is — only the
        # variable VALUES are escaped. Confirms migration-048/051 seed
        # bodies render correctly.
        template = '<p style="color:red">Stage <strong>{{ stage }}</strong> overdue</p>'
        assert substitute_variables(template, {"stage": "prep"}) == (
            '<p style="color:red">Stage <strong>prep</strong> overdue</p>'
        )


class TestSubstituteVariablesText:
    """Phase 7.4 — the no-escape variant for plain-text contexts
    (email Subject headers, log lines). Adding it fixed the
    regression where ``substitute_variables`` was being applied to
    subjects and apostrophes in session titles came out as ``&#x27;``."""

    def test_no_html_escape_in_text_variant(self):
        # The HTML variant would emit `&#x27;` for the apostrophe;
        # the text variant must pass it through verbatim.
        assert substitute_variables_text(
            "Hello {{ name }}", {"name": "ACVIM's Forum"}
        ) == "Hello ACVIM's Forum"

    def test_text_variant_preserves_angle_brackets(self):
        # No escape: < and > stay as-is. Caller is responsible for
        # NOT routing this output into an HTML context.
        assert substitute_variables_text(
            "Subject: {{ s }}", {"s": "<top>"}
        ) == "Subject: <top>"

    def test_text_variant_missing_key_is_empty_string(self):
        # Same null-handling as the HTML variant.
        assert substitute_variables_text(
            "Hello {{ name }}!", {}
        ) == "Hello !"

    def test_text_variant_seed_subject_shape(self):
        # Smoke test against the real seed-template subject pattern
        # from migration 048 / 051 — substitute_variables_text is what
        # the SOP deadline task now applies to subject lines.
        subject = "[VIN] OVERDUE: prep — {{ session_code }} ({{ overdue_hours }}h past SLA)"
        out = substitute_variables_text(subject, {
            "session_code":  "SS-123",
            "overdue_hours": "5.0",
        })
        assert out == "[VIN] OVERDUE: prep — SS-123 (5.0h past SLA)"

    def test_text_variant_does_not_corrupt_apostrophe_session_title(self):
        # The regression that motivated this variant: a session title
        # containing an apostrophe (e.g. "ACVIM's Forum") must reach
        # the recipient's inbox as written, not as "ACVIM&#x27;s".
        assert substitute_variables_text(
            "[VIN] {{ title }} overdue",
            {"title": "ACVIM's Forum"},
        ) == "[VIN] ACVIM's Forum overdue"

    def test_seed_template_subject_shape(self):
        # Smoke test against the actual seed template shape from
        # migration 048: '[VIN] Ready for prep — {{ session_code }}'
        subject = "[VIN] Ready for prep — {{ session_code }}"
        assert substitute_variables(subject, {"session_code": "SS-123"}) \
            == "[VIN] Ready for prep — SS-123"

    def test_unrelated_braces_left_alone(self):
        # CSS / style attributes use { } too — only {{ }} substitutes.
        assert substitute_variables(
            "style='{ font-weight: bold; }' name={{ name }}",
            {"name": "X"},
        ) == "style='{ font-weight: bold; }' name=X"

    def test_underscore_in_variable_name(self):
        # Seed templates use {{ assignee_first_name }} — underscores must work.
        assert substitute_variables(
            "Hi {{ assignee_first_name }}",
            {"assignee_first_name": "Jane"},
        ) == "Hi Jane"


class TestSyncResolverContract:
    """Documents the resolve_template_sync contract.

    DB integration tests are deferred to a sync test fixture; the SQL
    paths in resolve_template_sync are structurally identical to the
    async resolve_template route which is exercised by the
    EmailBuilder.vue UI and the future stage-transition Celery hook."""

    def test_resolver_returns_none_on_missing_stage(self, monkeypatch):
        # The sync resolver MUST return None (not raise) when no row
        # exists. This is the key behavioral diff from the async route
        # — it lets Celery callers gracefully fall back.
        from app.api.email_templates import resolve_template_sync

        class _StubConn:
            def execute(self, *_a, **_kw):
                class _Result:
                    def mappings(self):
                        class _M:
                            def first(self_inner):
                                return None
                        return _M()
                return _Result()

        result = resolve_template_sync(
            _StubConn(),
            session_type_id=None,
            stage_id="nonexistent_stage",
        )
        assert result is None
