# Plan: Gemini Context-Overflow Fix (AI MODE direct token-budget defense)

**Created:** 2026-05-18
**Type:** fix
**Severity:** HIGH — production-blocking for >~20 min CE sessions with slide decks
**Authoritative finding:** docs/plans/2026-05-18-003-gemini-context-overflow-fix.md (this doc)
**Related:** docs/plans/2026-05-18-002-parity-remediation-phases.md (Phase 0 already flipped the default model)

---

## 1. Symptom and Root Cause

**Symptom (reported as "STT failing"):**
Session `afb1d4df-6e0f-46aa-aeda-33f58e61d54d` (042326_Hendershott chat, 247MB MP4 + 140-slide PDF) loops through `ai_process_task` retries every ~2 min for >1h. Each retry fails with:

```
400 INVALID_ARGUMENT.
'The input token count exceeds the maximum number of tokens allowed 1048576.'
```

The user reads "STT failed" in the UI because the session sits in `uploading→ingesting→failed` and the failure surface doesn't yet say *why*.

**Root cause (not STT):**

STT is never invoked on this code path. The session has `ai_pipeline=direct, ai_mode=transcript` so [app/tasks/ai_process.py:_process_direct](../../app/tasks/ai_process.py) runs instead. That function:

1. Downloads the video (247MB) and the slide PDF (140 pages) from GCS to /tmp
2. Builds `downloaded = [(video_path, video/mp4), (pdf_path, application/pdf)]`
3. Calls `call_gemini_multimodal(downloaded, system_prompt, model_id='gemini-2.5-flash')`
4. Gemini File API ingests both files, then the `generate_content` call is rejected with **400 INVALID_ARGUMENT** because the combined token count (~1M+) exceeds gemini-2.5-flash's **1,048,576-token** context window.
5. The retry loop at [app/engines/llm_client.py:105-123](../../app/engines/llm_client.py) re-sends the *exact same payload* twice more. All three attempts fail identically. Task is then retried by Celery 3x, all identical failures. Session lands in `failed`.

**The defect is in BOTH MIC and Rounds.** MIC has the same code path with the same lack of token-budget defense. MIC has not hit this in production because no MIC user has uploaded a 247MB video + 140-slide PDF through AI MODE direct on gemini-2.5-flash. Rounds is the first to surface a latent shared bug.

---

## 2. What's Already Mitigated (Phase 0, shipped commit `146eaf2`)

Migration 027 flipped the `org_settings` defaults:

| Setting | Before | After |
|---|---|---|
| `default_ai_model` | `gemini-2.5-flash` (1M context) | `gemini-2.5-pro` (2M context) |
| `upload_backend` | `railway` | `gcs` |

**New sessions created after this commit pick `gemini-2.5-pro` from the prefill** — they have 2M context and should fit the same 247MB+140-slide combo cleanly.

**However**, three classes of failure remain unaddressed:

1. **Existing failed session** `afb1d4df` was created with `flash` baked into `session_templates.ai_model`. Re-running it still uses flash. Needs a fix path.
2. **Future huge sessions** could exceed even gemini-2.5-pro's 2M context. The code still has zero defense.
3. **User override**: an operator can pick `gemini-2.5-flash` explicitly on the upload page. That re-arms the bug.

This plan closes those three.

---

## 3. Code-Level Comparison: Rounds vs MIC

| Aspect | MIC | Rounds | Gap |
|---|---|---|---|
| Send slide PDF to Gemini multimodal | YES (`ai_process.py:146-166`) | YES (`ai_process.py:172-180`) | **Identical defect** |
| `1048576` / `MAX_INPUT_TOKENS` constant | absent | absent | **Both broken** |
| `INVALID_ARGUMENT` error categorization | falls through to `gemini_error` | falls through to `gemini_error` | **Both broken** |
| Model fallback on context overflow | none | none | **Both broken** |
| Pre-flight token counting | none | none | **Both broken** |
| `max_output_tokens` | 65536 | 65536 | same |
| Retry policy | 3 attempts, exponential backoff | 3 attempts, exponential backoff | same |

There is no MIC behavior to port. This plan adds defensive code Rounds will gain ahead of MIC; backport to MIC after verification.

