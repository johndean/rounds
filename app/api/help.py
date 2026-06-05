"""
app/api/help.py

Purpose:
    Help Center backend — Phase 2 ships the Ask AI route only.

    POST /v1/help/ask grounds a user question against the in-process help
    corpus (`app/data/help_content.py`) and synthesizes a grounded answer
    via Gemini. If Gemini is unavailable, mis-configured, or fails parsing,
    the route falls back to an extractive answer built from the top
    retrieved articles — the enabled path NEVER hard-errors.

    Phase 3 ships the rest (article CRUD, version history, coverage,
    bulk-publish). The Phase-2 surface is intentionally narrow: one POST,
    one rate-limit, one feature flag.

Responsibilities:
    - Feature-gate via settings.HELP_ASK_AI_ENABLED (returns 404 when off).
    - Per-user hourly rate limit via Redis (graceful: if Redis is down, the
      limit silently no-ops; the route stays up).
    - Top-N retrieval over the in-process corpus + Gemini synthesis.
    - Extractive fallback that summarizes the top hits when Gemini fails.

Critical invariants:
    - The enabled path never raises 5xx for a Gemini failure. We always
      degrade to extractive.
    - max_output_tokens hard cap = 1024. Larger values are not accepted at
      this layer; the model config in llm_client owns the upper bound.
    - The corpus is read-only; the ask endpoint never writes anything.

Related plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md
                ยง7 (Phase 2 backend)
Related business rules: none yet (CC-Rounds compliance lands in Phase 4).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
from typing import Annotated, Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text

from app.auth import CurrentUser
from app.config import settings
from app.data.help_content import HelpArticle, flatten_corpus
from app.db import DbSession
from app.security.roles import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/help", tags=["help"])


# ─── Schemas ─────────────────────────────────────────────────────────────


class HelpAskRequest(BaseModel):
    """Body for POST /v1/help/ask."""
    question: str = Field(min_length=1, max_length=2000)
    page_key: Optional[str] = Field(default=None, max_length=64)
    role: Optional[str] = Field(default=None, max_length=16)


class HelpAskSource(BaseModel):
    id: str
    title: str
    summary: str


class HelpAskResponse(BaseModel):
    answer: str
    sources: list[HelpAskSource]
    used_llm: bool


# ─── Retrieval ───────────────────────────────────────────────────────────


def _score_article(article: HelpArticle, terms: list[str], page_key: Optional[str], role: Optional[str]) -> int:
    """Simple word-overlap score with page/role bias. Mirrors MIC's pattern."""
    hay = (article["title"] + " " + article["summary"]).lower()
    s = sum(1 for t in terms if t in hay)
    if page_key and article["page_key"] == page_key:
        s += 2
    if role and article["role"] == role:
        s += 1
    return s


def _retrieve_top(question: str, page_key: Optional[str], role: Optional[str], k: int = 5) -> list[HelpArticle]:
    """Return up to k highest-scoring articles for the question."""
    terms = [t for t in question.lower().split() if len(t) > 2][:8]
    pool = flatten_corpus()
    scored = [(a, _score_article(a, terms, page_key, role)) for a in pool]
    scored.sort(key=lambda p: p[1], reverse=True)
    top = [a for a, score in scored if score > 0][:k]
    if not top:
        # Cold question — return a small generic head so we always cite
        # at least something rather than producing a bare answer.
        top = [a for a, _ in scored[:3]]
    return top


# ─── Rate limit (Redis-backed; soft-fail to no-op if Redis is down) ──────


def _rate_limit_check(user_email: str) -> bool:
    """Return True if the user is OVER the per-hour cap, False otherwise.

    On Redis errors we soft-fail (return False, allow the call). The rate
    limit is a soft cap — guarding the LLM cost surface against burst, not
    a hard security boundary.
    """
    cap = settings.HELP_ASK_AI_RATE_LIMIT_PER_HOUR
    if cap <= 0:
        return False  # disabled cap
    try:
        import redis  # type: ignore[import-untyped]
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        epoch_hour = int(time.time()) // 3600
        key = f"rounds:help:ask:{user_email.lower()}:{epoch_hour}"
        count = r.incr(key)
        if count == 1:
            r.expire(key, 3600)
        return int(count) > cap
    except Exception as exc:  # noqa: BLE001
        logger.warning("help.ask rate-limit check failed (allowing request): %s", exc)
        return False


