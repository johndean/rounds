/**
 * SLIDE_PALETTE — IMPLEMENTATION.md §4.
 * 10-color array, indexed by (slide_index % 10). Precomputed Map for O(1) lookup (P18).
 *
 * Applied to: slide-rail row tints · segment 3px left stripe · slide-chip dots ·
 *             AI/STT/Discrepancies/Audit segment chrome · minimap rects ·
 *             ActiveSlide card border + gradient · Session Detail timeline strip +
 *             slide-assignment list + per-segment confidence dots.
 */

export const SLIDE_PALETTE = Object.freeze([
  '#2563eb', // 0
  '#7c3aed', // 1
  '#059669', // 2
  '#d97706', // 3
  '#dc2626', // 4
  '#0891b2', // 5
  '#6366f1', // 6
  '#ea580c', // 7
  '#0d9488', // 8
  '#be185d', // 9
]) as readonly string[];

const _cache = new Map<number, string>();
for (let i = 0; i < SLIDE_PALETTE.length; i++) _cache.set(i, SLIDE_PALETTE[i]!);

/** Returns the slide accent color for a 0-based slide index. */
export function colorForSlide(index: number): string {
  const key = ((index % SLIDE_PALETTE.length) + SLIDE_PALETTE.length) % SLIDE_PALETTE.length;
  return _cache.get(key)!;
}

/**
 * 3-branch nav style helper (IMPLEMENTATION.md §6 slide rail):
 *   - active: full accent bg + 100% border + 3px inset stripe
 *   - empty:  0.55 opacity + 33% stripe
 *   - normal: 12% bg + 44% border + 100% stripe
 */
export type SlideNavState = 'active' | 'empty' | 'normal';

export function slideRailStyle(index: number, state: SlideNavState): Record<string, string> {
  const accent = colorForSlide(index);
  switch (state) {
    case 'active':
      return {
        '--slide-bg':    accent,
        '--slide-border': accent,
        '--slide-stripe': accent,
        '--slide-opacity': '1',
        '--slide-stripe-opacity': '1',
      };
    case 'empty':
      return {
        '--slide-bg':    'transparent',
        '--slide-border': hexWithAlpha(accent, 0.44),
        '--slide-stripe': hexWithAlpha(accent, 0.33),
        '--slide-opacity': '0.55',
        '--slide-stripe-opacity': '0.33',
      };
    case 'normal':
    default:
      return {
        '--slide-bg':    hexWithAlpha(accent, 0.12),
        '--slide-border': hexWithAlpha(accent, 0.44),
        '--slide-stripe': accent,
        '--slide-opacity': '1',
        '--slide-stripe-opacity': '1',
      };
  }
}

function hexWithAlpha(hex: string, alpha: number): string {
  // Expand short hex if needed
  const h = hex.replace('#', '').padEnd(6, '0');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