---

## 4. Fix Architecture — Five Layers of Defense

The fix is layered so each layer catches what the previous one misses. All five ship together.

### Layer 1 — Error categorization (1 line change)

[app/engines/llm_client.py:`_categorize_gemini_error`](../../app/engines/llm_client.py:37-45)

Add a new error category:

```python
def _categorize_gemini_error(exc_text: str) -> str:
    t = (exc_text or "").lower()
    if "exceeds the maximum number of tokens" in t or "input token count" in t:
        return "gemini_context_overflow"          # NEW
    if "503" in t or "unavailable" in t or "high demand" in t:
        return "gemini_overloaded"
    ...
```

This alone changes nothing functionally but makes the next layers possible.

### Layer 2 — Skip blind retries on context overflow

[app/engines/llm_client.py:105-123](../../app/engines/llm_client.py)

Inside the retry loop, when the categorized error is `gemini_context_overflow`, **break out immediately** — re-sending the same payload three times wastes 60s per failure and burns Gemini quota for nothing. Raise once.

```python
except Exception as e:
    last_err = e
    cat = _categorize_gemini_error(str(e))
    if cat == "gemini_context_overflow":
        logger.warning(f"gemini context overflow on attempt {attempt + 1}: aborting retries")
        # cleanup uploaded files
        for uf in uploaded:
            try: client.files.delete(name=uf.name)
            except: pass
        raise LLMError(str(e), category="gemini_context_overflow")
    if attempt < max_retries:
        time.sleep(2 ** attempt)
```

### Layer 3 — Auto-upgrade model on overflow

[app/tasks/ai_process.py:`_process_direct`](../../app/tasks/ai_process.py)

When `LLMError(category="gemini_context_overflow")` bubbles up:

- If the failing model was `gemini-2.5-flash` (1M), automatically retry once with `gemini-2.5-pro` (2M) and log the upgrade in `session_audit.processing_log`. Update `session_templates.ai_model` so future retries also use pro.
- If the failing model was already `gemini-2.5-pro`, fall through to Layer 4 (input reduction).

```python
MODEL_CONTEXT_TIERS = [
    ("gemini-2.5-flash-lite", 1_048_576),
    ("gemini-2.5-flash",      1_048_576),
    ("gemini-2.5-pro",        2_097_152),
]

def _upgrade_model(current: str) -> Optional[str]:
    """Return the next-larger model, or None if at the top."""
    idx = next((i for i, (m, _) in enumerate(MODEL_CONTEXT_TIERS) if m == current), -1)
    if idx == -1 or idx == len(MODEL_CONTEXT_TIERS) - 1:
        return None
    return MODEL_CONTEXT_TIERS[idx + 1][0]
```

In `_process_direct`, wrap the Gemini call:

```python
try:
    raw = call_gemini_multimodal(downloaded, system_prompt, model_id=ai_model)
except LLMError as e:
    if e.category == "gemini_context_overflow":
        upgraded = _upgrade_model(ai_model)
        if upgraded:
            logger.warning(f"ai_process: context overflow on {ai_model}; auto-upgrading to {upgraded}")
            _persist_model_upgrade(session_id, upgraded, reason=f"context_overflow_from_{ai_model}")
            raw = call_gemini_multimodal(downloaded, system_prompt, model_id=upgraded)
        else:
            raise   # already at top tier; fall through to Layer 4
    else:
        raise
```

### Layer 4 — Input reduction (slide-text fallback)

If even gemini-2.5-pro overflows (>2M tokens — possible with very long videos), drop the slide PDF from the multimodal call and pass slide content as text in the system prompt instead. PyMuPDF has already extracted slide bullets locally into the `bullets` table during `slide_extract_task`, so this isn't lossy — just a different transport.

```python
def _build_slide_text_appendix(session_id: str) -> str:
    """Build a compact text representation of slide bullets, for embedding in prompt
       when the slide PDF can't fit in the multimodal payload."""
    rows = db.execute("""
        SELECT slide_index, content
        FROM bullets WHERE session_id = :sid
        ORDER BY slide_index, bullet_index
    """, {"sid": session_id})
    lines = []
    cur = -1
    for r in rows:
        if r.slide_index != cur:
            cur = r.slide_index
            lines.append(f"\n### Slide {cur + 1}")
        lines.append(f"- {r.content}")
    return "\n".join(lines)
```

