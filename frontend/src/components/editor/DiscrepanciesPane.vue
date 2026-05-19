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
 */
import { computed, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import SegmentText from '@/components/editor/SegmentText.vue';
import {
  SEGMENTS as FIXTURE_SEGMENTS,
  slideAccent,
  slideById as fixtureSlideById,
  speakerDisplay,
  type Segment,
  type Slide,
} from '@/fixtures/transcript';
import { DISCREPANCIES as FIXTURE_DISCREPANCIES, type Discrepancy } from '@/fixtures/audit';
import type { DiscrepancyRow, WordRow } from '@/services/api';
import { withAlpha, fmtTime } from '@/utils/editorHelpers';
import { toast } from '@/composables/useToast';

const props = defineProps<{
  activeSegmentId: string | null | undefined;
  focusedSlideId: string | null;
  slideRailMode: 'focus' | 'filter';
  // Live (real-session) data. When all three are present and non-empty,
  // the pane renders from real data. Absence = fixture-demo path.
  liveSegments?: readonly Segment[];
  liveSlides?: readonly Slide[];
  liveDiscrepancies?: readonly DiscrepancyRow[];
  liveWords?: Map<string, WordRow[]>;
}>();

const emit = defineEmits<{
  (e: 'segmentClick', id: string): void;
  (e: 'clearFocus'): void;
}>();

const mode = ref<'all' | 'flagged' | 'meaningful'>('flagged');

// ─── Path selector ──────────────────────────────────────────────────────
const isLive = computed(() => !!(props.liveSegments && props.liveSegments.length));

// ─── Source data (live or fixture) ──────────────────────────────────────
const segments = computed<readonly Segment[]>(
  () => (isLive.value ? props.liveSegments! : FIXTURE_SEGMENTS),
);

const slidesById = computed<Map<string, Slide>>(() => {
  const m = new Map<string, Slide>();
  if (isLive.value && props.liveSlides) {
    props.liveSlides.forEach((s) => m.set(s.id, s));
  }
  return m;
});
function slideById(slideId: string | null | undefined): Slide | undefined {
  if (!slideId) return undefined;
  return slidesById.value.get(slideId) ?? fixtureSlideById(slideId);
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
  if (isLive.value) {
    (props.liveDiscrepancies || []).forEach((d) => {
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
  } else {
    FIXTURE_DISCREPANCIES.forEach((d: Discrepancy) => {
      const arr = m.get(d.seg) ?? [];
      arr.push({
        segmentId:  d.seg,
        aiText:     d.base,
        sttText:    d.stt,
        category:   d.kind,
        meaningful: d.meaningful,
      });
      m.set(d.seg, arr);
    });
  }
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

const totalDiffs = computed(() =>
  isLive.value ? (props.liveDiscrepancies?.length ?? 0) : FIXTURE_DISCREPANCIES.length,
);
const meaningfulCount = computed(() => {
  if (isLive.value) {
    return (props.liveDiscrepancies || []).filter((d) => d.is_meaningful === true).length;
  }
  return FIXTURE_DISCREPANCIES.filter((d) => d.meaningful).length;
});

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
// LIVE: join real STT words for the segment (real text + spaces).
// FIXTURE: lowercase AI text and string-replace fixture drift fragments.
function _escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function renderSTT(seg: Segment): string {
  const diffs = flagsBySeg.value.get(seg.id) || [];

  // LIVE: real STT text comes from the words table; substitute nothing.
  if (isLive.value) {
    const ws = props.liveWords?.get(seg.id) || [];
    let stt = ws.length
      ? ws.map((w) => w.word.toLowerCase()).join(' ')
      // No words yet (e.g. stt_background hasn't finished) — fall back to AI text
      // so the comparison column isn't blank. Honest banner above will flag this.
      : seg.text.toLowerCase().replace(/[.,;!?—–]/g, '');
    // Highlight the stt_text fragment from each discrepancy (real LCS output).
    let html = stt;
    diffs.forEach((d) => {
      if (!d.sttText) return;
      const frag = _escapeRegex(d.sttText.toLowerCase());
      try {
        html = html.replace(new RegExp(`(${frag})`, 'i'), '<mark class="compare-diff">$1</mark>');
      } catch (_) { /* noop */ }
    });
    return html;
  }

  // FIXTURE-DEMO path (unchanged from prototype).
  let stt = seg.text.toLowerCase().replace(/[.,;!?—–]/g, '');
  diffs.forEach((d) => {
    if (d.category === 'drift' && d.aiText && d.sttText) {
      const baseFrag = _escapeRegex(d.aiText.toLowerCase());
      try {
        stt = stt.replace(new RegExp(baseFrag, 'i'), d.sttText.toLowerCase());
      } catch (_) { /* noop */ }
    }
  });
  if (!diffs.length) return stt;
  let html = stt;
  diffs.forEach((d) => {
    if (d.category === 'drift' && d.sttText) {
      const sttFrag = _escapeRegex(d.sttText.toLowerCase());
      try {
        html = html.replace(new RegExp(`(${sttFrag})`, 'i'), '<mark class="compare-diff">$1</mark>');
      } catch (_) { /* noop */ }
    }
  });
  return html;
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

    <!-- LIVE banner — clear about source -->
    <div
      v-if="isLive"
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
        STT column joins real Google STT words per segment.
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
