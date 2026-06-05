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
