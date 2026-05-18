<script setup lang="ts">
/**
 * DiscrepanciesPane — verbatim port of audit.jsx::DiscrepanciesPane (7-160).
 * Side-by-side AI Transcript ↔ STT Raw with inline diff highlighting.
 * Modes: all | flagged | meaningful. Synced 2-column CSS grid.
 */
import { ref, computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import SegmentText from '@/components/editor/SegmentText.vue';
import {
  SEGMENTS,
  SPEAKERS,
  slideAccent,
  slideById,
  type Segment,
} from '@/fixtures/transcript';
import { DISCREPANCIES, type Discrepancy } from '@/fixtures/audit';
import { withAlpha, fmtTime } from '@/utils/editorHelpers';
import { toast } from '@/composables/useToast';

const props = defineProps<{
  activeSegmentId: string | null | undefined;
  focusedSlideId: string | null;
  slideRailMode: 'focus' | 'filter';
}>();

const emit = defineEmits<{
  (e: 'segmentClick', id: string): void;
  (e: 'clearFocus'): void;
}>();

const mode = ref<'all' | 'flagged' | 'meaningful'>('flagged');

const flagsBySeg = computed<Map<string, Discrepancy[]>>(() => {
  const m = new Map<string, Discrepancy[]>();
  DISCREPANCIES.forEach((d) => {
    if (!m.has(d.seg)) m.set(d.seg, []);
    m.get(d.seg)!.push(d);
  });
  return m;
});

const flaggedSegmentIds = computed(() => new Set(DISCREPANCIES.map((d) => d.seg)));
const meaningfulSegmentIds = computed(
  () => new Set(DISCREPANCIES.filter((d) => d.meaningful).map((d) => d.seg))
);

const visibleSegments = computed<Segment[]>(() => {
  let pool: Segment[] = [...SEGMENTS];
  if (props.slideRailMode === 'filter' && props.focusedSlideId) {
    pool = pool.filter((s) => s.slide_id === props.focusedSlideId);
  }
  if (mode.value === 'all') return pool;
  if (mode.value === 'flagged') return pool.filter((s) => flaggedSegmentIds.value.has(s.id));
  if (mode.value === 'meaningful') return pool.filter((s) => meaningfulSegmentIds.value.has(s.id));
  return pool;
});

const totalDiffs = DISCREPANCIES.length;
const meaningfulCount = DISCREPANCIES.filter((d) => d.meaningful).length;

function renderSTT(seg: Segment): string {
  const diffs = flagsBySeg.value.get(seg.id) || [];
  let stt = seg.text.toLowerCase().replace(/[.,;!?—–]/g, '');
  diffs.forEach((d) => {
    if (d.kind === 'drift') {
      const baseFrag = d.base.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      try {
        stt = stt.replace(new RegExp(baseFrag, 'i'), d.stt.toLowerCase());
      } catch (_) { /* noop */ }
    }
  });
  if (!diffs.length) return stt;
  let html = stt;
  diffs.forEach((d) => {
    if (d.kind === 'drift') {
      const sttFrag = d.stt.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      try {
        html = html.replace(new RegExp(`(${sttFrag})`, 'i'), '<mark class="compare-diff">$1</mark>');
      } catch (_) { /* noop */ }
    }
  });
  return html;
}

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
  toast.push(`Edit segment ${seg.id}`, { tone: 'info' });
}
function onSegReassign(seg: Segment): void {
  toast.push(`Reassign segment ${seg.id}`, { tone: 'info' });
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
    <div class="compare__toolbar compare__toolbar--top">
      <div class="count">
        <strong :style="{ color: 'var(--color-amber)' }">{{ meaningfulCount }}</strong> flagged for review · {{ totalDiffs }} raw diffs
      </div>
      <div class="compare__modes" role="radiogroup" aria-label="Filter mode">
        <button
          :class="mode === 'all' ? 'is-active' : ''"
          role="radio" :aria-checked="mode === 'all'"
          @click="mode = 'all'"
        >All <span class="count-pill">{{ SEGMENTS.length }}</span></button>
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
            </span>
          </header>
          <div class="segment__body">
            <div class="segment__gutter">
              <span class="segment__time">{{ fmtTime(seg.start) }}</span>
              <span :class="['segment__speaker-pill', `speaker-${seg.speaker}`]">{{ SPEAKERS[seg.speaker].short }}</span>
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
