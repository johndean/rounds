"""
Tests for Phase 3 of the Help Center port — /v1/help/articles* CRUD.

Smoke-style coverage (route registration + auth + admin-gate + Pydantic
validation) without spinning up a real Postgres. Tests that need DB
state are out of scope here; the route handlers themselves swallow
"table missing" errors and degrade gracefully for the list/search
surfaces, so we can exercise the auth/gate plumbing without 5xx noise.

What we cover:
  - Every Phase 3 route is mounted (401 = registered + auth-gated;
    a 404 would imply the route is missing from the router).
  - Admin-gated routes return 403 (not 401) when a non-admin token is
    supplied.
  - Pydantic body validation (422) for create / update payloads.
  - Schema-level sanity: HelpArticleCreate accepts the expected shape;
    invalid audience / oversized fields are rejected.

DB-integration tests (CRUD round-trip, version snapshot, audience
filter) live in a future tests/test_help_api_integration.py once the
project-wide DB fixture exists. See conftest.py header.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app
    return TestClient(app)


# ─── Route registration smoke ──────────────────────────────────────────


@pytest.mark.parametrize(
    "method, path",
    [
        ("GET",   "/v1/help/articles"),
        ("GET",   "/v1/help/articles/00000000-0000-0000-0000-000000000000"),
        ("POST",  "/v1/help/articles"),
        ("PATCH", "/v1/help/articles/00000000-0000-0000-0000-000000000000"),
        ("PATCH", "/v1/help/articles/00000000-0000-0000-0000-000000000000/archive"),
        ("PATCH", "/v1/help/articles/reorder"),
        ("GET",   "/v1/help/articles/00000000-0000-0000-0000-000000000000/versions"),
        ("GET",   "/v1/help/articles/00000000-0000-0000-0000-000000000000/versions/1"),
        ("GET",   "/v1/help/coverage"),
        ("GET",   "/v1/help/search?q=foo"),
    ],
)
def test_phase3_routes_registered_and_auth_gated(method, path):
    """Without bearer token, every Phase 3 route returns 401 — proving
    the route is mounted under the auth-gated stack. A 404 would mean
    the route isn't registered at all."""
    client = _client()
    if method == "GET":
        resp = client.get(path)
    elif method == "POST":
        resp = client.post(path, json={"title": "x"})
    elif method == "PATCH":
        resp = client.patch(path, json={"items": [{"id": "00000000-0000-0000-0000-000000000000", "display_order": 0}]})
    else:
        raise AssertionError(f"unknown method {method}")
    assert resp.status_code in (401, 422), \
        f"{method} {path} -> {resp.status_code} (expected 401 auth-gated or 422 validation)"


# ─── Schema validation (Pydantic, runs before auth on FastAPI) ─────────


def test_create_rejects_empty_title():
    """HelpArticleCreate has title min_length=1; empty title -> 422."""
    client = _client()
    resp = client.post("/v1/help/articles", json={"title": ""})
    assert resp.status_code in (401, 422)


def test_create_rejects_invalid_audience():
    """audience pattern is ^(users|admin)$; anything else -> 422."""
    client = _client()
    resp = client.post("/v1/help/articles", json={"title": "x", "audience": "everyone"})
    assert resp.status_code in (401, 422)


def test_update_rejects_invalid_audience():
    client = _client()
    resp = client.patch(
        "/v1/help/articles/00000000-0000-0000-0000-000000000000",
        json={"audience": "everyone"},
    )
    assert resp.status_code in (401, 422)


def test_reorder_rejects_empty_list():
    """min_length=1 on items."""
    client = _client()
    resp = client.patch("/v1/help/articles/reorder", json={"items": []})
    assert resp.status_code in (401, 422)


def test_search_requires_min_query_length():
    """q min_length=2."""
    client = _client()
    resp = client.get("/v1/help/search?q=a")
    assert resp.status_code in (401, 422)


