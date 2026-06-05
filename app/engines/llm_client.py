"""
LLM client — Gemini multimodal + text for the ingest pipeline.

Ports MIC `app/engines/llm_client.py` (lines 1-200) keeping the
multimodal upload path (used by AI MODE direct-to-Gemini) and the
text-only path (used downstream by discrepancy classify). Vertex AI
text fallback ships when `VERTEX_AI_CLASSIFY_ENABLED=true`.

This file deliberately keeps the surface narrow:
  * call_gemini_multimodal(file_paths, system_prompt, model_id)
  * call_gemini_text(system_prompt, user_payload, model_id)
  * call_vertex_ai_text(system_prompt, user_payload, model_id)
  * classify_discrepancies(...) — dispatcher (Gemini vs Vertex)

`LLMError.category` is one of:
  gemini_overloaded | gemini_quota | gemini_config | gemini_error
The worker uses these to mark sessions failed with a useful reason.

Related ADRs: ADR-006 (queue processing + retries).
Related business rules: BR-015 (Gemini hallucination-loop detector lives in ai_process.py, not here).
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    def __init__(self, message: str, category: str = "gemini_error") -> None:
        super().__init__(message)
        self.category = category


# Categories where retry will never help — caller should fail-fast and surface
# a specific failure card instead of burning the Celery retry budget.
TERMINAL_LLM_CATEGORIES = frozenset({
    "gemini_context_overflow",
    "gemini_config",
    "gemini_model_deprecated",
    "validation_error",
})


# Public input-token caps per Gemini model. Used by the pre-flight count_tokens
# probe to fail-fast on overflow instead of paying the 30-60 s upload + first
# generate_content cost. Numbers from Google's published model docs; flash-lite
# / flash share the 1M ceiling and 2.5-pro is the 2M tier.
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "gemini-2.5-flash-lite": 1_048_576,
    "gemini-2.5-flash":      1_048_576,
    "gemini-2.5-pro":        2_097_152,
}


def _estimate_input_tokens(client, model_id: str, contents) -> Optional[int]:
    """Best-effort token-count probe. Returns None on any error so the caller
    falls through to the existing generate_content path with zero behavior
    change. Never raises."""
    try:
        result = client.models.count_tokens(model=model_id, contents=contents)
        return int(getattr(result, "total_tokens", 0)) or None
    except Exception as e:
        logger.warning(f"count_tokens probe failed (non-fatal): {e}")
        return None


def _categorize_gemini_error(exc_text: str) -> str:
    t = (exc_text or "").lower()
    # Model deprecated / removed: 404 NOT_FOUND with "no longer available".
    # Permanent — every retry with the same model id will fail.
    if ("no longer available" in t) or ("404" in t and "not_found" in t) or ("404" in t and "not found" in t):
        return "gemini_model_deprecated"
    # Context overflow: 400 INVALID_ARGUMENT with "token count exceeds" — permanent
    # for the given input. Retrying with the same files always fails.
    if "token count exceeds" in t or "input token count" in t:
        return "gemini_context_overflow"
    if "503" in t or "unavailable" in t or "high demand" in t:
        return "gemini_overloaded"
    if "resource_exhausted" in t or "quota" in t or "billing" in t:
        return "gemini_quota"
    if "api_key" in t or "401" in t or "permission_denied" in t:
        return "gemini_config"
    return "gemini_error"


def _wait_for_file_active(client, uploaded_file, timeout_sec: int = 300) -> None:
    """Poll Gemini File API until the uploaded file flips from PROCESSING to ACTIVE."""
    start = time.time()
    name = uploaded_file.name
    while time.time() - start < timeout_sec:
        f = client.files.get(name=name)
        state = getattr(f, "state", None)
        if state and str(state).upper().endswith("ACTIVE"):
            return
        if state and str(state).upper().endswith("FAILED"):
            raise LLMError(f"Gemini file {name} processing failed", category="gemini_error")
        time.sleep(2)
    raise LLMError(f"Gemini file {name} did not become ACTIVE within {timeout_sec}s", category="gemini_error")


def call_gemini_multimodal(
    file_paths: list[tuple[str, str]],
    system_prompt: str,
    # 2.5-pro (2M context) is the only model that fits a typical CE session
    # (30-60 min video + 100+ slide deck = up to ~1.5M tokens). 2.5-flash
    # (1M context) rejects these uploads with 400 INVALID_ARGUMENT. Callers
    # may still pass model_id=gemini-2.5-flash explicitly for short clips.
    model_id: str = "gemini-2.5-pro",
    max_retries: int = 2,
) -> str:
    """Send local files + a prompt to Gemini. Returns raw response text."""
    if not settings.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY not configured", category="gemini_config")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    uploaded = []
    for local_path, mime in file_paths:
        logger.info(f"gemini upload: {local_path} ({mime})")
        try:
            # google-genai SDK renamed `file=` to `path=`. Try `path=` first
            # (new SDK) and fall back to `file=` for older installs so the
            # code works against both.
            try:
                uf = client.files.upload(path=local_path, config={"mime_type": mime})
            except TypeError:
                uf = client.files.upload(file=local_path, config={"mime_type": mime})
            uploaded.append(uf)
        except Exception as e:
            for prev in uploaded:
                try:
                    client.files.delete(name=prev.name)
                except Exception as cleanup_err:
                    logger.debug(f"gemini cleanup ignored: {cleanup_err}")
            raise LLMError(f"upload failed for {local_path}: {e}", category=_categorize_gemini_error(str(e)))

    for uf in uploaded:
        _wait_for_file_active(client, uf)

    content = [types.Part.from_uri(file_uri=uf.uri, mime_type=uf.mime_type) for uf in uploaded]
    content.append(system_prompt)

    # Pre-flight token check (Phase 5 of the 2026-05-23 perf plan). Catches
    # the overflow case BEFORE the 30-60s generate_content round-trip, saving
    # quota and worker time on already-doomed inputs. Best-effort: if the
    # probe itself errors, fall through silently to the existing path.
    tokens = _estimate_input_tokens(client, model_id, content)
    limit = MODEL_CONTEXT_LIMITS.get(model_id)
    if tokens is not None and limit is not None and tokens > limit:
        logger.warning(
            f"gemini pre-flight: {tokens} tokens > {model_id} limit {limit}; "
            f"aborting before generate_content"
        )
        for uf in uploaded:
            try:
                client.files.delete(name=uf.name)
            except Exception as cleanup_err:
                logger.debug(f"gemini cleanup ignored: {cleanup_err}")
        raise LLMError(
            f"input is {tokens} tokens; {model_id} limit is {limit}",
            category="gemini_context_overflow",
        )
    if tokens is not None and limit is not None:
        logger.info(f"gemini pre-flight: {tokens}/{limit} tokens for {model_id}")

    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"gemini multimodal call attempt={attempt + 1} model={model_id} files={len(uploaded)}")
            response = client.models.generate_content(
                model=model_id,
                contents=content,
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=65536),
            )
            for uf in uploaded:
                try:
                    client.files.delete(name=uf.name)
                except Exception as cleanup_err:
                    logger.debug(f"gemini cleanup ignored: {cleanup_err}")
            return response.text
        except Exception as e:
            last_err = e
            category = _categorize_gemini_error(str(e))
            logger.warning(f"gemini attempt {attempt + 1} failed ({category}): {e}")
            # Permanent errors: retrying with the same inputs can't help. Bail
            # immediately so the caller can fail-fast with a specific message.
            if category in TERMINAL_LLM_CATEGORIES:
                for uf in uploaded:
                    try:
                        client.files.delete(name=uf.name)
                    except Exception as cleanup_err:
                        logger.debug(f"gemini cleanup ignored: {cleanup_err}")
                raise LLMError(f"gemini permanent error ({category}): {e}", category=category)
            if attempt < max_retries:
                time.sleep(2 ** attempt)

    for uf in uploaded:
        try:
            client.files.delete(name=uf.name)
        except Exception as cleanup_err:
            logger.debug(f"gemini cleanup ignored: {cleanup_err}")
    raise LLMError(
        f"gemini failed after {max_retries + 1} attempts: {last_err}",
        category=_categorize_gemini_error(str(last_err)),
    )


def call_gemini_text(
    system_prompt: str,
    user_payload: str,
    model_id: str = "gemini-2.5-pro",
    max_retries: int = 2,
    max_output_tokens: int = 16384,
) -> str:
    if not settings.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY not configured", category="gemini_config")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    backoff = [3, 8]
    last_err: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            combined = system_prompt + "\n\n---\n\n" + user_payload
            response = client.models.generate_content(
                model=model_id,
                contents=combined,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=max_output_tokens,
                    response_mime_type="application/json",
                ),
            )
            try:
                finish = response.candidates[0].finish_reason
            except (IndexError, AttributeError):
                finish = None
            if finish is not None and "STOP" not in str(finish).upper():
                raise LLMError(
                    f"gemini truncated (finish_reason={finish})",
                    category="gemini_overloaded",
                )
            return response.text
        except Exception as e:
            last_err = e
            category = _categorize_gemini_error(str(e))
            logger.warning(f"gemini text attempt {attempt + 1} failed ({category}): {e}")
            if attempt < max_retries:
                time.sleep(backoff[min(attempt, len(backoff) - 1)])

    raise LLMError(
        f"gemini text failed after {max_retries + 1} attempts: {last_err}",
        category=_categorize_gemini_error(str(last_err)),
    )


def call_vertex_ai_text(
    system_prompt: str,
    user_payload: str,
    model_id: str = "gemini-2.5-flash",
    max_retries: int = 2,
) -> str:
    """Vertex AI text. Routed when settings.VERTEX_AI_CLASSIFY_ENABLED is True."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise LLMError(f"google-genai not installed: {e}", category="gemini_config")

    client = genai.Client(
        vertexai=True,
        project=settings.GCP_PROJECT_ID,
        location=settings.VERTEX_AI_LOCATION,
    )
    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            combined = system_prompt + "\n\n---\n\n" + user_payload
            response = client.models.generate_content(
                model=model_id,
                contents=combined,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            return response.text
        except Exception as e:
            last_err = e
            logger.warning(f"vertex attempt {attempt + 1} failed: {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
    raise LLMError(f"vertex failed: {last_err}", category=_categorize_gemini_error(str(last_err)))


DISCREPANCY_BATCH_SIZE = 15

_DISCREPANCY_ALLOWED_CATEGORIES = frozenset({
    "medication", "number", "name", "date", "terminology",
    "filler", "punctuation", "style", "other",
})


def _parse_gemini_json_array(raw: str) -> list[dict] | None:
    """
    Parse Gemini's response into a JSON array, stripping markdown fences if
    the model ignored the "no fences" instruction. Returns None on parse
    failure or non-list payload.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        # Drop the opening fence + optional language tag
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"_parse_gemini_json_array: failed to parse: {e}; raw={raw[:400]!r}")
        return None
    if not isinstance(parsed, list):
        logger.warning(f"_parse_gemini_json_array: expected list, got {type(parsed).__name__}")
        return None
    return parsed


def _classify_batch_once(
    batch: list[dict],
    prompt: str,
    classify_model: str,
    use_vertex: bool,
) -> list[dict] | None:
    """Single classify pass — no count validation, no missing-id retry."""
    payload = json.dumps(
        [
            {"id": str(it["id"]), "ai": it.get("ai_text", ""), "stt": it.get("stt_text", "")}
            for it in batch
        ],
        ensure_ascii=False,
    )
    backend_label = "Vertex AI Gemini" if use_vertex else "Gemini"
    try:
        if use_vertex:
            raw = call_vertex_ai_text(prompt, payload, model_id=classify_model)
        else:
            raw = call_gemini_text(prompt, payload, model_id=classify_model)
    except LLMError as e:
        logger.warning(f"_classify_batch_once: {backend_label} failed ({e.category})")
        return None

    parsed = _parse_gemini_json_array(raw)
    if parsed is None:
        return None

    out: list[dict] = []
    for r in parsed:
        if not isinstance(r, dict):
            continue
        rid = r.get("id")
        cat = r.get("category")
        mean = r.get("is_meaningful")
        if rid is None or not isinstance(mean, bool):
            continue
        if cat not in _DISCREPANCY_ALLOWED_CATEGORIES:
            cat = "other"
        out.append({"id": str(rid), "category": cat, "is_meaningful": mean})
    return out


def _classify_batch(
    batch: list[dict],
    prompt: str,
    model_id: Optional[str] = None,
    use_vertex: bool = False,
) -> list[dict] | None:
    """
    Classify a batch with count validation: if Gemini returns fewer items
    than were sent (truncation or item-skip), retry the missing ids ONCE
    before returning a partial. Items still missing after retry stay
    `is_meaningful IS NULL` in the DB and get re-picked by the next
    Celery retry / sweep.
    """
    classify_model = model_id or settings.GEMINI_CLASSIFY_MODEL
    expected_ids = {str(it["id"]) for it in batch}

    out = _classify_batch_once(batch, prompt, classify_model, use_vertex)
    if out is None:
        return None

    received_ids = {r["id"] for r in out}
    missing_ids = expected_ids - received_ids
    if missing_ids:
        logger.warning(
            f"_classify_batch: {len(missing_ids)}/{len(expected_ids)} items missing, retrying missing ids"
        )
        retry_batch = [it for it in batch if str(it["id"]) in missing_ids]
        retry_out = _classify_batch_once(retry_batch, prompt, classify_model, use_vertex)
        if retry_out:
            out.extend(retry_out)
        still_missing = expected_ids - {r["id"] for r in out}
        if still_missing:
            logger.warning(
                f"_classify_batch: {len(still_missing)} items still missing after retry; "
                "returning partial — Celery retry will re-pick these as is_meaningful IS NULL"
            )
    return out


def classify_discrepancies(
    items: list[dict],
    model_id: Optional[str] = None,
    already_classified_ids: Optional[set] = None,
    use_vertex: bool = False,
) -> list[dict] | None:
    """
    Classify word-level diffs as meaningful or noise.

    items: list of dicts with keys {id, ai_text, stt_text}
    model_id: optional Gemini model override (default settings.GEMINI_CLASSIFY_MODEL)
    already_classified_ids: set of item IDs already written to DB — skip these
    use_vertex: route through Vertex AI Gemini instead of dev Gemini

    Returns:
      - list of dicts {id, category, is_meaningful} — partial results when
        some batches fail are still returned
      - None ONLY if zero batches succeed (caller should retry whole task)

    Ports MIC `app/engines/llm_client.py:365-415`. Batching size matches
    MIC (DISCREPANCY_BATCH_SIZE=15) to keep payloads under Gemini's per-
    response truncation threshold; per-batch retry rescues missing ids
    when Gemini truncates the JSON array.
    """
    if not items:
        return []

    from app.prompts import DISCREPANCY_FILTER_PROMPT

    skip_ids = already_classified_ids or set()
    pending_items = [i for i in items if str(i["id"]) not in skip_ids]
    if not pending_items:
        logger.info("classify_discrepancies: all items already classified, skipping")
        return []

    batches = [
        pending_items[i:i + DISCREPANCY_BATCH_SIZE]
        for i in range(0, len(pending_items), DISCREPANCY_BATCH_SIZE)
    ]
    logger.info(
        f"classify_discrepancies: {len(pending_items)} pending items in {len(batches)} batch(es), "
        f"model={model_id or 'default'}, vertex={use_vertex} (skipped {len(skip_ids)} already done)"
    )

    all_results: list[dict] = []
    failed_count = 0
    for batch_idx, batch in enumerate(batches):
        logger.info(f"classify_discrepancies: batch {batch_idx + 1}/{len(batches)} ({len(batch)} items)")
        result = _classify_batch(batch, DISCREPANCY_FILTER_PROMPT, model_id=model_id, use_vertex=use_vertex)
        if result is None:
            logger.warning(f"classify_discrepancies: batch {batch_idx + 1} failed — continuing")
            failed_count += 1
            continue
        all_results.extend(result)

    if not all_results and failed_count > 0:
        logger.warning(f"classify_discrepancies: ALL {failed_count} batch(es) failed, returning None")
        return None

    if failed_count > 0:
        logger.warning(
            f"classify_discrepancies: {failed_count} batch(es) failed, "
            f"{len(all_results)} items classified (partial)"
        )
    return all_results