# ─── Helpers ─────────────────────────────────────────────────────────────


def _extractive_answer(top: list[HelpArticle]) -> str:
    """Build a degraded but useful answer from the top articles' summaries.

    Used when Gemini is unavailable / mis-configured / fails JSON parsing.
    """
    if not top:
        return "No matching help articles were found for that question."
    parts: list[str] = []
    for i, a in enumerate(top[:3], start=1):
        parts.append(f"[{i}] {a['title']}: {a['summary']}")
    return "\n\n".join(parts)


def _stable_id_for_question(question: str, user_email: str) -> str:
    """Best-effort log key — not security-sensitive."""
    h = hashlib.sha256()
    h.update(f"{user_email.lower()}|{question}".encode("utf-8"))
    return h.hexdigest()[:12]


# ─── Endpoint ────────────────────────────────────────────────────────────


@router.post("/ask", response_model=HelpAskResponse)
async def ask_ai(body: HelpAskRequest, user: CurrentUser) -> HelpAskResponse:
    """Grounded Q&A over the Phase-2 in-process help corpus.

    Returns:
        - 404 when settings.HELP_ASK_AI_ENABLED is false
        - 400 when the question is empty (Pydantic min_length=1 catches this)
        - 429 when the per-user hourly cap is exceeded
        - 200 otherwise — always with a usable answer (LLM or extractive)
    """
    if not settings.HELP_ASK_AI_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ask AI is not enabled")

    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question is required")

    if _rate_limit_check(user.email):
        # 429 with envelope error code — middleware wraps responses; we
        # raise HTTPException with a structured detail so the EnvelopeMiddleware
        # serializes it consistently. The retryable flag tells the client
        # to back off rather than retry immediately.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "HELP_ASK_RATE_LIMIT", "retryable": True,
                    "message": f"Hourly Ask AI limit reached ({settings.HELP_ASK_AI_RATE_LIMIT_PER_HOUR}/hr). Try again later."},
        )

    top = _retrieve_top(question, body.page_key, body.role, k=5)
    sources = [HelpAskSource(id=a["id"], title=a["title"], summary=a["summary"]) for a in top]
    extractive = _extractive_answer(top)
    answer = extractive
    used_llm = False

    if settings.GEMINI_API_KEY and top:
        try:
            from app.engines.llm_client import call_gemini_text
            context = "\n\n".join(f"[{i+1}] {a['title']}\n{a['summary']}" for i, a in enumerate(top))
            sys_prompt = (
                "You are a help assistant for the rounds.vin transcript editing application. "
                "Answer the user's question ONLY using the provided help articles. "
                "If the articles do not cover the question, say so plainly. Be concise — "
                "two to four sentences. Cite article numbers inline as [1], [2], ... matching "
                "the numbered list. "
                'Return STRICT JSON: {"answer": "<text with [n] cites>"}. No prose outside the JSON.'
            )
            payload = f"Question: {question}\n\nHelp articles:\n{context}"
            raw = call_gemini_text(sys_prompt, payload, max_output_tokens=1024)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                # Some models wrap JSON in code fences; strip and retry once.
                stripped = raw.strip()
                if stripped.startswith("```"):
                    stripped = stripped.strip("`")
                    # remove possible 'json\n' fence-language tag
                    if stripped.startswith("json"):
                        stripped = stripped[4:].lstrip()
                parsed = json.loads(stripped)
            if isinstance(parsed, dict) and parsed.get("answer"):
                answer = str(parsed["answer"]).strip()
                used_llm = True
        except Exception as exc:  # noqa: BLE001 — degrade to extractive, never 5xx
            qid = _stable_id_for_question(question, user.email)
            logger.warning("HELP_ASK: LLM path failed (qid=%s, using extractive): %s", qid, exc)

    return HelpAskResponse(answer=answer, sources=sources, used_llm=used_llm)


