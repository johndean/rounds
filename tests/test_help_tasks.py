"""
Tests for Phase 4 of the Help Center port — bulk-AI Celery tasks.

The Celery tasks (fix_help_summaries_task, expand_help_steps_task,
expand_faq_steps_task) hit a real Postgres + a real Gemini in
production. These tests cover the route-mount + auth-gate + admin-gate
plumbing and unit-test the small JSON-parse helper. End-to-end task
runs are exercised in staging.

Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §9.2
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app
    return TestClient(app)


# ─── Phase 4 endpoint registration smoke ───────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/v1/help/admin/bulk-publish",
        "/v1/help/admin/fix-summaries",
        "/v1/help/admin/expand-steps",
        "/v1/help/admin/expand-faqs",
        "/v1/help/admin/generate-faq-corpus",  # Phase 5
    ],
)
def test_phase4_admin_routes_registered_and_auth_gated(path):
    """Without a bearer token, every Phase 4/5 admin route returns 401 —
    proving it's mounted under the auth-gated router. 404 would mean the
    route is missing entirely."""
    client = _client()
    resp = client.post(path)
    assert resp.status_code == 401, f"POST {path} -> {resp.status_code}"


# ─── JSON-parse helper isolation ───────────────────────────────────────


def test_parse_json_response_plain():
    from app.tasks.help_tasks import _parse_json_response
    out = _parse_json_response('{"summary": "hello"}')
    assert out == {"summary": "hello"}


def test_parse_json_response_with_code_fences():
    """LLMs sometimes wrap JSON in ```json ... ``` fences; the parser
    strips them gracefully."""
    from app.tasks.help_tasks import _parse_json_response
    out = _parse_json_response('```json\n{"summary": "hello"}\n```')
    assert out == {"summary": "hello"}


def test_parse_json_response_with_bare_fences():
    from app.tasks.help_tasks import _parse_json_response
    out = _parse_json_response('```\n{"summary": "hello"}\n```')
    assert out == {"summary": "hello"}


def test_parse_json_response_returns_none_on_garbage():
    from app.tasks.help_tasks import _parse_json_response
    assert _parse_json_response("not json at all") is None


# ─── Row → dict serializer (internal, mirrors app/api/help.py) ─────────


def test_row_to_dict_handles_null_jsonb():
    from app.tasks.help_tasks import _row_to_dict
    fake = {
        "id": "00000000-0000-0000-0000-000000000000",
        "slug": "x",
        "title": "x",
        "summary": "",
        "category": "general",
        "audience": "users",
        "feature_tags": None,
        "steps": None,
        "related_article_ids": None,
        "display_order": 0,
        "is_published": False,
        "content_domain": "general",
        "workflow_slug": None,
        "version": 1,
        "last_edited_by": "",
        "created_at": None,
        "updated_at": None,
    }
    out = _row_to_dict(fake)
    assert out["feature_tags"] == []
    assert out["steps"] == []
    assert out["related_article_ids"] == []


# ─── Task registration with Celery ─────────────────────────────────────


def test_celery_help_tasks_registered():
    """All four tasks should be picked up by celery_app.conf.include
    via the 'app.tasks.help_tasks' entry."""
    from app.tasks.celery_app import celery_app
    # Importing app.tasks.help_tasks triggers @celery_app.task decorators.
    import app.tasks.help_tasks  # noqa: F401

    names = set(celery_app.tasks.keys())
    assert "rounds.tasks.help.fix_summaries" in names
    assert "rounds.tasks.help.expand_steps" in names
    assert "rounds.tasks.help.expand_faqs" in names
    assert "rounds.tasks.help.generate_faq_corpus" in names


# ─── Phase 5 — generate_faq_corpus dev-speak filter + route table ──────


def test_contains_devspeak_catches_vue_component_name():
    from app.tasks.help_tasks import _contains_devspeak
    assert _contains_devspeak("Open the SpeakerEditPanel on the right") == "SpeakerEditPanel"


def test_contains_devspeak_catches_db_term():
    from app.tasks.help_tasks import _contains_devspeak
    assert _contains_devspeak("The correction ledger logs every edit") == "correction ledger"


def test_contains_devspeak_catches_http_route():
    from app.tasks.help_tasks import _contains_devspeak
    found = _contains_devspeak("Call GET /v1/sessions/abc to fetch")
    assert found is not None
    assert "/v1/" in found


def test_contains_devspeak_catches_framework_name():
    from app.tasks.help_tasks import _contains_devspeak
    assert _contains_devspeak("The FastAPI route validates") == "FastAPI"


def test_contains_devspeak_catches_phase_marker():
    """Phase markers are caught via regex `\\bphase\\s*\\d` — the match
    is the prefix 'Phase 9' (the regex stops at the first digit), not
    the full '9.5' version string. Either is sufficient for rejection."""
    from app.tasks.help_tasks import _contains_devspeak
    found = _contains_devspeak("Phase 9.5 introduced spellcheck")
    assert found is not None
    assert "phase 9" in found.lower()


def test_contains_devspeak_catches_arbitrary_phase_number():
    """Regex catches any phase marker, not just the two literal strings
    that were in the original blacklist."""
    from app.tasks.help_tasks import _contains_devspeak
    for raw in ("Phase 1 work", "Phase 4 of the port", "phase 12 cleanup"):
        assert _contains_devspeak(raw) is not None, f"{raw!r} should be flagged"


def test_contains_devspeak_catches_paraphrased_dev_terms():
    """Hardened 2026-06-05: the blacklist now catches the spaced /
    paraphrased forms an LLM realistically emits, not just the literal
    snake_case identifiers."""
    from app.tasks.help_tasks import _contains_devspeak
    paraphrases = [
        "Open the speaker edit panel",       # was: SpeakerEditPanel
        "Check the audit events table",       # was: audit_events
        "Open the help articles table",       # was: help_articles
        "The background worker runs at 60s",  # generic celery synonym
    ]
    for p in paraphrases:
        assert _contains_devspeak(p) is not None, f"missed paraphrase: {p!r}"


def test_contains_devspeak_catches_dotvue_reference():
    """Regex catches any FooBar.vue mention."""
    from app.tasks.help_tasks import _contains_devspeak
    assert _contains_devspeak("Edit HelpFaqAccordion.vue to add a chip") is not None


def test_contains_devspeak_catches_env_var_pattern():
    """Regex catches SCREAMING_SNAKE env-var-like identifiers."""
    from app.tasks.help_tasks import _contains_devspeak
    assert _contains_devspeak("Set HELP_ASK_AI_ENABLED in the env") is not None


def test_contains_devspeak_returns_none_on_clean_copy():
    from app.tasks.help_tasks import _contains_devspeak
    clean = (
        "Click the Editor in the top bar. The transcript appears in the middle pane. "
        "Type a correction and click Save. Your change is recorded and reversible."
    )
    assert _contains_devspeak(clean) is None


def test_contains_devspeak_case_insensitive():
    """Lower-casing the input ensures common case variants are caught."""
    from app.tasks.help_tasks import _contains_devspeak
    assert _contains_devspeak("the speakereditpanel") == "SpeakerEditPanel"
    assert _contains_devspeak("FASTAPI") == "FastAPI"


def test_faq_generator_routes_cover_phase1_route_inventory():
    """Sanity check that the route table the FAQ generator iterates
    covers all the Phase-1 HELP_CONTENT routes (drift sentinel)."""
    from app.tasks.help_tasks import _FAQ_GENERATOR_ROUTES
    page_keys = {r[0] for r in _FAQ_GENERATOR_ROUTES}
    expected = {
        "dashboard", "sessions", "session-detail", "editor", "sop",
        "upload", "improvements", "settings", "audit", "viewer",
        "processing", "help",
    }
    missing = expected - page_keys
    assert not missing, f"FAQ generator route table missing: {missing}"


def test_faq_generator_routes_have_friendly_labels():
    """Every entry must have a non-empty page_key + content_domain + label,
    or the prompt template renders blank substitutions."""
    from app.tasks.help_tasks import _FAQ_GENERATOR_ROUTES
    for page_key, content_domain, friendly in _FAQ_GENERATOR_ROUTES:
        assert page_key and content_domain and friendly, (page_key, content_domain, friendly)
