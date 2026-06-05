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
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import CurrentUser
from app.config import settings
from app.data.help_content import HelpArticle, flatten_corpus

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