# ════════════════════════════════════════════════════════════════════════
#  Phase 3 — Help Article CMS (CRUD + versions + coverage + search)
#
#  Read endpoints are auth-gated (any logged-in user); write/admin endpoints
#  use `require_admin(user)` from app/security/roles.py (BR-001 — single
#  LEGACY_ADMIN_EMAIL gate until auth_users.role lands). The audience
#  filter masks unpublished + admin-only rows for non-admins as a
#  defense-in-depth layer beyond the gate.
#
#  Tables: help_articles (053), help_article_versions (054), seeded by 055.
# ════════════════════════════════════════════════════════════════════════


# ─── Helper: row → dict serializer ───────────────────────────────────────


def _row_to_article(r) -> dict:
    """Hand-built serializer matching the rounds pattern (see
    app/api/email_templates.py::_row_to_template). JSONB columns arrive as
    Python lists from asyncpg; we just pass them through."""
    return {
        "id":                  str(r["id"]),
        "slug":                r["slug"],
        "title":               r["title"],
        "summary":             r["summary"],
        "category":            r["category"],
        "audience":            r["audience"],
        "feature_tags":        r["feature_tags"] or [],
        "steps":               r["steps"] or [],
        "related_article_ids": r["related_article_ids"] or [],
        "display_order":       r["display_order"],
        "is_published":        bool(r["is_published"]),
        "content_domain":      r["content_domain"],
        "workflow_slug":       r["workflow_slug"],
        "version":             r["version"],
        "last_edited_by":      r["last_edited_by"],
        "created_at":          r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at":          r["updated_at"].isoformat() if r["updated_at"] else None,
    }


def _row_to_version(r) -> dict:
    return {
        "id":         str(r["id"]),
        "article_id": str(r["article_id"]),
        "version":    r["version"],
        "snapshot":   r["snapshot"],
        "edited_by":  r["edited_by"],
        "edited_at":  r["edited_at"].isoformat() if r["edited_at"] else None,
    }


_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9-]+")


def _slugify(title: str) -> str:
    """Deterministic slug for admin-created articles. Server-side fallback
    if the client doesn't pass one. ASCII-only; collisions raise 409."""
    norm = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    lowered = norm.strip().lower().replace(" ", "-")
    cleaned = _SLUG_NON_ALNUM.sub("", lowered)
    return cleaned[:64] or "article"


# ─── Schemas (Phase 3) ───────────────────────────────────────────────────


class HelpStep(BaseModel):
    """One numbered step on a multi-step help article (X8 in the plan)."""
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)


class HelpArticleCreate(BaseModel):
    """Body for POST /v1/help/articles."""
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=4000)
    category: str = Field(default="general", max_length=64)
    audience: str = Field(default="users", pattern=r"^(users|admin)$")
    feature_tags: list[str] = Field(default_factory=list, max_length=20)
    steps: list[HelpStep] = Field(default_factory=list, max_length=20)
    related_article_ids: list[UUID] = Field(default_factory=list, max_length=20)
    display_order: int = Field(default=0, ge=0)
    is_published: bool = False
    content_domain: str = Field(default="general", max_length=64)
    workflow_slug: Optional[str] = Field(default=None, max_length=64)
    slug: Optional[str] = Field(default=None, max_length=64)


class HelpArticleUpdate(BaseModel):
    """Body for PATCH /v1/help/articles/{id}. All fields optional."""
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    summary: Optional[str] = Field(default=None, max_length=4000)
    category: Optional[str] = Field(default=None, max_length=64)
    audience: Optional[str] = Field(default=None, pattern=r"^(users|admin)$")
    feature_tags: Optional[list[str]] = Field(default=None, max_length=20)
    steps: Optional[list[HelpStep]] = Field(default=None, max_length=20)
    related_article_ids: Optional[list[UUID]] = Field(default=None, max_length=20)
    display_order: Optional[int] = Field(default=None, ge=0)
    is_published: Optional[bool] = None
    content_domain: Optional[str] = Field(default=None, max_length=64)
    workflow_slug: Optional[str] = Field(default=None, max_length=64)


