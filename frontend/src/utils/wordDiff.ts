/**
 * wordDiff — token-level diff between two strings via LCS.
 *
 * Used by DecisionCard to highlight only the changed words inside a long
 * paragraph (WAS / NOW panels) instead of wrapping the whole segment in a
 * single <s>/<mark>. Pure utility; no deps; safe to unit-test.
 *
 * Tokenization preserves whitespace so the rendered output reads naturally:
 *   "we can avoid that" → ["we", " ", "can", " ", "avoid", " ", "that"]
 *
 * Complexity is O(m·n) on token counts; paragraphs of ~150 words run in <10ms.
 */

export type DiffKind = 'same' | 'removed' | 'added';

export interface DiffToken {
  text: string;
  kind: DiffKind;
}

function tokenize(s: string): string[] {
  return s.split(/(\s+)/).filter((t) => t.length > 0);
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * Word-level diff. Returns parallel token streams for the WAS and NOW panels.
 * `was` contains tokens flagged `same` or `removed`. `now` contains `same` or `added`.
 */
export function wordDiff(oldText: string, newText: string): { was: DiffToken[]; now: DiffToken[] } {
  const a = tokenize(oldText);
  const b = tokenize(newText);
  const m = a.length;
  const n = b.length;

  // LCS DP table
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i]![j] = a[i - 1] === b[j - 1] ? dp[i - 1]![j - 1]! + 1 : Math.max(dp[i - 1]![j]!, dp[i]![j - 1]!);
    }
  }

  // Backtrack to build the parallel diff streams
  const was: DiffToken[] = [];
  const now: DiffToken[] = [];
  let i = m;
  let j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      was.unshift({ text: a[i - 1]!, kind: 'same' });
      now.unshift({ text: b[j - 1]!, kind: 'same' });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i]![j - 1]! >= dp[i - 1]![j]!)) {
      now.unshift({ text: b[j - 1]!, kind: 'added' });
      j--;
    } else if (i > 0) {
      was.unshift({ text: a[i - 1]!, kind: 'removed' });
      i--;
    }
  }

  return { was, now };
}

/**
 * Render a diff stream to HTML. Non-diff tokens are HTML-escaped; diff tokens
 * are wrapped in <s> / <mark> with the provided class names.
 */
export function diffToHtml(
  tokens: readonly DiffToken[],
  removedClass: string,
  addedClass: string,
): string {
  return tokens
    .map((t) => {
      const safe = escapeHtml(t.text);
      if (t.kind === 'removed') return `<s class="${removedClass}">${safe}</s>`;
      if (t.kind === 'added') return `<mark class="${addedClass}">${safe}</mark>`;
      return safe;
    })
    .join('');
}