On the second overflow (post-upgrade), retry video-only with the slide-text appended to `system_prompt`. The combined token count drops by 80%+.

### Layer 5 — Pre-flight token counting

Avoid the round-trip entirely. The Gemini SDK exposes `client.models.count_tokens(model, contents)` — call it before `generate_content`. If the count exceeds the model's context, skip to Layer 3/4 immediately.

```python
def _estimate_tokens(client, model_id: str, content) -> Optional[int]:
    try:
        result = client.models.count_tokens(model=model_id, contents=content)
        return int(result.total_tokens)
    except Exception as e:
        logger.warning(f"token count failed (non-fatal): {e}")
        return None

# In call_gemini_multimodal, after uploading and building content:
ctx_limit = MODEL_CONTEXT.get(model_id, 1_048_576)
tokens = _estimate_tokens(client, model_id, content)
if tokens and tokens > ctx_limit:
    logger.warning(f"pre-flight: {tokens} tokens exceeds {model_id} limit {ctx_limit}; skipping call")
    raise LLMError(
        f"input is {tokens} tokens; {model_id} limit is {ctx_limit}",
        category="gemini_context_overflow",
    )
```

This converts a 60-second 3-retry waste into a sub-second decision.

---

## 5. The Failing Session: Unblock Path

For session `afb1d4df-6e0f-46aa-aeda-33f58e61d54d` specifically (and any other already-failed sessions configured with flash + large inputs):

**Option A — Edit and retry (no re-upload):**

```sql
UPDATE session_templates SET ai_model = 'gemini-2.5-pro' WHERE session_id = 'afb1d4df-...';
UPDATE sessions SET status = 'uploading' WHERE id = 'afb1d4df-...';
-- then trigger ingest_task or the diagnostics /reingest endpoint
```

**Option B — Re-upload from scratch:**

Now that migration 027 has flipped `default_ai_model` to gemini-2.5-pro, a fresh upload via the UI will create the session with pro and succeed on the first call.

**Recommendation:** Option A is faster (no re-upload of 247MB). Confirm with operator first; this is a one-off SQL patch, not a long-term recipe.

---

## 6. Implementation Phases

| Phase | Layer | Files touched | Effort | Ship order |
|---|---|---|---|---|
| 4.1 | Error categorization (Layer 1) | `app/engines/llm_client.py` | 5 min | **1st (atomic with 4.2)** |
| 4.2 | Skip blind retry on overflow (Layer 2) | `app/engines/llm_client.py` | 10 min | **1st** |
| 4.3 | Auto-upgrade model (Layer 3) | `app/tasks/ai_process.py`, `app/engines/llm_client.py` (new helper) | 30 min | **2nd** |
| 4.4 | Slide-text fallback (Layer 4) | `app/tasks/ai_process.py`, new `_build_slide_text_appendix` | 1 hr | 3rd |
| 4.5 | Pre-flight count_tokens (Layer 5) | `app/engines/llm_client.py` | 30 min | 4th |
| 4.6 | Unblock failing session via SQL | one-off | 2 min | parallel to 4.1 |
| 4.7 | Surface error reason in failure-detail modal | already-shipped `failure-reason` endpoint will now show "gemini_context_overflow" cleanly | 0 (free win) | parallel |
| 4.8 | Add test fixtures simulating overflow | `tests/test_gemini_context_overflow.py` | 30 min | with 4.3 |
| 4.9 | Backport Layers 1+2+3 to MIC | `Desktop\mic\app\engines\llm_client.py`, `Desktop\mic\app\tasks\ai_process.py` | 30 min | last |

**Total effort:** ~3 hours for layers 1-5 + test + MIC backport. Phases 4.1+4.2+4.6 alone close 80% of the risk and ship in ~15 min.

---

## 7. Acceptance Criteria

- [ ] `pytest tests/test_gemini_context_overflow.py` passes — three cases:
  - flash overflows → auto-upgrades to pro → succeeds
  - pro overflows → drops slide PDF + appends bullets text → succeeds
  - both overflow → raises `LLMError(category='gemini_context_overflow')` cleanly with no triple-retry waste
