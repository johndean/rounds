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


def _categorize_gemini_error(exc_text: str) -> str:
    t = (exc_text or "").lower()
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
            logger.warning(f"gemini attempt {attempt + 1} failed: {e}")
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


def classify_discrepancies(
    system_prompt: str,
    user_payload: str,
    backend: Optional[str] = None,
    model_id: Optional[str] = None,
) -> dict:
    """
    Dispatcher: Gemini (default) or Vertex AI (when settings flag enabled).
    `backend` can override the global setting per-request (frontend
    Settings → Discrepancy classification → Vertex toggle sends
    `X-Classify-Backend: vertex` for example).

    Returns the parsed JSON object. Caller is responsible for shape validation.
    """
    use_vertex = (backend == "vertex") or (backend is None and settings.VERTEX_AI_CLASSIFY_ENABLED)
    model = model_id or settings.GEMINI_CLASSIFY_MODEL
    raw = (
        call_vertex_ai_text(system_prompt, user_payload, model_id=model)
        if use_vertex
        else call_gemini_text(system_prompt, user_payload, model_id=model)
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMError(f"classify returned invalid JSON: {e}", category="gemini_error")
