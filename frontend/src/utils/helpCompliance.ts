/**
 * frontend/src/utils/helpCompliance.ts — CC-Rounds compliance SSOT (frontend).
 *
 * Phase 4 of the Help Center port. MIRROR of app/utils/help_compliance.py.
 * The two files MUST stay byte-identical on threshold values. A backend
 * test (tests/test_help_compliance.py::test_thresholds_match_audit)
 * pins both sides to a hardcoded expected table — drift fails CI.
 *
 * See the Python file header for the rationale behind the rounds-
 * specific thresholds (looser than MIC's CC5.2 to let the smaller
 * seed corpus publish without padding).
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §9.1
 */

// ── Thresholds (LOCKED) ─────────────────────────────────────────────
export const HELP_MIN_STEPS = 3;
export const HELP_MIN_WORDS = 200;
export const HELP_SUMMARY_MIN = 180;
export const HELP_SUMMARY_MAX: number | null = null; // no max for Help

export const FAQ_MIN_STEPS = 2;
export const FAQ_MIN_WORDS = 80;
export const FAQ_SUMMARY_MIN = 60;
export const FAQ_SUMMARY_MAX = 300;

export const WORD_CEILING = 1000;

export const HELP_SUMMARY_TARGET: readonly [number, number] = [180, 400] as const;
export const FAQ_SUMMARY_TARGET: readonly [number, number] = [120, 280] as const;

// ── Types ───────────────────────────────────────────────────────────
export interface ComplianceInput {
  category?: string | null;
  summary?: string | null;
  steps?: ReadonlyArray<{ title?: string; body?: string } | string> | null;
}

export interface ComplianceResult {
  isFaq:      boolean;
  wordCount:  number;
  summaryLen: number;
  stepCount:  number;
  wordsOk:    boolean;
  summaryOk:  boolean;
  stepsOk:    boolean;
  allPass:    boolean;
  pct:        number;
}

/** SSOT predicate. Frontend mirror of ``is_faq_category`` in Python. */
export function isFaqCategory(category: string | null | undefined): boolean {
  return (category || '').toLowerCase().includes('faq');
}

export function computeCompliance(article: ComplianceInput): ComplianceResult {
  const category = article.category ?? '';
  const summary = article.summary ?? '';
  const steps = article.steps ?? [];

  let wordCount = 0;
  for (const s of steps) {
    const body = typeof s === 'string' ? '' : (s.body ?? '');
    wordCount += body.split(/\s+/).filter((w) => w.length > 0).length;
  }

  const stepCount = steps.length;
  const summaryLen = summary.length;
  const isFaq = isFaqCategory(category);

  let wordsOk: boolean;
  let summaryOk: boolean;
  let stepsOk: boolean;

  if (isFaq) {
    wordsOk = wordCount >= FAQ_MIN_WORDS;
    summaryOk = summaryLen >= FAQ_SUMMARY_MIN && summaryLen <= FAQ_SUMMARY_MAX;
    stepsOk = stepCount >= FAQ_MIN_STEPS;
  } else {
    wordsOk = wordCount >= HELP_MIN_WORDS;
    if (HELP_SUMMARY_MAX === null) {
      summaryOk = summaryLen >= HELP_SUMMARY_MIN;
    } else {
      summaryOk = summaryLen >= HELP_SUMMARY_MIN && summaryLen <= HELP_SUMMARY_MAX;
    }
    stepsOk = stepCount >= HELP_MIN_STEPS;
  }

  const allPass = wordsOk && summaryOk && stepsOk;
  const pct = Math.min(100, Math.round((wordCount / WORD_CEILING) * 100));

  return { isFaq, wordCount, summaryLen, stepCount, wordsOk, summaryOk, stepsOk, allPass, pct };
}