class HelpReorderItem(BaseModel):
    id: UUID
    display_order: int = Field(ge=0)


class HelpReorderRequest(BaseModel):
    items: list[HelpReorderItem] = Field(min_length=1, max_length=200)


# ─── Audience filter ─────────────────────────────────────────────────────


def _filter_for_audience(article: dict, is_admin: bool) -> bool:
    """Binary audience: admin sees everything; users see only published
    rows whose audience='users'."""
    if is_admin:
        return True
    return bool(article.get("is_published")) and article.get("audience") == "users"


def _is_user_admin(user) -> bool:
    """Local mirror of is_admin from security.roles, without importing
    the helper that does HTTPException."""
    from app.security.roles import is_admin as _is_admin
    try:
        return _is_admin(user)
    except Exception:  # noqa: BLE001
        return False


# ─── GET /v1/help/articles ───────────────────────────────────────────────


@router.get("/articles")
async def list_articles(
    db: DbSession,
    user: CurrentUser,
    feature_tag: Optional[str] = Query(default=None, max_length=64),
    audience: Optional[str] = Query(default=None, pattern=r"^(users|admin)$"),
    content_domain: Optional[str] = Query(default=None, max_length=64),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict]:
    """List articles, audience-filtered for non-admins.

    Admins see all rows (including drafts) and may pass `audience` to
    narrow. Non-admins always see only `is_published=TRUE AND audience='users'`.
    """
    is_admin = _is_user_admin(user)
    where_clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit}

    if not is_admin:
        where_clauses.append("is_published = TRUE")
        where_clauses.append("audience = 'users'")
    elif audience is not None:
        where_clauses.append("audience = :aud")
        params["aud"] = audience

    if feature_tag is not None:
        where_clauses.append("feature_tags @> CAST(:ft AS jsonb)")
        params["ft"] = json.dumps([feature_tag])

    if content_domain is not None:
        where_clauses.append("content_domain = :cd")
        params["cd"] = content_domain

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = (
        f"SELECT id, slug, title, summary, category, audience, feature_tags, steps, "
        f"       related_article_ids, display_order, is_published, content_domain, "
        f"       workflow_slug, version, last_edited_by, created_at, updated_at "
        f"  FROM help_articles {where} "
        f"  ORDER BY content_domain, display_order, created_at "
        f"  LIMIT :limit"
    )

    try:
        rows = (await db.execute(sql_text(sql), params)).mappings().all()
    except Exception as exc:  # noqa: BLE001 — table missing (pre-053) → graceful empty
        logger.warning("help.list_articles: query failed (table missing? returning empty): %s", exc)
        return []

    return [_row_to_article(r) for r in rows]


# ─── GET /v1/help/articles/{id} ─────────────────────────────────────────


