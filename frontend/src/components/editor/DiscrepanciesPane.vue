<script setup lang="ts">
/**
 * DiscrepanciesPane — side-by-side AI Transcript ↔ STT Raw with inline diff
 * highlighting, classified by category and "meaningful vs noise."
 *
 * Two render paths:
 *   • LIVE (real session): props.liveSegments + props.liveDiscrepancies +
 *     optional props.liveWords. The AI column shows the real segment text;
 *     the STT column joins real Google STT words per segment; both highlight
 *     real per-segment ai_text/stt_text diff fragments from
 *     transcription_discrepancies. Counts/filters/categories come from the
 *     real backend rows.
 *   • FIXTURE-DEMO (prototype.html): no props → falls through to the
 *     original fixture SEGMENTS + DISCREPANCIES + AI-text-as-STT path so
 *     the React-port demo keeps rendering identically.
 *
 * Related ADRs: ADR-005 (corrections — Mark OK + Dismiss write corrections).
 * Related business rules: BR-006 (priority scoring drives row order),
 * BR-018 (Mark OK auto-closes discrepancies on the same segment).
 */
import { computed, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import SegmentText from '@/components/editor/SegmentText.vue';
import {
  slideAccent,
  speakerDisplay,
  type Segment,
  type Slide,
} from '@/fixtures/transcript';
import type { DiscrepancyRow, WordRow } from '@/services/api';
import { corrections as correctionsApi } from '@/services/api';
import { withAlpha, fmtTime } from '@/utils/editorHelpers';
import { toast } from '@/composables/useToast';
import { ApiError } from '@/services/http';

const props = defineProps<{
  activeSegmentId: string | null | undefined;
  focusedSlideId: string | null;
  slideRailMode: 'focus' | 'filter';
  liveSegments?: readonly Segment[];
  liveSlides?: readonly Slide[];
  liveDiscrepancies?: readonly DiscrepancyRow[];
  liveWords?: Map<string, WordRow[]>;
  sessionId: string;
}>();

const emit = defineEmits<{
  (e: 'segmentClick', id: string): void;
  (e: 'clearFocus'): void;
  (e: 'requestEdit', segmentId: string): void;
  (e: 'discrepancyResolved', segmentId: string): void;
}>();

// Track per-segment in-flight rescue so the operator can't double-fire.
const resolving = ref<Set<string>>(new Set());

// Phase B1 — Mark OK closes any discrepancies attached to this segment
// because mark_ok ∈ CLOSES_DISCREPANCY_TYPES (app/api/corrections.py:49).
// Optimistic: emit discrepancyResolved so the parent removes this segment
// from the discrepancies array immediately; revert by re-emitting on error
// (parent re-fetches).
async function onMarkOk(seg: Segment, dismiss = false): Promise<void> {
  if (resolving.value.has(seg.id)) return;
  resolving.value.add(seg.id);
  try {
    await correctionsApi.apply(props.sessionId, {
      segment_id:      seg.id,
      correction_type: 'mark_ok',
      old_text:        '',
      new_text:        '',
      ...(dismiss ? { note: 'dismissed' } : {}),
    });
    emit('discrepancyResolved', seg.id);
    toast.push(dismiss ? 'Discrepancy dismissed' : 'Marked OK', { tone: 'success' });
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Could not mark';
    toast.push(msg, { tone: 'error' });
  } finally {
    resolving.value.delete(seg.id);
  }
}

const mode = ref<'all' | 'flagged' | 'meaningful'>('flagged');

// Real data only. No fixture fallback.
const segments = computed<readonly Segment[]>(() => props.liveSegments ?? []);

const slidesById = computed<Map<string, Slide>>(() => {
  const m = new Map<string, Slide>();
  (props.liveSlides ?? []).forEach((s) => m.set(s.id, s));
  return m;
});
function slideById(slideId: string | null | undefined): Slide | undefined {
  if (!slideId) return undefined;
  return slidesById.value.get(slideId);
}

// Flagged segments (have at least one real or fixture discrepancy attached).
// LIVE: group real DiscrepancyRow[] by segment_id.
// FIXTURE: group Discrepancy[] by .seg.
interface FlagInfo {
  segmentId: string;
  aiText: string | null;
  sttText: string | null;
  category: string | null;
  meaningful: boolean | null;
}

const flagsBySeg = computed<Map<string, FlagInfo[]>>(() => {
  const m = new Map<string, FlagInfo[]>();
  (props.liveDiscrepancies ?? []).forEach((d) => {
    if (!d.segment_id) return;
    const arr = m.get(d.segment_id) ?? [];
    arr.push({
      segmentId:  d.segment_id,
      aiText:     d.ai_text,
      sttText:    d.stt_text,
      category:   d.category,
      meaningful: d.is_meaningful,
    });
    m.set(d.segment_id, arr);
  });
  return m;
});

const flaggedSegmentIds = computed<Set<string>>(() => new Set(flagsBySeg.value.keys()));
const meaningfulSegmentIds = computed<Set<string>>(() => {
  const s = new Set<string>();
  flagsBySeg.value.forEach((flags, segId) => {
    if (flags.some((f) => f.meaningful === true)) s.add(segId);
  });
  return s;
});

const totalDiffs = computed(() => props.liveDiscrepancies?.length ?? 0);
const meaningfulCount = computed(
  () => (props.liveDiscrepancies ?? []).filter((d) => d.is_meaningful === true).length,
);

const visibleSegments = computed<Segment[]>(() => {
  let pool: Segment[] = [...segments.value];
  if (props.slideRailMode === 'filter' && props.focusedSlideId) {
    pool = pool.filter((s) => s.slide_id === props.focusedSlideId);
  }
  if (mode.value === 'all') return pool;
  if (mode.value === 'flagged') return pool.filter((s) => flaggedSegmentIds.value.has(s.id));
  if (mode.value === 'meaningful') return pool.filter((s) => meaningfulSegmentIds.value.has(s.id));
  return pool;
});

// ─── STT text per segment ───────────────────────────────────────────────
// Join real STT words for the segment, then highlight diffed fragments.
// Single-pass render: collect (start, end) ranges on the PLAINTEXT, merge
// overlaps, then walk the text once building HTML-escaped output with
// <mark> wrappers around each merged range. This guarantees no fragment
// regex ever matches inside an already-injected <mark> tag.
function renderSTT(seg: Segment): string {
  const ws = props.liveWords?.get(seg.id) ?? [];
  if (ws.length === 0) return '';
  const plain = ws.map((w) => w.word.toLowerCase()).join(' ');

  const ranges: Array<{ start: number; end: number }> = [];
  for (const d of flagsBySeg.value.get(seg.id) ?? []) {
    if (!d.sttText) continue;
    const idx = plain.indexOf(d.sttText.toLowerCase());
    if (idx >= 0) ranges.push({ start: idx, end: idx + d.sttText.length });
  }

  ranges.sort((a, b) => a.start - b.start);
  const merged: Array<{ start: number; end: number }> = [];
  for (const r of ranges) {
    const prev = merged[merged.length - 1];
    if (prev && r.start <= prev.end) prev.end = Math.max(prev.end, r.end);
    else merged.push({ ...r });
  }

  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  let out = '';
  let cursor = 0;
  for (const r of merged) {
    out += esc(plain.slice(cursor, r.start));
    out += `<mark class="compare-diff">${esc(plain.slice(r.start, r.end))}</mark>`;
    cursor = r.end;
  }
  out += esc(plain.slice(cursor));
  return out;
}

// ─── Row classes ────────────────────────────────────────────────────────
function aiRowCls(seg: Segment): string {
  const cls = ['segment', 'compare__row-ai'];
  if (seg.id === props.activeSegmentId) cls.push('is-active');
  if (flaggedSegmentIds.value.has(seg.id)) cls.push('is-needs-review');
  return cls.join(' ');
}
function sttRowCls(seg: Segment): string {
  const cls = ['stt-segment', 'compare__row-stt'];
  if (seg.id === props.activeSegmentId) cls.push('is-active');
  return cls.join(' ');
}
function sttConfStyle(seg: Segment): Record<string, string> {
  const a = slideAccent(seg.slide_id);
  return { color: a, borderColor: withAlpha(a, '44') };
}

function onSegEdit(seg: Segment): void {
  // Phase B1: pivot the editor to the AI tab + open the inline edit on
  // this segment. Parent (EditorView) handles the tab switch + scroll +
  // startEdit dispatch.
  emit('requestEdit', seg.id);
}
function onSegReassign(seg: Segment): void {
  // Reassign UI lives in the AI tab. Pivot via the same path; the
  // operator clicks the segment's Reassign button there. Keeps this
  // pane focused on the diff comparison and avoids duplicating the
  // slide picker.
  emit('requestEdit', seg.id);
}
</script>

<template>
  <section class="compare" data-screen-label="Discrepancies — AI ↔ STT compare">
    <div
      v-if="slideRailMode === 'filter' && focusedSlideId"
      class="transcript__filter-banner"
      role="status"
      :style="{ margin: '10px 18px 0' }"
    >
      <Icon name="filter" :size="14" />
      <span><strong>Filter mode:</strong> showing {{ visibleSegments.length }} segments on slide {{ focusedSlideId.replace('s', '') }}.</span>
      <button class="btn btn--tertiary btn--sm" @click="emit('clearFocus')">Clear filter</button>
    </div>

    <div
      role="note"
      :style="{
        margin: '10px 18px 0', padding: '10px 14px',
        background: 'rgba(0,125,97,0.10)', border: '1px solid rgba(0,125,97,0.4)',
        borderRadius: '6px', color: 'var(--color-green)',
        fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px'
      }"
    >
      <Icon name="alert" :size="14" />
      <span>
        <strong>Live data.</strong> {{ totalDiffs }} LCS-detected diffs from
        <code :style="{ background: 'rgba(255,255,255,0.08)', padding: '1px 5px', borderRadius: '2px' }">transcription_discrepancies</code>;
        STT column joins real Google STT words per segment. No data shown anywhere is fabricated.
      </span>
    </div>

    <div class="compare__toolbar compare__toolbar--top">
      <div class="count">
        <strong :style="{ color: 'var(--color-amber)' }">{{ meaningfulCount }}</strong> flagged for review · {{ totalDiffs }} raw diffs
      </div>
      <div class="compare__modes" role="radiogroup" aria-label="Filter mode">
        <button
          :class="mode === 'all' ? 'is-active' : ''"
          role="radio" :aria-checked="mode === 'all'"
          @click="mode = 'all'"
        >All <span class="count-pill">{{ segments.length }}</span></button>
        <button
          :class="mode === 'flagged' ? 'is-active' : ''"
          role="radio" :aria-checked="mode === 'flagged'"
          @click="mode = 'flagged'"
        >Flagged <span class="count-pill">{{ flaggedSegmentIds.size }}</span></button>
        <button
          :class="mode === 'meaningful' ? 'is-active' : ''"
          role="radio" :aria-checked="mode === 'meaningful'"
          @click="mode = 'meaningful'"
        >Meaningful <span class="count-pill">{{ meaningfulSegmentIds.size }}</span></button>
      </div>
    </div>

    <div class="compare__split">
      <div class="compare__col-head compare__col-head--ai">
        <Icon name="doc" :size="13" /> AI Transcript
      </div>
      <div class="compare__col-head compare__col-head--stt">
        <Icon name="speaker" :size="13" /> STT Raw <span class="badge">read-only</span>
      </div>
      <template v-for="seg in visibleSegments" :key="seg.id">
        <article
          :class="aiRowCls(seg)"
          :style="{ boxShadow: `inset 3px 0 0 ${slideAccent(seg.slide_id)}` }"
          @click="emit('segmentClick', seg.id)"
        >
          <header class="segment__header">
            <span class="segment__slide-chip">
              <span :style="{ width: '8px', height: '8px', borderRadius: '50%', background: slideAccent(seg.slide_id) }" />
              <strong>{{ slideById(seg.slide_id || '') ? String(slideById(seg.slide_id || '')!.n).padStart(2, '0') : '—' }}</strong>
              <span :style="{ opacity: 0.5 }">·</span>
              <span :style="{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }">{{ slideById(seg.slide_id || '')?.title || 'Unassigned' }}</span>
            </span>
            <span class="segment__inline-actions">
              <span
                v-if="flaggedSegmentIds.has(seg.id)"
                class="chip chip--amber"
                :style="{ fontSize: '9px', padding: '2px 7px' }"
              >{{ (flagsBySeg.get(seg.id) || []).length }} diff</span>
              <button class="segment__inline-action" data-test-id="seg-edit-disc" @click.stop="onSegEdit(seg)">Edit</button>
              <button class="segment__inline-action" data-test-id="seg-reassign-disc" @click.stop="onSegReassign(seg)">Reassign</button>
              <button
                v-if="flaggedSegmentIds.has(seg.id)"
                class="segment__inline-action"
                :data-test-id="`seg-mark-ok-${seg.id}`"
                :disabled="resolving.has(seg.id)"
                @click.stop="onMarkOk(seg, false)"
              >Mark OK</button>
              <button
                v-if="flaggedSegmentIds.has(seg.id)"
                class="segment__inline-action"
                :data-test-id="`seg-dismiss-${seg.id}`"
                :disabled="resolving.has(seg.id)"
                @click.stop="onMarkOk(seg, true)"
              >Dismiss</button>
            </span>
          </header>
          <div class="segment__body">
            <div class="segment__gutter">
              <span class="segment__time">{{ fmtTime(seg.start) }}</span>
              <span
                :class="['segment__speaker-pill', `speaker-${seg.speaker}`]"
                :style="{ background: `${speakerDisplay(seg).color}22`, color: speakerDisplay(seg).color, borderColor: `${speakerDisplay(seg).color}55` }"
              >{{ speakerDisplay(seg).short }}</span>
            </div>
            <div class="segment__main">
              <SegmentText :text="seg.text" :flags="seg.ai_flags" :active-word-idx="-1" />
            </div>
          </div>
        </article>
        <article
          :class="sttRowCls(seg)"
          :data-stt-seg="seg.id"
          :style="{ boxShadow: `inset 3px 0 0 ${slideAccent(seg.slide_id)}` }"
          @click="emit('segmentClick', seg.id)"
        >
          <header class="segment__header" :style="{ visibility: 'hidden' }" aria-hidden="true">
            <span class="segment__slide-chip">
              <span :style="{ width: '8px', height: '8px', borderRadius: '50%', background: 'transparent' }" />
              <strong>·</strong>
            </span>
          </header>
          <div class="stt-segment__gutter">
            <span class="stt-segment__time">{{ fmtTime(seg.start) }}</span>
            <span
              :class="['stt-segment__conf', seg.confidence === 'low' ? 'low' : '']"
              :style="sttConfStyle(seg)"
            >{{ slideById(seg.slide_id || '') ? `s${String(slideById(seg.slide_id || '')!.n).padStart(2, '0')}` : '' }}</span>
          </div>
          <div class="stt-segment__main" v-html="renderSTT(seg)" />
        </article>
      </template>
      <div v-if="visibleSegments.length === 0" class="compare__empty">
        All clean — no discrepancies matching this filter.
      </div>
    </div>
  </section>
</template>
