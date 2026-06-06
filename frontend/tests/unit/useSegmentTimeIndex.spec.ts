/**
 * Phase 3 — useSegmentTimeIndex.
 *
 * Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 3.
 * Audit IDs closed: E22 (video → segment lookup).
 *
 * Pure-function tests; no Vue mounting needed. Run via the repo's
 * existing vitest / mocha setup or in isolation with `tsx`.
 */
import { describe, expect, it } from 'vitest';
import { ref } from 'vue';
import { useSegmentTimeIndex, type SegmentLite } from '../../src/composables/useSegmentTimeIndex';

function fixture(): SegmentLite[] {
  return [
    { id: 'a', start: 0,    end: 5 },
    { id: 'b', start: 5,    end: 10 },
    { id: 'c', start: 10.5, end: 15 },   // gap from 10 -> 10.5
    { id: 'd', start: 15,   end: 20 },
  ];
}

describe('useSegmentTimeIndex', () => {
  it('returns -1 before the first segment', () => {
    const segs = ref(fixture());
    const { index } = useSegmentTimeIndex(segs);
    expect(index.value.find(-0.5)).toBe(-1);
    expect(index.value.idAt(-0.5)).toBeNull();
  });

  it('returns -1 after the last segment', () => {
    const segs = ref(fixture());
    const { index } = useSegmentTimeIndex(segs);
    expect(index.value.find(99)).toBe(-1);
    expect(index.value.idAt(99)).toBeNull();
  });

  it('returns the correct index for a time inside a segment', () => {
    const segs = ref(fixture());
    const { index } = useSegmentTimeIndex(segs);
    expect(index.value.find(2.5)).toBe(0);
    expect(index.value.find(7)).toBe(1);
    expect(index.value.find(12)).toBe(2);
    expect(index.value.find(18)).toBe(3);
  });

  it('falls back to the preceding segment when the time is in a gap', () => {
    const segs = ref(fixture());
    const { index } = useSegmentTimeIndex(segs);
    // 10.25 is between segment b.end (10) and segment c.start (10.5).
    // Binary search settles on segment b (the preceding one) so the
    // editor keeps the last-known active segment instead of going blank.
    expect(index.value.find(10.25)).toBe(1);
    expect(index.value.idAt(10.25)).toBe('b');
  });

  it('handles boundary times (exactly at segment start)', () => {
    const segs = ref(fixture());
    const { index } = useSegmentTimeIndex(segs);
    expect(index.value.find(5)).toBe(1);  // starts of seg b
    expect(index.value.find(15)).toBe(3); // start of seg d
  });

  it('returns -1 when segments is empty', () => {
    const segs = ref<SegmentLite[]>([]);
    const { index } = useSegmentTimeIndex(segs);
    expect(index.value.find(0)).toBe(-1);
    expect(index.value.size).toBe(0);
  });

  it('rebuilds when segments reference changes', () => {
    const segs = ref<SegmentLite[]>([{ id: 'a', start: 0, end: 5 }]);
    const { index } = useSegmentTimeIndex(segs);
    expect(index.value.size).toBe(1);
    segs.value = fixture();
    // Force reactive read so computed recomputes.
    expect(index.value.size).toBe(4);
    expect(index.value.idAt(7)).toBe('b');
  });
});
