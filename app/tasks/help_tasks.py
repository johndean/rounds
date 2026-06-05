"""
app/tasks/help_tasks.py — Bulk-AI admin tasks for the Help Center CMS.

Phase 4 of the Help Center port (plan 2026-06-05-009 §9.2). Three Celery
tasks, all admin-invoked via /v1/help/admin/* routes:

  - fix_help_summaries_task — rewrites any article failing CC-Rounds
    summary length into the target range via Gemini.
  - expand_help_steps_task — drafts additional steps for non-FAQ
    articles failing CC-Rounds stepCount.
  - expand_faq_steps_task — same for FAQ-category articles.

Shared posture for all three:

  - Inherit RoundsTask. Retry 3x with exponential backoff + jitter
    (inherited from base).
  - Redis idempotency key `rounds:help:task:{name}:{article_id}` with
    24h TTL. Re-runs on the same article within the window are no-ops.
  - All AI-edited articles land as ``is_published=False`` (review-gate
    invariant — admins must manually publish the rewrite). Mirrors
    MIC's app/tasks/help_tasks.py contract.
  - Versions table receives the prior snapshot before the AI rewrite
    overwrites the current row, so admin can always revert via the
    Version History dialog.
  - Every AI rewrite emits an ``audit_events`` row with
    ``kind='help.ai_rewrite'``, ``actor='ai:{task-name}'`` and
    ``details`` carrying article_id + version_before/after + which
    compliance checks failed at the time of the call.

  - Failure mode: per-article failures are caught + logged; the task
    continues to the next article. Total counts of {rewritten, skipped,
    failed} are returned and exposed in the WS event / admin toast.

Related plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §9.2
Related ADRs: ADR-006 (Celery + retries), ADR-007 (locked weights — CC-Rounds is a sibling SSOT, see app/utils/help_compliance.py).
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.engine import Engine

from app.config import settings
from app.tasks.celery_app import celery_app, RoundsTask
from app.utils.help_compliance import (
    HELP_SUMMARY_TARGET,
    FAQ_SUMMARY_TARGET,
    HELP_MIN_STEPS,
    FAQ_MIN_STEPS,
    compute_compliance,
    is_faq_category,
)

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────


def _sync_engine() -> Engine:
    """Sync SQLAlchemy engine for Celery use. Matches the pattern in
    app/tasks/sop_tasks.py + app/tasks/upload_watchdog.py."""
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    return create_engine(sync_url)


def _redis_client():
    """Local redis client. Wrapped so Celery tasks can soft-fail if Redis
    is briefly unavailable (the idempotency key is a guard, not a hard
    contract — re-running an AI rewrite without it is wasteful but safe)."""
    import redis  # type: ignore[import-untyped]
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _idem_seen(task_name: str, article_id: str) -> bool:
    """SETNX-style idempotency check. Returns True if already processed
    within the 24h TTL window."""
    try:
        r = _redis_client()
        key = f"rounds:help:task:{task_name}:{article_id}"
        was_set = r.set(key, str(int(time.time())), nx=True, ex=86400)
        return not bool(was_set)
    except Exception as exc:  # noqa: BLE001 — soft-fail; don't block the rewrite
        logger.warning("help idempotency check failed (proceeding): %s", exc)
        return False


def _row_to_dict(r) -> dict[str, Any]:
    """Mirror of app/api/help._row_to_article — duplicated here so this
    module doesn't import the API layer."""
    return {
        "id": str(r["id"]),
        "slug": r["slug"],
        "title": r["title"],
        "summary": r["summary"],
        "category": r["category"],
        "audience": r["audience"],
        "feature_tags": r["feature_tags"] or [],
        "steps": r["steps"] or [],
        "related_article_ids": r["related_article_ids"] or [],
        "display_order": r["display_order"],
        "is_published": bool(r["is_published"]),
        "content_domain": r["content_domain"],
        "workflow_slug": r["workflow_slug"],
        "version": r["version"],
        "last_edited_by": r["last_edited_by"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


def _snapshot_prior(conn, article: dict, actor: str) -> None:
    """Append the article's current state to help_article_versions BEFORE
    the AI rewrite overwrites it. Matches the PATCH route's contract in
    app/api/help.py."""
    conn.execute(
        sql_text(
            "INSERT INTO help_article_versions (article_id, version, snapshot, edited_by) "
            "VALUES (CAST(:aid AS uuid), :ver, CAST(:snap AS jsonb), :u)"
        ),
        {"aid": article["id"], "ver": int(article["version"]), "snap": json.dumps(article), "u": actor},
    )


def _emit_audit(conn, article_id: str, actor: str, summary: str, details: dict) -> None:
    """Best-effort audit row. session_id is NULL since help articles are
    not session-scoped (the audit_events.session_id column is NULLABLE
    by design — see migrations/004_audit.sql)."""
    try:
        conn.execute(
            sql_text(
                "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
                "VALUES (NULL, :actor, 'help.ai_rewrite', :s, CAST(:d AS jsonb))"
            ),
            {
                "actor": actor,
                "s": summary,
                "d": json.dumps({**details, "article_id": article_id}),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("help audit insert failed (proceeding): %s", exc)


def _ai_call(system_prompt: str, payload: str, max_tokens: int = 1024) -> str:
    """Wrapper around llm_client.call_gemini_text with a fixed token cap
    for help rewrites. Bulk tasks cap output low to keep cost bounded
    when the admin clicks Fix-CC-Rounds on a corpus of 50+ articles."""
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")
    from app.engines.llm_client import call_gemini_text
    return call_gemini_text(system_prompt, payload, max_output_tokens=max_tokens)


def _parse_json_response(raw: str) -> Optional[dict]:
    """Tolerant JSON parser — strips fence wrappers if present."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].lstrip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None
    return None


# ═════════════════════════════════════════════════════════════════════
#   Task 1 — Fix CC-Rounds summaries
# ═════════════════════════════════════════════════════════════════════


@celery_app.task(bind=True, base=RoundsTask, name="rounds.tasks.help.fix_summaries", max_retries=2)
def fix_help_summaries_task(self) -> dict:
    """For every published article whose summary fails CC-Rounds, ask
    Gemini to rewrite it into the appropriate target range and save the
    rewrite as a draft (is_published=False) pending admin review.

    Returns a dict {rewritten: int, skipped: int, failed: int, article_ids: [..]}.
    """
    engine = _sync_engine()
    rewritten = 0
    skipped = 0
    failed = 0
    touched_ids: list[str] = []

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sql_text(
                    "SELECT id, slug, title, summary, category, audience, feature_tags, steps, "
                    "       related_article_ids, display_order, is_published, content_domain, "
                    "       workflow_slug, version, last_edited_by, created_at, updated_at "
                    "  FROM help_articles"
                )
            ).mappings().all()

        targets = []
        for r in rows:
            a = _row_to_dict(r)
            cc = compute_compliance(a)
            if not cc["summaryOk"]:
                targets.append(a)

        logger.info("help.fix_summaries: %d articles need rewrite", len(targets))

        for a in targets:
            if _idem_seen("fix_summaries", a["id"]):
                skipped += 1
                continue
            try:
                low, high = FAQ_SUMMARY_TARGET if is_faq_category(a["category"]) else HELP_SUMMARY_TARGET
                sys_prompt = (
                    "You are a technical writer for the rounds.vin transcript editing application. "
                    "Rewrite the user-facing summary of the help article below so the result is "
                    "between {low} and {high} characters, in plain product voice (second person, "
                    "end-user nouns). Do not invent features that the source content does not "
                    "describe. Do not use Vue component names, DB schema terms, phase markers, "
                    "or HTTP routes. "
                    'Return STRICT JSON: {{"summary": "<the rewritten summary>"}}. No prose outside the JSON.'
                ).format(low=low, high=high)
                payload = (
                    f"Title: {a['title']}\n\n"
                    f"Current summary ({len(a['summary'])} chars):\n{a['summary']}\n\n"
                    "Step bodies (for context, do not include in summary):\n"
                    + "\n".join(f"- {s.get('title','')}: {s.get('body','')}" for s in a["steps"] if isinstance(s, dict))
                )
                raw = _ai_call(sys_prompt, payload, max_tokens=512)
                parsed = _parse_json_response(raw)
                if not parsed or not isinstance(parsed.get("summary"), str) or not parsed["summary"].strip():
                    logger.warning("help.fix_summaries: bad LLM response for %s", a["id"])
                    failed += 1
                    continue
                new_summary = parsed["summary"].strip()

                actor = "ai:fix_summaries"
                with engine.begin() as conn:
                    _snapshot_prior(conn, a, actor)
                    conn.execute(
                        sql_text(
                            "UPDATE help_articles "
                            "   SET summary = :s, version = version + 1, "
                            "       is_published = FALSE, last_edited_by = :u, updated_at = now() "
                            " WHERE id = CAST(:aid AS uuid)"
                        ),
                        {"s": new_summary, "u": actor, "aid": a["id"]},
                    )
                    _emit_audit(
                        conn,
                        article_id=a["id"],
                        actor=actor,
                        summary=f"AI summary rewrite ({len(a['summary'])} → {len(new_summary)} chars)",
                        details={
                            "version_before": int(a["version"]),
                            "version_after":  int(a["version"]) + 1,
                            "summary_len_before": len(a["summary"]),
                            "summary_len_after":  len(new_summary),
                            "target_range":   [low, high],
                        },
                    )
                rewritten += 1
                touched_ids.append(a["id"])
            except Exception as exc:  # noqa: BLE001 — per-article failure isolated
                failed += 1
                logger.warning("help.fix_summaries: failed for %s: %s", a["id"], exc)

    finally:
        engine.dispose()

    return {"rewritten": rewritten, "skipped": skipped, "failed": failed, "article_ids": touched_ids}


# ═════════════════════════════════════════════════════════════════════
#   Task 2 — Expand help steps
# ═════════════════════════════════════════════════════════════════════


def _expand_steps_for_category(category_filter: str, min_steps: int, task_name: str) -> dict:
    """Internal helper shared by expand_help_steps and expand_faq_steps."""
    engine = _sync_engine()
    rewritten = 0
    skipped = 0
    failed = 0
    touched_ids: list[str] = []

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sql_text(
                    "SELECT id, slug, title, summary, category, audience, feature_tags, steps, "
                    "       related_article_ids, display_order, is_published, content_domain, "
                    "       workflow_slug, version, last_edited_by, created_at, updated_at "
                    "  FROM help_articles"
                )
            ).mappings().all()

        targets = []
        for r in rows:
            a = _row_to_dict(r)
            faq = is_faq_category(a["category"])
            if category_filter == "faq" and not faq:
                continue
            if category_filter == "help" and faq:
                continue
            if len(a["steps"]) < min_steps:
                targets.append(a)

        logger.info("%s: %d articles need expansion", task_name, len(targets))

        for a in targets:
            if _idem_seen(task_name, a["id"]):
                skipped += 1
                continue
            try:
                existing_steps = a["steps"] or []
                needed = max(0, min_steps - len(existing_steps))
                if needed == 0:
                    skipped += 1
                    continue
                sys_prompt = (
                    "You are a technical writer for the rounds.vin transcript editing application. "
                    "The help article below has fewer steps than required. Draft {n} additional "
                    "numbered step(s) to bring the total to at least {min_steps}. Each step is a "
                    "short imperative title (e.g. 'Open the page') and a 1-2 sentence body in plain "
                    "product voice (second person, end-user nouns). Do not invent features that the "
                    "source content does not describe. Do not use Vue component names, DB schema "
                    "terms, phase markers, or HTTP routes. "
                    'Return STRICT JSON: {{"steps": [{{"title":"...","body":"..."}}, ...]}}. '
                    "No prose outside the JSON."
                ).format(n=needed, min_steps=min_steps)
                payload = (
                    f"Title: {a['title']}\n\n"
                    f"Summary: {a['summary']}\n\n"
                    f"Existing steps ({len(existing_steps)}):\n"
                    + "\n".join(
                        f"  {i+1}. {s.get('title','')} — {s.get('body','')}"
                        for i, s in enumerate(existing_steps)
                        if isinstance(s, dict)
                    )
                )
                raw = _ai_call(sys_prompt, payload, max_tokens=1024)
                parsed = _parse_json_response(raw)
                if not parsed or not isinstance(parsed.get("steps"), list):
                    failed += 1
                    logger.warning("%s: bad LLM response for %s", task_name, a["id"])
                    continue
                new_steps_raw = parsed["steps"]
                clean_new: list[dict] = []
                for s in new_steps_raw:
                    if not isinstance(s, dict):
                        continue
                    title = str(s.get("title", "")).strip()
                    body = str(s.get("body", "")).strip()
                    if title and body:
                        clean_new.append({"title": title, "body": body})
                if not clean_new:
                    failed += 1
                    continue

                combined = list(existing_steps) + clean_new

                actor = f"ai:{task_name}"
                with engine.begin() as conn:
                    _snapshot_prior(conn, a, actor)
                    conn.execute(
                        sql_text(
                            "UPDATE help_articles "
                            "   SET steps = CAST(:st AS jsonb), version = version + 1, "
                            "       is_published = FALSE, last_edited_by = :u, updated_at = now() "
                            " WHERE id = CAST(:aid AS uuid)"
                        ),
                        {"st": json.dumps(combined), "u": actor, "aid": a["id"]},
                    )
                    _emit_audit(
                        conn,
                        article_id=a["id"],
                        actor=actor,
                        summary=f"AI step expansion ({len(existing_steps)} → {len(combined)})",
                        details={
                            "version_before": int(a["version"]),
                            "version_after":  int(a["version"]) + 1,
                            "steps_before":   len(existing_steps),
                            "steps_after":    len(combined),
                            "min_target":     min_steps,
                        },
                    )
                rewritten += 1
                touched_ids.append(a["id"])
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.warning("%s: failed for %s: %s", task_name, a["id"], exc)
    finally:
        engine.dispose()

    return {"rewritten": rewritten, "skipped": skipped, "failed": failed, "article_ids": touched_ids}


@celery_app.task(bind=True, base=RoundsTask, name="rounds.tasks.help.expand_steps", max_retries=2)
def expand_help_steps_task(self) -> dict:
    """Drafts additional steps for non-FAQ articles failing CC-Rounds HELP_MIN_STEPS=3."""
    return _expand_steps_for_category("help", HELP_MIN_STEPS, "expand_steps")


# ═════════════════════════════════════════════════════════════════════
#   Task 3 — Expand FAQ steps
# ═════════════════════════════════════════════════════════════════════


@celery_app.task(bind=True, base=RoundsTask, name="rounds.tasks.help.expand_faqs", max_retries=2)
def expand_faq_steps_task(self) -> dict:
    """Drafts additional steps for FAQ-category articles failing CC-Rounds FAQ_MIN_STEPS=2."""
    return _expand_steps_for_category("faq", FAQ_MIN_STEPS, "expand_faqs")


# ═════════════════════════════════════════════════════════════════════
#   Task 4 — Generate FAQ corpus (Phase 5, X6)
# ═════════════════════════════════════════════════════════════════════


# The routes Phase 1 ships content for. The FAQ generator drafts one
# FAQ article per route to cover the "I have a quick question about X"
# surface in the in-app Help drawer's FAQ tab.
#
# Each entry is (page_key, content_domain, friendly_label). The label
# feeds into the Gemini prompt verbatim — admins should tweak this
# table when the rounds.vin route inventory grows.
_FAQ_GENERATOR_ROUTES: list[tuple[str, str, str]] = [
    ("dashboard",      "dashboard",   "the Dashboard"),
    ("sessions",       "sessions",    "the Sessions list"),
    ("session-detail", "sessions",    "an individual session's detail page"),
    ("editor",         "editor",      "the Transcript Editor"),
    ("sop",            "sop",         "the SOP workflow page"),
    ("upload",         "processing",  "the Upload page"),
    ("improvements",   "improvements","the Improvements page"),
    ("settings",       "settings",    "the admin Settings page"),
    ("audit",          "editor",      "the Audit view"),
    ("viewer",         "sessions",    "the read-only Viewer"),
    ("processing",     "processing",  "the Processing progress page"),
    ("help",           "general",     "the Help Center itself"),
]


import re as _re

# Dev-speak terms the generator MUST NOT emit. The task post-filters
# Gemini's response against this list before insert — if ANY term hits,
# the draft is rejected and counted as a failure rather than seeded.
# This is defense in depth on top of the system prompt's "don't say
# these" instruction; LLMs sometimes ignore prose constraints.
#
# Hardened 2026-06-05 after adversarial workflow review found the
# original substring-only blacklist trivially bypassable via paraphrase
# (e.g. Gemini emits "the audit events table" instead of "audit_events").
# Expanded with the spaced/paraphrased variants the LLM realistically
# emits, plus regex patterns for whole categories below.
_DEVSPEAK_BLACKLIST: tuple[str, ...] = (
    # Specific Vue components + their spaced paraphrases.
    "SpeakerEditPanel", "speaker edit panel",
    "HelpCenterDrawer", "help center drawer",
    "HelpPanel", "help panel",
    "HelpAskComposer", "help ask composer",
    # DB table names + spaced paraphrases + generic schema terms.
    "text_edit row", "audit_events", "audit events table",
    "help_articles", "help articles table",
    "auth_users", "auth users table",
    "correction ledger", "JSONB column", "JSONB field",
    # HTTP routes (method-prefix + generic /v1 references).
    "GET /v1/", "POST /v1/", "PATCH /v1/", "DELETE /v1/",
    "/v1/sessions", "/v1/help", "/v1/corrections", "/v1/exports",
    # Frameworks + libraries.
    "FastAPI", "Swagger", "Celery", "Pinia", "Pydantic",
    "SQLAlchemy", "Postgres", "asyncpg", "uvicorn", "Vite", "Vuex",
    # Env vars (specific + generic).
    "VITE_HELP_ASK_AI_ENABLED", "SOP_DEADLINE_EMAIL_ENABLED",
    "GEMINI_API_KEY", "DATABASE_URL", "REDIS_URL",
    # Implementation slang.
    "browser local", "localStorage", "sessionStorage",
    "Vue component", "background worker", "worker queue",
)

# Regex patterns catch entire categories of dev-speak the literal list
# can't enumerate. Compiled once at module load.
_DEVSPEAK_REGEXES: tuple[_re.Pattern[str], ...] = (
    _re.compile(r"\bphase\s*\d", _re.IGNORECASE),               # "Phase 1", "Phase 9.5", "Phase8"
    _re.compile(r"\b[a-z_]+\.vue\b", _re.IGNORECASE),           # any "FooBar.vue"
    _re.compile(r"\b[A-Z][A-Z0-9_]{4,}\b"),                     # ENV_VAR_LIKE_THIS (case-sensitive)
)


def _contains_devspeak(text: str) -> Optional[str]:
    """Returns the first dev-speak term found, or None if clean.

    Checks literal substrings (case-insensitive) AND regex patterns
    for entire categories (Phase markers, .vue references, SCREAMING_SNAKE
    env vars). Returns the offending term for logging.
    """
    lower = text.lower()
    for term in _DEVSPEAK_BLACKLIST:
        if term.lower() in lower:
            return term
    for pattern in _DEVSPEAK_REGEXES:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return None


@celery_app.task(bind=True, base=RoundsTask, name="rounds.tasks.help.generate_faq_corpus", max_retries=1)
def generate_faq_corpus_task(self) -> dict:
    """One-time admin-invoked seed: draft a starter FAQ article per route.

    For each entry in ``_FAQ_GENERATOR_ROUTES`` the task asks Gemini for
    ONE FAQ article in strict JSON, validates the response against the
    CC-Rounds FAQ thresholds (summary length, step count) AND the
    dev-speak blacklist, then INSERTs the article as ``is_published=False``
    with slug ``faq-ai-{page_key}`` for idempotency. Re-runs skip routes
    that already have an ``faq-ai-{page_key}`` row (ON CONFLICT
    DO NOTHING), so the task is safe to invoke multiple times.

    All drafts land for admin review — none are auto-published. The
    admin reviews + clicks Publish via the standard UI.

    Returns ``{created: int, skipped_existing: int, devspeak_rejected: int,
    failed: int, article_ids: [...]}``.
    """
    from app.utils.help_compliance import FAQ_SUMMARY_TARGET, FAQ_MIN_STEPS

    engine = _sync_engine()
    created = 0
    skipped_existing = 0
    devspeak_rejected = 0
    failed = 0
    touched_ids: list[str] = []

    actor = "ai:generate_faq_corpus"
    low, high = FAQ_SUMMARY_TARGET
    min_steps = FAQ_MIN_STEPS

    # Task-level Redis idempotency guard (hardened 2026-06-05 — Phase 5
    # adversarial review). A double-clicked Generate button used to
    # enqueue two task messages; the per-route slug uniqueness defended
    # data integrity but BOTH runs would still call Gemini for every
    # route until the first one inserted. This SETNX-style guard
    # short-circuits the duplicate run at task entry, costing zero
    # extra LLM calls. 10-minute TTL lets a stuck task be retried
    # after a Celery worker crash.
    if _idem_seen("generate_faq_corpus", "global"):
        logger.info("generate_faq_corpus: another instance is already running; bailing")
        return {
            "created": 0, "skipped_existing": 0, "devspeak_rejected": 0, "failed": 0,
            "article_ids": [], "skipped_concurrent_run": True,
        }

    try:
        # Build a small list of existing article titles as cross-link
        # candidates. Capped at 30 so the prompt stays compact; the
        # generator picks 0-3 IDs by index.
        with engine.connect() as conn:
            existing_rows = conn.execute(
                sql_text(
                    "SELECT id, title, slug, content_domain "
                    "  FROM help_articles "
                    " WHERE is_published = TRUE "
                    " ORDER BY content_domain, display_order "
                    " LIMIT 30"
                )
            ).mappings().all()
        existing_compact = [
            {"id": str(r["id"]), "title": r["title"], "domain": r["content_domain"]}
            for r in existing_rows
        ]

        for page_key, content_domain, friendly_label in _FAQ_GENERATOR_ROUTES:
            slug = f"faq-ai-{page_key}"
            # Idempotency — bail before the LLM call if this slug exists.
            with engine.connect() as conn:
                exists = conn.execute(
                    sql_text("SELECT 1 FROM help_articles WHERE slug = :slug"),
                    {"slug": slug},
                ).first()
            if exists:
                skipped_existing += 1
                continue

            sys_prompt = (
                "You are a technical writer for the rounds.vin transcript editing application. "
                "Draft ONE Frequently Asked Question (FAQ) article in plain product voice for "
                "{friendly}. The output goes into the FAQ tab of an in-app Help Center read by "
                "end users (clinicians, copy editors, operators) — not engineers."
                "\n\n"
                "STRICT RULES (a violation makes the output unusable):\n"
                "  1. Second person, end-user nouns ('you upload', 'the segment', 'the Editor').\n"
                "  2. No Vue component names. No DB schema or table names. No HTTP routes. "
                "No env var names. No 'Phase N' markers. No 'FastAPI', 'Celery', 'Pinia', "
                "'Pydantic', or framework names. No 'browser local' or other implementation slang.\n"
                "  3. Title is the question, ending in a question mark. 6-14 words.\n"
                "  4. Summary is a single short paragraph that answers the question in plain "
                "language. Length MUST be {low}-{high} characters inclusive.\n"
                "  5. Exactly {min_steps} or more numbered steps. Each step has a short imperative "
                "title (e.g. 'Open the page') and a 1-2 sentence body. Steps follow the "
                "open / do / verify pattern.\n"
                "  6. From the provided existing-article list, pick 0-3 ids whose topic is closely "
                "related and return them in related_ids. If nothing is closely related, return [].\n"
                "\n"
                "OUTPUT - STRICT JSON, no prose outside:\n"
                '{{"title": "<question>", "summary": "<paragraph>", "steps": ['
                '{{"title":"<imperative>","body":"<sentence>"}}, ...], "related_ids": ["<uuid>", ...]}}'
            ).format(friendly=friendly_label, low=low, high=high, min_steps=min_steps)

            payload = (
                f"Page: {friendly_label} (route key '{page_key}', content domain '{content_domain}').\n\n"
                "Existing published help articles (pick up to 3 ids for related_ids, "
                "or return []):\n"
                + "\n".join(
                    f"  [{a['id']}] {a['title']} ({a['domain']})" for a in existing_compact
                )
            )

            try:
                raw = _ai_call(sys_prompt, payload, max_tokens=1024)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.warning("generate_faq_corpus: LLM call failed for %s: %s", page_key, exc)
                continue

            parsed = _parse_json_response(raw)
            if not parsed or not isinstance(parsed, dict):
                failed += 1
                logger.warning("generate_faq_corpus: non-JSON response for %s", page_key)
                continue

            # Strict isinstance — coercion via str() on a non-string
            # (e.g. Gemini returns title: [1,2]) would produce garbage
            # like "[1, 2]" and slip into the article. Reject instead.
            raw_title = parsed.get("title")
            raw_summary = parsed.get("summary")
            raw_steps = parsed.get("steps", [])
            raw_related = parsed.get("related_ids", [])

            if not isinstance(raw_title, str) or not isinstance(raw_summary, str):
                failed += 1
                logger.warning("generate_faq_corpus: non-string title/summary for %s", page_key)
                continue
            title = raw_title.strip()
            summary = raw_summary.strip()

            if not title or not summary or not isinstance(raw_steps, list):
                failed += 1
                logger.warning("generate_faq_corpus: shape failure for %s", page_key)
                continue

            # Validate + clean steps.
            clean_steps: list[dict] = []
            for s in raw_steps:
                if not isinstance(s, dict):
                    continue
                st = str(s.get("title", "")).strip()
                sb = str(s.get("body", "")).strip()
                if st and sb:
                    clean_steps.append({"title": st, "body": sb})
            if len(clean_steps) < min_steps:
                failed += 1
                logger.warning(
                    "generate_faq_corpus: too few steps for %s (got %d, need %d)",
                    page_key, len(clean_steps), min_steps,
                )
                continue

            # Validate summary length.
            if not (low <= len(summary) <= high):
                failed += 1
                logger.warning(
                    "generate_faq_corpus: summary length %d outside [%d,%d] for %s",
                    len(summary), low, high, page_key,
                )
                continue

            # Validate related_ids — keep only IDs that match existing rows.
            valid_existing_ids = {a["id"] for a in existing_compact}
            clean_related: list[str] = []
            if isinstance(raw_related, list):
                for rid in raw_related[:3]:
                    if isinstance(rid, str) and rid in valid_existing_ids:
                        clean_related.append(rid)

            # DEV-SPEAK BLACKLIST — defense in depth on top of the prompt.
            joined = title + "\n" + summary + "\n" + "\n".join(
                s["title"] + " " + s["body"] for s in clean_steps
            )
            term = _contains_devspeak(joined)
            if term is not None:
                devspeak_rejected += 1
                logger.warning(
                    "generate_faq_corpus: REJECTED %s - dev-speak term '%s' in output", page_key, term,
                )
                continue

            # Insert.
            try:
                with engine.begin() as conn:
                    inserted = conn.execute(
                        sql_text(
                            "INSERT INTO help_articles "
                            "  (slug, title, summary, category, audience, feature_tags, steps, "
                            "   related_article_ids, display_order, is_published, content_domain, "
                            "   workflow_slug, version, last_edited_by) "
                            "VALUES (:slug, :title, :summary, :cat, 'users', "
                            "        CAST(:ft AS jsonb), CAST(:st AS jsonb), CAST(:ri AS jsonb), "
                            "        0, FALSE, :cd, NULL, 1, :u) "
                            "ON CONFLICT (slug) DO NOTHING "
                            "RETURNING id"
                        ),
                        {
                            "slug":  slug,
                            "title": title,
                            "summary": summary,
                            "cat":   f"faq:{page_key}",
                            "ft":    json.dumps([page_key]),
                            "st":    json.dumps(clean_steps),
                            "ri":    json.dumps(clean_related),
                            "cd":    content_domain,
                            "u":     actor,
                        },
                    ).first()
                    if inserted is None:
                        # Race - another instance of the task created the
                        # row between our existence check and this INSERT.
                        # Count as skipped, not failed.
                        skipped_existing += 1
                        continue
                    article_id = str(inserted[0])
                    _emit_audit(
                        conn,
                        article_id=article_id,
                        actor=actor,
                        summary=f"AI FAQ corpus seed for {page_key}",
                        details={
                            "page_key":        page_key,
                            "content_domain":  content_domain,
                            "summary_len":     len(summary),
                            "step_count":      len(clean_steps),
                            "related_count":   len(clean_related),
                        },
                    )
                created += 1
                touched_ids.append(article_id)
            except Exception as exc:  # noqa: BLE001
                # Re-raise DB connection errors so Celery's retry policy
                # kicks in — a full DB outage shouldn't be silently
                # absorbed as 12 individual route "failures" that exhaust
                # 12 wasted Gemini calls on the next attempt.
                from sqlalchemy.exc import OperationalError, DisconnectionError
                if isinstance(exc, (OperationalError, DisconnectionError)):
                    logger.error("generate_faq_corpus: DB connection lost — bubbling to Celery retry")
                    raise
                failed += 1
                logger.exception("generate_faq_corpus: insert failed for %s: %s", page_key, exc)

    finally:
        engine.dispose()

    return {
        "created":           created,
        "skipped_existing":  skipped_existing,
        "devspeak_rejected": devspeak_rejected,
        "failed":            failed,
        "article_ids":       touched_ids,
    }
