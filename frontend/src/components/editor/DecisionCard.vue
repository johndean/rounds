<script setup lang="ts">
/**
 * DecisionCard — verbatim port of audit.jsx::DecisionCard (223-288).
 * WAS / NOW two-panel card for a single correction. Renders inline highlights
 * for text_edit, chat_insert, slide/speaker reassignment, annotation_add.
 */
import { computed } from 'vue';
import type { Correction } from '@/fixtures/audit';
import { SLIDES, type Segment } from '@/fixtures/transcript';
import { fmtTime } from '@/utils/editorHelpers';

const props = defineProps<{
  c: Correction;
  segmentsById: Map<string, Segment>;
  activeSegmentId: string | null | undefined;
}>();

const emit = defineEmits<{ (e: 'segmentClick', id: string): void }>();

const seg = computed(() => props.segmentsById.get(props.c.seg));
const slide = computed(() => (seg.value ? SLIDES.find((s) => s.id === seg.value!.slide_id) : null));
const isActive = computed(() => seg.value && seg.value.id === props.activeSegmentId);

interface Pill { label: string; tone: 'amber' | 'blue' }
const pill = computed<Pill>(() => {
  switch (props.c.type) {
    case 'text_edit':            return { label: 'edited',           tone: 'amber' };
    case 'chat_insert':          return { label: 'inserted chat',    tone: 'amber' };
    case 'slide_reassignment':   return { label: 'slide reassigned', tone: 'amber' };
    case 'speaker_reassignment': return { label: 'speaker change',   tone: 'amber' };
    case 'annotation_add':       return { label: 'annotation',       tone: 'blue'  };
    default:                     return { label: props.c.type as string, tone: 'amber' };
  }
});

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const wasHtml = computed(() => {
  const c = props.c;
  if (c.type === 'text_edit' && seg.value && c.next) {
    let was = seg.value.text;
    try {
      was = was.replace(new RegExp(`(${escapeRe(c.next)})`, 'i'), `<s class="dc-was-strike">${c.prior ?? ''}</s>`);
    } catch (_) { /* noop */ }
    return `<p>${was}</p>`;
  }
  if (c.type === 'chat_insert') return '<p><s class="dc-was-strike">(none)</s></p>';
  if (c.type === 'slide_reassignment')   return `<p>Slide <s class="dc-was-strike">${c.prior ?? ''}</s></p>`;
  if (c.type === 'speaker_reassignment') return `<p>Speaker: <s class="dc-was-strike">${c.prior ?? ''}</s></p>`;
  if (c.type === 'annotation_add')       return '<p><s class="dc-was-strike">(no annotation)</s></p>';
  return '<p style="color: var(--fg2)">—</p>';
});

const nowHtml = computed(() => {
  const c = props.c;
  if (c.type === 'text_edit' && seg.value && c.next) {
    let now = seg.value.text;
    try {
      now = now.replace(new RegExp(`(${escapeRe(c.next)})`, 'i'), `<mark class="dc-now-mark">${c.next}</mark>`);
    } catch (_) { /* noop */ }
    return `<p>${now}</p>`;
  }
  if (c.type === 'chat_insert') {
    const parts = c.actor.split(/[. ]/);
    const first = parts[0] || '';
    const last = parts[parts.length - 1] || '';
    return `<p><mark class="dc-now-mark">[${first} ${last}]</mark> ${seg.value?.text || c.note || ''}</p>`;
  }
  if (c.type === 'slide_reassignment')   return `<p>Slide <mark class="dc-now-mark">${c.next ?? ''}</mark> — ${c.note ?? ''}</p>`;
  if (c.type === 'speaker_reassignment') return `<p>Speaker: <mark class="dc-now-mark">${c.next ?? ''}</mark></p>`;
  if (c.type === 'annotation_add')       return `<p>Marked as <mark class="dc-now-mark">${c.next ?? ''}</mark> — ${c.note ?? ''}</p>`;
  return `<p>${c.note ?? ''}</p>`;
});

const timeRange = computed(() => (seg.value ? `${fmtTime(seg.value.start)}–${fmtTime(seg.value.end)}` : '—'));

const fmtActor = computed(() =>
  new Date(props.c.t).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true,
  })
);

const actorShort = computed(() => props.c.actor.toLowerCase().replace(/[. ]+/g, ''));
</script>

<template>
  <article
    :class="['decision-card', isActive ? 'is-active' : '']"
    @click="seg && emit('segmentClick', seg.id)"
  >
    <header class="decision-card__head">
      <span class="decision-card__time">{{ timeRange }}</span>
      <span :class="['decision-card__pill', `decision-card__pill--${pill.tone}`]">{{ pill.label }}</span>
      <span class="decision-card__pill decision-card__pill--export">export</span>
      <span class="decision-card__actor">
        <strong>{{ actorShort }}</strong> · {{ fmtActor }}
      </span>
    </header>
    <div class="decision-card__slidechip">{{ slide?.title || `Segment ${c.seg}` }}</div>
    <div class="decision-card__panel decision-card__panel--was">
      <span class="decision-card__lbl">WAS</span>
      <div v-html="wasHtml" />
    </div>
    <div class="decision-card__panel decision-card__panel--now">
      <span class="decision-card__lbl">NOW</span>
      <div v-html="nowHtml" />
    </div>
  </article>
</template>
