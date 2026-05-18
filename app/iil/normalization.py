"""
IIL Normalization Engine — verbatim port of MIC `app/iil/normalization.py`.

Three-tier rule-based normalize with these locked rules (Section 24):

  RULE 0 — SSOT PROTECTION: words[] is immutable. Engine reads only.
  RULE 1 — DUAL STORAGE: raw_text and normalized_text stored in parallel.
  RULE 2 — NO HALLUCINATION: output contains ONLY words from words[].
  RULE 3 — TECHNICAL TERM PROTECTION: domain terms from slide bullets/full_text
           never removed (cross-checked at every tier).
  RULE 4 — FAIL-SAFE: any exception → return raw_text unchanged, log failure.
  RULE 5 — TIER 1: um/uh/er/ah/umm/uhh/hmm — ALWAYS remove (gated by tier1 flag).
  RULE 6 — TIER 2: discourse markers — KEEP by default, conditional remove with
           confidence threshold + first-word + domain + context guards.
  RULE 7 — TIER 3: structural phrases — COMPRESS (remove phrase, keep following).
  RULE 8 — IDEMPOTENCE: same input + same config → same output.

The output `NormalizedResult` carries an audit trail per segment (tier1_removed,
tier2_removed, tier2_kept with reasons, tier3_compressed) — this becomes the
JSONB blob in `normalization_results.validation_results`.

Phase 7c. Closes residual 🟠 (Rounds' normalize was simple word substitution
without RULE 3 protection / TIER 2 conditional logic / TIER 3 compression).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Locked word lists (Section 24) ────────────────────────────────────


TIER1_WORDS = frozenset(["um", "uh", "er", "ah", "umm", "uhh", "hmm"])

TIER2_WORDS = frozenset([
    "basically", "right", "you know", "like", "okay", "so",
    "well", "i mean", "sort of", "kind of",
])

TIER3_PATTERNS = [
    "the thing is",
    "what i want to say is",
    "if you think about it",
]


# ─── Output dataclasses ────────────────────────────────────────────────


@dataclass
class NormalizedResult:
    segment_id: str
    raw_text: str
    normalized_text: str
    filler_count: int
    compression_ratio: float
    tier1_removed: list[str] = field(default_factory=list)
    tier2_removed: list[str] = field(default_factory=list)
    tier2_kept: list[dict] = field(default_factory=list)
    tier3_compressed: list[dict] = field(default_factory=list)
    repair_applied: bool = False
    repair_attempts: int = 0
    validation_checks: dict = field(default_factory=dict)


# ─── Helpers ───────────────────────────────────────────────────────────


def _get_domain_terms(slide_context: str) -> frozenset[str]:
    """Lowercase tokens from slide bullets/full_text — never removed."""
    return frozenset(w.lower() for w in (slide_context or "").split() if len(w) > 2)


def _is_first_word(idx: int) -> bool:
    return idx == 0


def _context_depends_on(idx: int, words: list[str]) -> bool:
    """Heuristic — conservative `keep` at segment boundaries."""
    return idx == 0 or idx == len(words) - 1


# ─── Public entry ──────────────────────────────────────────────────────


def normalize(
    segment_id: str,
    words: list[dict],
    template_config: dict,
    slide_context: str = "",
    iil_config: Optional[dict] = None,
) -> NormalizedResult:
    """
    Run the 3-tier normalize. Never modifies `words[]`. RULE 4: returns
    raw_text unchanged on any exception.

    `words` items must carry `.word`. Time fields are tolerated but not
    used here — the segmenter already determined boundaries.

    `template_config` keys:
      filler_policy  ('light' | 'moderate' | 'strict')
      structure_extraction / key_points / tone / terminology / rewrite — reserved
    """
    raw_text = " ".join(w.get("word", "") for w in words)
    cfg = iil_config or {}

    # Master OFF — return raw, no tiers run.
    if cfg.get("enabled", True) is False:
        return NormalizedResult(
            segment_id=segment_id,
            raw_text=raw_text,
            normalized_text=raw_text,
            filler_count=0,
            compression_ratio=1.0,
        )

    try:
        return _normalize_internal(segment_id, words, raw_text, template_config, slide_context, cfg)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"IIL normalize failed for {segment_id}: {exc}", exc_info=True)
        return NormalizedResult(
            segment_id=segment_id,
            raw_text=raw_text,
            normalized_text=raw_text,
            filler_count=0,
            compression_ratio=1.0,
        )


def _normalize_internal(
    segment_id: str,
    words: list[dict],
    raw_text: str,
    template_config: dict,
    slide_context: str,
    cfg: dict,
) -> NormalizedResult:
    filler_policy = template_config.get("filler_policy", "strict")
    domain_terms = _get_domain_terms(slide_context)

    tier1_on = cfg.get("tier1", True) is not False
    tier2_on = cfg.get("tier2", True) is not False
    tier3_on = cfg.get("tier3", True) is not False

    word_strings = [w.get("word", "") for w in words]
    output: list[str] = []
    tier1_removed: list[str] = []
    tier2_removed: list[str] = []
    tier2_kept: list[dict] = []
    tier3_compressed: list[dict] = []

    i = 0
    while i < len(word_strings):
        word = word_strings[i]
        word_lower = word.lower().rstrip(".,?!")

        # RULE 3 — domain term protection (applies before any tier)
        if word_lower in domain_terms:
            output.append(word)
            i += 1
            continue

        # TIER 3 — structural phrase compression (skipped under filler_policy=light)
        if tier3_on and filler_policy != "light":
            matched = False
            for pattern in TIER3_PATTERNS:
                pwords = pattern.split()
                plen = len(pwords)
                if i + plen <= len(word_strings):
                    slice_lower = " ".join(w.lower().rstrip(".,?!") for w in word_strings[i:i + plen])
                    if slice_lower == pattern:
                        tier3_compressed.append({
                            "original":   " ".join(word_strings[i:i + plen]),
                            "compressed": "",
                            "position":   i,
                        })
                        i += plen
                        matched = True
                        break
            if matched:
                continue

        # TIER 1 — acoustic fillers, always remove when tier1 enabled
        if tier1_on and word_lower in TIER1_WORDS:
            tier1_removed.append(word)
            i += 1
            continue

        # TIER 2 — discourse markers, conditional
        tier2_hit = False
        if tier2_on:
            for phrase in sorted(TIER2_WORDS, key=len, reverse=True):
                pwords = phrase.split()
                plen = len(pwords)
                if i + plen > len(word_strings):
                    continue
                slice_lower = " ".join(w.lower().rstrip(".,?!") for w in word_strings[i:i + plen])
                if slice_lower != phrase:
                    continue

                if filler_policy == "light":
                    output.extend(word_strings[i:i + plen])
                    tier2_kept.append({"phrase": phrase, "reason": "filler_policy=light"})
                    i += plen
                    tier2_hit = True
                    break

                is_first = _is_first_word(i)
                is_domain = any(w.lower() in domain_terms for w in pwords)
                ctx_dep = _context_depends_on(i, word_strings)

                threshold = 0.85 if filler_policy == "moderate" else 0.70
                remove_conf = 0.75 if not (is_first or is_domain or ctx_dep) else 0.30

                if not is_first and not is_domain and not ctx_dep and remove_conf > threshold:
                    tier2_removed.append(phrase)
                    logger.debug(f"T2 REMOVE: '{phrase}' seg={segment_id} conf={remove_conf:.2f}")
                else:
                    output.extend(word_strings[i:i + plen])
                    reason = (
                        "first_word" if is_first
                        else "domain_term" if is_domain
                        else "context_dependent" if ctx_dep
                        else f"confidence_below_threshold({remove_conf:.2f}<{threshold})"
                    )
                    tier2_kept.append({"phrase": phrase, "reason": reason})

                i += plen
                tier2_hit = True
                break

        if tier2_hit:
            continue

        # Default — keep word
        output.append(word)
        i += 1

    normalized_text = " ".join(output).strip()
    filler_count = len(tier1_removed) + len(tier2_removed)
    compression_ratio = round(len(normalized_text) / len(raw_text), 4) if raw_text else 1.0

    return NormalizedResult(
        segment_id=segment_id,
        raw_text=raw_text,
        normalized_text=normalized_text or raw_text,  # RULE 4 fallback
        filler_count=filler_count,
        compression_ratio=compression_ratio,
        tier1_removed=tier1_removed,
        tier2_removed=tier2_removed,
        tier2_kept=tier2_kept,
        tier3_compressed=tier3_compressed,
    )
