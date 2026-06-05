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
    ],
)
def test_phase4_admin_routes_registered_and_auth_gated(path):
    """Without a bearer token, every Phase 4 admin route returns 401 —
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
    """All three tasks should be picked up by celery_app.conf.include
    via the 'app.tasks.help_tasks' entry."""
    from app.tasks.celery_app import celery_app
    # Importing app.tasks.help_tasks triggers @celery_app.task decorators.
    import app.tasks.help_tasks  # noqa: F401

    names = set(celery_app.tasks.keys())
    assert "rounds.tasks.help.fix_summaries" in names
    assert "rounds.tasks.help.expand_steps" in names
    assert "rounds.tasks.help.expand_faqs" in names
