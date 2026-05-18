<script setup lang="ts">
/**
 * AdminTab — verbatim port of editor.jsx::AdminTab (175-235).
 * Right-rail "Admin" sub-tab body: timeline minimap + per-slide segment list +
 * instructor card + IIL signal previews (cadence / filler ratio).
 */
import { computed } from 'vue';
import { slideAccent, type Slide, type Segment } from '@/fixtures/transcript';
import { withAlpha, fmtTime } from '@/utils/editorHelpers';

const props = defineProps<{
  slide: Slide | null | undefined;
  segments: readonly Segment[];
  time: number;
  totalDuration: number;
  slides: readonly Slide[];
}>();

const accent = computed(() => (props.slide ? slideAccent(props.slide.id) : '#4D6995'));

interface MapRect { id: string; x: number; w: number; fill: string; isCurrent: boolean; }
const minimapRects = computed<MapRect[]>(() => {
  if (!props.slide) return [];
  const out: MapRect[] = [];
  props.slides.forEach((s) => {
    const sSegs = props.segments.filter((g) => g.slide_id === s.id);
    if (!sSegs.length) return;
    const x1 = (sSegs[0]!.start / props.totalDuration) * 200;
    const x2 = (sSegs[sSegs.length - 1]!.end / props.totalDuration) * 200;
    const isCurrent = s.id === props.slide!.id;
    const a = slideAccent(s.id);
    out.push({
      id: s.id,
      x: x1,
      w: Math.max(1, x2 - x1),
      fill: isCurrent ? a : withAlpha(a, '55'),
      isCurrent,
    });
  });
  return out;
});

const headLeft = computed(() => `${(props.time / props.totalDuration) * 100}%`);

const slideSegs = computed<Segment[]>(() =>
  props.slide ? props.segments.filter((s) => s.slide_id === props.slide!.id) : []
);

function isActive(s: Segment): boolean {
  return props.time >= s.start && props.time < s.end + 0.25;
}

function segStyle(s: Segment): Record<string, string | number> {
  const active = isActive(s);
  return {
    background: active ? withAlpha(accent.value, '33') : withAlpha(accent.value, '12'),
    borderLeftColor: accent.value,
    borderLeftWidth: active ? '3px' : '2px',
  };
}
</script>

<template>
  <div v-if="!slide" :style="{ fontSize: '12px', color: 'var(--fg2)' }">No active slide.</div>
  <div v-else>
    <div class="rightrail__sectionhead">Timeline · session map</div>
    <div class="minimap" aria-label="Session timeline minimap" :style="{ marginBottom: '12px' }">
      <svg viewBox="0 0 200 20" preserveAspectRatio="none">
        <rect
          v-for="r in minimapRects"
          :key="r.id"
          :x="r.x"
          y="4"
          :width="r.w"
          height="12"
          :fill="r.fill"
          :stroke="r.isCurrent ? r.fill : 'none'"
          :stroke-width="r.isCurrent ? 0.5 : 0"
        />
      </svg>
      <div class="minimap__head" :style="{ left: headLeft }" />
    </div>

    <div class="rightrail__sectionhead">Segments on this slide · {{ slideSegs.length }}</div>
    <ul class="admin-segment-list">
      <li v-for="s in slideSegs" :key="s.id" :style="segStyle(s)">
        <span class="t" :style="{ color: accent }">{{ fmtTime(s.start) }}</span>
        <span :style="{ display: '-webkit-box', '-webkit-line-clamp': 1, '-webkit-box-orient': 'vertical', overflow: 'hidden' }">{{ s.text }}</span>
      </li>
    </ul>

    <div class="rightrail__sectionhead">Instructor</div>
    <div class="instructor-card">
      <div class="instructor-card__av">PM</div>
      <div>
        <div class="instructor-card__name">Dr. Pamela Mueller, DVM, DACVS</div>
        <div class="instructor-card__role">Soft Tissue Surgery · University of Wisconsin SVM</div>
        <div class="instructor-card__meta">23 sessions on VIN · avg 1.0h · 4.8 rating</div>
      </div>
    </div>

    <div class="rightrail__sectionhead">IIL signals (preview)</div>
    <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '11px' }">
      <div :style="{ padding: '6px 8px', background: 'var(--surface-bg)', border: '1px solid var(--border-subtle)', borderRadius: '6px' }">
        <div :style="{ color: 'var(--fg2)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 700 }">Cadence</div>
        <div :style="{ fontSize: '12px', fontWeight: 700, color: 'var(--fg1)' }">148 wpm</div>
      </div>
      <div :style="{ padding: '6px 8px', background: 'var(--surface-bg)', border: '1px solid var(--border-subtle)', borderRadius: '6px' }">
        <div :style="{ color: 'var(--fg2)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 700 }">Filler ratio</div>
        <div :style="{ fontSize: '12px', fontWeight: 700, color: 'var(--fg1)' }">2.1%</div>
      </div>
    </div>
  </div>
</template>