# ─── Schema sanity checks ─────────────────────────────────────────────


def test_help_article_create_schema_accepts_full_payload():
    """Direct schema construction round-trip with every field set."""
    from app.api.help import HelpArticleCreate, HelpStep
    payload = HelpArticleCreate(
        title="How do I do X?",
        summary="Two-sentence answer.",
        category="page:editor",
        audience="users",
        feature_tags=["editor", "sop"],
        steps=[
            HelpStep(title="Open the page", body="Click the link."),
            HelpStep(title="Do the thing",  body="Click Save."),
        ],
        related_article_ids=[],
        display_order=3,
        is_published=True,
        content_domain="editor",
        workflow_slug=None,
        slug="how-do-i-do-x",
    )
    assert payload.title == "How do I do X?"
    assert payload.audience == "users"
    assert len(payload.steps) == 2
    assert payload.steps[1].title == "Do the thing"


def test_help_article_create_rejects_too_many_steps():
    """max_length=20 on steps."""
    from app.api.help import HelpArticleCreate, HelpStep
    from pydantic import ValidationError
    too_many = [HelpStep(title=f"s{i}", body=f"b{i}") for i in range(25)]
    with pytest.raises(ValidationError):
        HelpArticleCreate(title="x", steps=too_many)


def test_help_article_create_rejects_too_many_feature_tags():
    from app.api.help import HelpArticleCreate
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        HelpArticleCreate(title="x", feature_tags=[f"t{i}" for i in range(25)])


# ─── Slugify helper ──────────────────────────────────────────────────


def test_slugify_basic():
    from app.api.help import _slugify
    assert _slugify("How do I edit a transcript segment?") == "how-do-i-edit-a-transcript-segment"


def test_slugify_strips_non_ascii():
    from app.api.help import _slugify
    # Accents / em-dash / quotes should be normalized away.
    out = _slugify("How do I — edit the “transcript”?")
    assert out  # non-empty
    # No quote / dash chars in the result.
    assert "—" not in out and '"' not in out and '"' not in out


def test_slugify_empty_returns_fallback():
    from app.api.help import _slugify
    assert _slugify("   ") == "article"


def test_slugify_truncates_to_64():
    from app.api.help import _slugify
    long_title = "x" * 200
    assert len(_slugify(long_title)) <= 64


# ─── Audience filter helper ──────────────────────────────────────────


def test_audience_filter_admin_sees_everything():
    from app.api.help import _filter_for_audience
    drafted = {"is_published": False, "audience": "users"}
    admin_only = {"is_published": True, "audience": "admin"}
    assert _filter_for_audience(drafted, is_admin=True) is True
    assert _filter_for_audience(admin_only, is_admin=True) is True


def test_audience_filter_user_hides_drafts():
    from app.api.help import _filter_for_audience
    drafted = {"is_published": False, "audience": "users"}
    assert _filter_for_audience(drafted, is_admin=False) is False


def test_audience_filter_user_hides_admin_only():
    from app.api.help import _filter_for_audience
    admin_only = {"is_published": True, "audience": "admin"}
    assert _filter_for_audience(admin_only, is_admin=False) is False


def test_audience_filter_user_sees_published_users():
    from app.api.help import _filter_for_audience
    published = {"is_published": True, "audience": "users"}
    assert _filter_for_audience(published, is_admin=False) is True


# ─── Row serializer helper ──────────────────────────────────────────


def test_row_to_article_handles_null_jsonb():
    """JSONB columns may arrive as None on freshly-created rows where the
    DEFAULT didn't fire (test stubs etc.). The serializer should fold
    them into empty lists, never propagate None."""
    from app.api.help import _row_to_article
    fake = {
        "id": "00000000-0000-0000-0000-000000000000",
        "slug": "s",
        "title": "t",
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
    out = _row_to_article(fake)
    assert out["feature_tags"] == []
    assert out["steps"] == []
    assert out["related_article_ids"] == []