@router.get("/articles/{article_id}")
async def get_article(
    article_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    row = (await db.execute(
        sql_text(
            "SELECT id, slug, title, summary, category, audience, feature_tags, steps, "
            "       related_article_ids, display_order, is_published, content_domain, "
            "       workflow_slug, version, last_edited_by, created_at, updated_at "
            "  FROM help_articles WHERE id = CAST(:aid AS uuid)"
        ),
        {"aid": str(article_id)},
    )).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Article not found"})

    serialized = _row_to_article(row)
    if not _filter_for_audience(serialized, _is_user_admin(user)):
        # Defense in depth — don't leak existence of unpublished/admin-only
        # rows to non-admins.
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Article not found"})
    return serialized


# ─── POST /v1/help/articles (admin) ──────────────────────────────────────


@router.post("/articles", status_code=201)
async def create_article(
    payload: HelpArticleCreate,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    require_admin(user)

    slug = (payload.slug or "").strip() or _slugify(payload.title)
    feature_tags = json.dumps(list(payload.feature_tags))
    steps = json.dumps([s.model_dump() for s in payload.steps])
    related_ids = json.dumps([str(x) for x in payload.related_article_ids])

    try:
        row = (await db.execute(
            sql_text(
                "INSERT INTO help_articles "
                "  (slug, title, summary, category, audience, feature_tags, steps, "
                "   related_article_ids, display_order, is_published, content_domain, "
                "   workflow_slug, version, last_edited_by) "
                "VALUES (:slug, :title, :summary, :category, :audience, "
                "        CAST(:ft AS jsonb), CAST(:st AS jsonb), CAST(:ri AS jsonb), "
                "        :dord, :pub, :cd, :ws, 1, :u) "
                "RETURNING id, slug, title, summary, category, audience, feature_tags, "
                "          steps, related_article_ids, display_order, is_published, "
                "          content_domain, workflow_slug, version, last_edited_by, "
                "          created_at, updated_at"
            ),
            {
                "slug": slug,
                "title": payload.title,
                "summary": payload.summary,
                "category": payload.category,
                "audience": payload.audience,
                "ft": feature_tags,
                "st": steps,
                "ri": related_ids,
                "dord": payload.display_order,
                "pub": payload.is_published,
                "cd": payload.content_domain,
                "ws": payload.workflow_slug,
                "u": user.email,
            },
        )).mappings().one()
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        msg = str(exc)
        if "help_articles_slug_key" in msg or "duplicate" in msg.lower():
            raise HTTPException(
                status_code=409,
                detail={"code": "SLUG_CONFLICT", "message": f"Slug '{slug}' already in use."},
            ) from exc
        if "does not exist" in msg.lower():
            raise HTTPException(
                status_code=503,
                detail={"code": "TABLE_NOT_MIGRATED", "message": "help_articles table not yet migrated; run migrations."},
            ) from exc
        logger.exception("help.create_article failed: %s", exc)
        raise HTTPException(status_code=500, detail={"code": "INTERNAL", "message": "create failed"}) from exc

    return _row_to_article(row)


# ─── PATCH /v1/help/articles/{id} (admin) — versioned ──────────────────


@router.patch("/articles/{article_id}")
async def update_article(
    article_id: UUID,
    payload: HelpArticleUpdate,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    require_admin(user)

    # Read the current row first so we can snapshot it.
    current = (await db.execute(
        sql_text(
            "SELECT id, slug, title, summary, category, audience, feature_tags, steps, "
            "       related_article_ids, display_order, is_published, content_domain, "
            "       workflow_slug, version, last_edited_by, created_at, updated_at "
            "  FROM help_articles WHERE id = CAST(:aid AS uuid) FOR UPDATE"
        ),
        {"aid": str(article_id)},
    )).mappings().first()

    if not current:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Article not found"})

    snapshot = _row_to_article(current)
    prior_version = int(current["version"])

    # Build the SET clause from non-None payload fields.
    sets: list[str] = []
    params: dict[str, Any] = {"aid": str(article_id), "u": user.email}

    if payload.title is not None:
        sets.append("title = :title")
        params["title"] = payload.title
    if payload.summary is not None:
        sets.append("summary = :summary")
        params["summary"] = payload.summary
    if payload.category is not None:
        sets.append("category = :category")
        params["category"] = payload.category
    if payload.audience is not None:
        sets.append("audience = :audience")
        params["audience"] = payload.audience
    if payload.feature_tags is not None:
        sets.append("feature_tags = CAST(:ft AS jsonb)")
        params["ft"] = json.dumps(list(payload.feature_tags))
    if payload.steps is not None:
        sets.append("steps = CAST(:st AS jsonb)")
        params["st"] = json.dumps([s.model_dump() for s in payload.steps])
    if payload.related_article_ids is not None:
        sets.append("related_article_ids = CAST(:ri AS jsonb)")
        params["ri"] = json.dumps([str(x) for x in payload.related_article_ids])
    if payload.display_order is not None:
        sets.append("display_order = :dord")
        params["dord"] = payload.display_order
    if payload.is_published is not None:
        sets.append("is_published = :pub")
        params["pub"] = payload.is_published
    if payload.content_domain is not None:
        sets.append("content_domain = :cd")
        params["cd"] = payload.content_domain
    if payload.workflow_slug is not None:
        sets.append("workflow_slug = :ws")
        params["ws"] = payload.workflow_slug

    if not sets:
        # Empty patch — no-op, return current row.
        return snapshot

    sets.append("version = version + 1")
    sets.append("last_edited_by = :u")
    sets.append("updated_at = now()")

    try:
        # Append snapshot of the PRIOR state to versions table FIRST.
        await db.execute(
            sql_text(
                "INSERT INTO help_article_versions (article_id, version, snapshot, edited_by) "
                "VALUES (CAST(:aid AS uuid), :ver, CAST(:snap AS jsonb), :u)"
            ),
            {"aid": str(article_id), "ver": prior_version, "snap": json.dumps(snapshot), "u": user.email},
        )

        # Then apply the update.
        sql = f"UPDATE help_articles SET {', '.join(sets)} WHERE id = CAST(:aid AS uuid) " \
              f"RETURNING id, slug, title, summary, category, audience, feature_tags, steps, " \
              f"          related_article_ids, display_order, is_published, content_domain, " \
              f"          workflow_slug, version, last_edited_by, created_at, updated_at"
        row = (await db.execute(sql_text(sql), params)).mappings().one()
        await db.commit()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.exception("help.update_article failed: %s", exc)
        raise HTTPException(status_code=500, detail={"code": "INTERNAL", "message": "update failed"}) from exc

    return _row_to_article(row)


# ─── PATCH /v1/help/articles/{id}/archive (admin) ──────────────────────


@router.patch("/articles/{article_id}/archive")
async def archive_article(
    article_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    """Soft-archive an article by setting is_published=FALSE. Mirrors
    MIC's semantics — there is no separate `archived` flag."""
    require_admin(user)

    current = (await db.execute(
        sql_text("SELECT * FROM help_articles WHERE id = CAST(:aid AS uuid)"),
        {"aid": str(article_id)},
    )).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Article not found"})

    snapshot = _row_to_article(current)
    try:
        await db.execute(
            sql_text(
                "INSERT INTO help_article_versions (article_id, version, snapshot, edited_by) "
                "VALUES (CAST(:aid AS uuid), :ver, CAST(:snap AS jsonb), :u)"
            ),
            {"aid": str(article_id), "ver": int(current["version"]), "snap": json.dumps(snapshot), "u": user.email},
        )
        row = (await db.execute(
            sql_text(
                "UPDATE help_articles "
                "   SET is_published = FALSE, version = version + 1, "
                "       last_edited_by = :u, updated_at = now() "
                " WHERE id = CAST(:aid AS uuid) "
                " RETURNING id, slug, title, summary, category, audience, feature_tags, steps, "
                "           related_article_ids, display_order, is_published, content_domain, "
                "           workflow_slug, version, last_edited_by, created_at, updated_at"
            ),
            {"aid": str(article_id), "u": user.email},
        )).mappings().one()
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.exception("help.archive_article failed: %s", exc)
        raise HTTPException(status_code=500, detail={"code": "INTERNAL", "message": "archive failed"}) from exc

    return _row_to_article(row)


# ─── PATCH /v1/help/articles/reorder (admin) ────────────────────────────


@router.patch("/articles/reorder")
async def reorder_articles(
    payload: HelpReorderRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    """Bulk-set display_order on a list of articles. Does NOT snapshot
    each affected article — reorder is cosmetic, and snapshotting 50
    rows for a drag-reorder would inflate the versions table."""
    require_admin(user)

    try:
        for item in payload.items:
            await db.execute(
                sql_text(
                    "UPDATE help_articles "
                    "   SET display_order = :dord, last_edited_by = :u, updated_at = now() "
                    " WHERE id = CAST(:aid AS uuid)"
                ),
                {"aid": str(item.id), "dord": item.display_order, "u": user.email},
            )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.exception("help.reorder_articles failed: %s", exc)
        raise HTTPException(status_code=500, detail={"code": "INTERNAL", "message": "reorder failed"}) from exc

    return {"updated": len(payload.items)}


# ─── GET /v1/help/articles/{id}/versions (admin) ────────────────────────


@router.get("/articles/{article_id}/versions")
async def list_versions(
    article_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> list[dict]:
    require_admin(user)
    rows = (await db.execute(
        sql_text(
            "SELECT id, article_id, version, snapshot, edited_by, edited_at "
            "  FROM help_article_versions "
            " WHERE article_id = CAST(:aid AS uuid) "
            " ORDER BY edited_at DESC"
        ),
        {"aid": str(article_id)},
    )).mappings().all()
    return [_row_to_version(r) for r in rows]


@router.get("/articles/{article_id}/versions/{version}")
async def get_version(
    article_id: UUID,
    version: int,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    require_admin(user)
    row = (await db.execute(
        sql_text(
            "SELECT id, article_id, version, snapshot, edited_by, edited_at "
            "  FROM help_article_versions "
            " WHERE article_id = CAST(:aid AS uuid) AND version = :ver"
        ),
        {"aid": str(article_id), "ver": version},
    )).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Version not found"})
    return _row_to_version(row)


# ─── GET /v1/help/coverage (admin) ──────────────────────────────────────


@router.get("/coverage")
async def coverage(db: DbSession, user: CurrentUser) -> dict:
    """Domain count grid for the admin coverage report. Returns counts of
    PUBLISHED articles per content_domain plus totals. The frontend
    flags any domain with <2 published articles as red (see
    HelpCoverageReport.vue)."""
    require_admin(user)
    rows = (await db.execute(
        sql_text(
            "SELECT content_domain, COUNT(*) AS n "
            "  FROM help_articles "
            " WHERE is_published = TRUE "
            " GROUP BY content_domain"
        )
    )).mappings().all()
    by_domain = {r["content_domain"]: int(r["n"]) for r in rows}

    totals = (await db.execute(
        sql_text(
            "SELECT "
            "  COUNT(*) FILTER (WHERE is_published) AS published, "
            "  COUNT(*) FILTER (WHERE NOT is_published) AS drafts "
            "FROM help_articles"
        )
    )).mappings().first()

    return {
        "by_domain": by_domain,
        "total_published": int(totals["published"]) if totals else 0,
        "total_drafts": int(totals["drafts"]) if totals else 0,
    }


# ─── GET /v1/help/search ────────────────────────────────────────────────


@router.get("/search")
async def search_articles(
    db: DbSession,
    user: CurrentUser,
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
) -> list[dict]:
    """Server-side substring search across title + summary. Title hits
    rank above summary-only hits. Audience-filtered for non-admins."""
    is_admin = _is_user_admin(user)

    where_clauses = ["(LOWER(title) LIKE :pat OR LOWER(summary) LIKE :pat)"]
    params: dict[str, Any] = {"pat": f"%{q.lower()}%", "limit": limit}
    if not is_admin:
        where_clauses.append("is_published = TRUE")
        where_clauses.append("audience = 'users'")

    where = " AND ".join(where_clauses)
    sql = (
        "SELECT id, slug, title, summary, category, audience, feature_tags, steps, "
        "       related_article_ids, display_order, is_published, content_domain, "
        "       workflow_slug, version, last_edited_by, created_at, updated_at, "
        "       (CASE WHEN LOWER(title) LIKE :pat THEN 0 ELSE 1 END) AS rnk "
        "  FROM help_articles "
        f" WHERE {where} "
        " ORDER BY rnk, display_order, title "
        " LIMIT :limit"
    )

    try:
        rows = (await db.execute(sql_text(sql), params)).mappings().all()
    except Exception as exc:  # noqa: BLE001
        logger.warning("help.search: query failed (table missing? returning empty): %s", exc)
        return []

    return [_row_to_article(r) for r in rows]


# ════════════════════════════════════════════════════════════════════════
#  Phase 4 — Admin actions: compliance bulk publish + AI rewrite triggers
# ════════════════════════════════════════════════════════════════════════


@router.post("/admin/bulk-publish")
async def bulk_publish_drafts(db: DbSession, user: CurrentUser) -> dict:
    """Inline (not Celery) — iterate every draft, run CC-Rounds compute_compliance,
    publish only the rows where allPass is True. Returns counts + a skipped list
    with the per-row failure reasons so the admin can target the next batch."""
    require_admin(user)

    from app.utils.help_compliance import compute_compliance

    rows = (await db.execute(
        sql_text(
            "SELECT id, slug, title, summary, category, audience, feature_tags, steps, "
            "       related_article_ids, display_order, is_published, content_domain, "
            "       workflow_slug, version, last_edited_by, created_at, updated_at "
            "  FROM help_articles WHERE is_published = FALSE"
        )
    )).mappings().all()

    published_ids: list[str] = []
    skipped: list[dict[str, Any]] = []

    for r in rows:
        a = _row_to_article(r)
        cc = compute_compliance(a)
        if cc["allPass"]:
            try:
                await db.execute(
                    sql_text(
                        "UPDATE help_articles "
                        "   SET is_published = TRUE, version = version + 1, "
                        "       last_edited_by = :u, updated_at = now() "
                        " WHERE id = CAST(:aid AS uuid)"
                    ),
                    {"aid": a["id"], "u": user.email},
                )
                published_ids.append(a["id"])
            except Exception as exc:  # noqa: BLE001
                logger.exception("help.bulk_publish: update failed for %s: %s", a["id"], exc)
                skipped.append({"id": a["id"], "title": a["title"], "reason": "DB update failed"})
        else:
            skipped.append({
                "id": a["id"],
                "title": a["title"],
                "reason": "CC-Rounds fail",
                "wordsOk": cc["wordsOk"],
                "summaryOk": cc["summaryOk"],
                "stepsOk": cc["stepsOk"],
                "wordCount": cc["wordCount"],
                "summaryLen": cc["summaryLen"],
                "stepCount": cc["stepCount"],
            })

    if published_ids:
        try:
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.exception("help.bulk_publish: commit failed: %s", exc)
            raise HTTPException(status_code=500, detail={"code": "INTERNAL", "message": "bulk publish commit failed"}) from exc

    return {
        "total_attempted": len(rows),
        "published": len(published_ids),
        "published_ids": published_ids,
        "skipped": skipped,
    }


# ─── Celery trigger endpoints (admin) ───────────────────────────────────


def _enqueue(task_name: str) -> dict:
    """Shared enqueue body. Returns the Celery task_id for operator
    tracking and the task name. Soft-fails if the broker is unreachable —
    surfaces a 503 with a clear code."""
    try:
        from app.tasks.celery_app import celery_app as _ca
        result = _ca.send_task(task_name)
        return {"task_id": result.id, "task": task_name, "enqueued": True}
    except Exception as exc:  # noqa: BLE001
        logger.exception("help: enqueue %s failed: %s", task_name, exc)
        raise HTTPException(
            status_code=503,
            detail={"code": "QUEUE_UNAVAILABLE", "message": f"Could not enqueue {task_name}; broker unreachable."},
        ) from exc


@router.post("/admin/fix-summaries")
async def admin_fix_summaries(user: CurrentUser) -> dict:
    """Enqueue fix_help_summaries_task. Returns the Celery task_id so the
    operator can poll, but the work is fire-and-forget — completion fires
    the audit_events row(s) which admin can inspect."""
    require_admin(user)
    return _enqueue("rounds.tasks.help.fix_summaries")


@router.post("/admin/expand-steps")
async def admin_expand_steps(user: CurrentUser) -> dict:
    require_admin(user)
    return _enqueue("rounds.tasks.help.expand_steps")


@router.post("/admin/expand-faqs")
async def admin_expand_faqs(user: CurrentUser) -> dict:
    require_admin(user)
    return _enqueue("rounds.tasks.help.expand_faqs")
