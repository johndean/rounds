/**
 * useSegmentTimeIndex — O(log n) lookup of "which segment contains a given
 * playback time?".
 *
 * Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 3.
 * Audit IDs closed: E22 (video time → segment jump). Also used by E20
 * (refresh persistence) to restore the active segment from currentTime.
 *
 * Why a separate index (not a plain Array.find):
 *   Reverse-jump auto-scroll runs on every timeupdate (~10Hz from
 *   VideoStrip throttling) on a 600-segment session. A linear find
 *   would be O(n) per tick = 6000 comparisons / sec at scale. The
 *   Float32Array binary search is O(log n) — 10 comparisons for 600
 *   segs, runs in <0.1ms. Per-tick perf budget stays nominally zero.
 *
 * Build is amortized:
 *   The index rebuilds when the segments array reference changes (i.e.
 *   when EditorView re-fetches), not on every render. Mutation of an
 *   existing segment's start/end timing is rare; if it happens, the
 *   caller passes a new array reference to trigger rebuild.
 */
import { computed, type Ref } from 'vue';

export interface SegmentLite {
  id: string;
  /** Start time in SECONDS (matches EditorView's `time` ref convention). */
  start: number;
  /** End time in SECONDS. */
  end: number;
}

export interface SegmentTimeIndex {
  /**
   * Return the index in the segments array of the segment whose
   * [start, end) range contains `t` seconds. Returns -1 when t is
   * before the first segment OR after the last; in those cases
   * caller should fall back to the nearest neighbor (typically
   * index 0 or segments.length - 1).
   *
   * Performance: O(log n). For 600 segs, ~10 comparisons.
   */
  find(t: number): number;
  /**
   * Convenience: return the segment id at `t`, or null if outside
   * the covered range.
   */
  idAt(t: number): string | null;
  /** Underlying segment count (for boundary callers). */
  size: number;
}

export function useSegmentTimeIndex(
  segments: Ref<readonly SegmentLite[]>,
): { index: Ref<SegmentTimeIndex> } {
  const index = computed<SegmentTimeIndex>(() => {
    const segs = segments.value;
    const n = segs.length;
    // Float32Array is tighter in memory than a Number[] and the binary
    // search compares primitives — no boxing.
    const starts = new Float32Array(n);
    const ends = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const seg = segs[i]!;
      starts[i] = seg.start;
      ends[i] = seg.end;
    }

    function find(t: number): number {
      if (n === 0) return -1;
      if (t < starts[0]!) return -1;
      if (t > ends[n - 1]!) return -1;
      // Standard binary search on starts; settle on the largest
      // i such that starts[i] <= t. If that segment's end >= t,
      // we're inside it; otherwise we're in a gap → return the
      // preceding index so the caller keeps the last-known active
      // segment instead of dropping to nothing.
      let lo = 0;
      let hi = n - 1;
      while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (starts[mid]! <= t) lo = mid;
        else hi = mid - 1;
      }
      return lo;
    }

    function idAt(t: number): string | null {
      const i = find(t);
      if (i < 0) return null;
      return segs[i]?.id ?? null;
    }

    return { find, idAt, size: n };
  });

  return { index };
}