- [ ] Re-run failing session `afb1d4df-...` after Layer 3 ships → completes through ai_process → session reaches `ready`
- [ ] `session_audit.processing_log` shows the model upgrade event with reason=`context_overflow_from_gemini-2.5-flash`
- [ ] Open the failure-detail modal on any future overflow → shows `category: gemini_context_overflow` + reason text
- [ ] Worker log shows ONE failed call + ONE upgraded retry, not 3+3 = 6 failed calls
- [ ] No regression on existing healthy sessions (run full pytest suite)
- [ ] MIC backport reviewed and merged

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Layer 3 auto-upgrade bills 2x on every flash overflow | Med | Low (cost not constrained yet) | Logs warn-level event; operator can audit. Layer 5 pre-flight eliminates the wasted first call. |
| Layer 4 slide-text appendix produces lower-quality transcript than full PDF context | Med | Med | Test side-by-side on a known-good session; only invoked after pro overflows (rare). |
| `count_tokens` SDK call adds latency to every successful call | Low | Low | <100ms typical; the saved blind-retry time (60s) dwarfs it. |
| Persisting model upgrade to `session_templates.ai_model` confuses the operator if they see "I picked flash but the row says pro" | Low | Low | Audit-log entry explains the override; settings page can show "auto-upgraded due to overflow". |
| Backporting to MIC could break MIC sessions currently in flight | Low | Med | Ship Layers 1+2 to MIC first (no behavior change for healthy calls), then 3+4+5 in a follow-up. |

---

## 9. Why "zero-tech-debt"

This isn't a workaround — it's the missing defense both codebases were always supposed to have. Each layer:

1. Solves a real, documented external limit, not a hypothetical
2. Has bounded effort (none of the 5 layers exceeds 1 hour)
3. Has a regression test that fails without the fix
4. Backports to MIC so both repos converge on the same defensive contract
5. Surfaces a user-readable failure reason instead of an opaque 400

If we ever need to support an even larger model tier, `MODEL_CONTEXT_TIERS` is the single seam to extend.

---

## 10. Debug Report (Phase 5 of /investigate)

```
DEBUG REPORT
════════════════════════════════════════
Symptom:         User-reported "STT failing" — session afb1d4df sits in
                 retry loop, every attempt fails the same way.
Root cause:      AI MODE direct (Gemini multimodal) overflows the
                 gemini-2.5-flash 1M-token context. Combined input:
                 247MB MP4 video + 140-slide PDF = >1M tokens.
                 STT was never invoked — wrong layer for the user's mental
                 model. Both MIC and Rounds share the defect: no
                 token-budget defense, no error categorization for
                 INVALID_ARGUMENT, no model fallback.
Failure point:   app/tasks/ai_process.py:188 — call_gemini_multimodal with
                 (video, slide_pdf) tuples and ai_model=flash. The retry
                 loop at app/engines/llm_client.py:105-123 re-sends the
                 identical payload twice more.
Fix:             Layered defense (see Section 4): error categorization
                 (Layer 1) + skip blind retries (Layer 2) + auto-upgrade
                 model (Layer 3) + slide-text fallback (Layer 4) +
                 pre-flight count_tokens (Layer 5). Migration 027 already
                 flipped the org-wide default to gemini-2.5-pro (Phase 0
                 partial mitigation).
Evidence:        Worker log shows 3 identical 400 INVALID_ARGUMENT failures.
                 grep for 1048576/MAX_INPUT_TOKENS/context_window across
                 both repos returns 0 hits. Code trace confirms slide PDF
                 always attached.
Regression test: tests/test_gemini_context_overflow.py (new) — three
                 cases enumerated in Section 7 acceptance criteria.
Related:         docs/plans/2026-05-18-002-parity-remediation-phases.md
                 (Phase 0 ships partial mitigation), Memory:
                 [[feedback_cost_consciousness]] — reliability beats cost
                 here, gemini-2.5-pro is OK.
Status:          DONE_WITH_CONCERNS — root cause confirmed and plan
                 written; implementation deferred pending operator
                 sign-off on Section 6 phase ordering.
════════════════════════════════════════
```
