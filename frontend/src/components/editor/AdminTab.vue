<script setup lang="ts">
/**
 * AdminTab — right-rail "Admin" sub-tab: timeline minimap + per-slide segment
 * list + instructor card + IIL signal previews (cadence / filler ratio).
 *
 * Instructor card pulls from real session_speakers (first row, preferred a
 * speaker with role='moderator'). If none, the card is hidden — no fixture
 * lies. IIL signals likewise only render when real data exists.
 */
import { computed } from 'vue';
import { slideAccent, type Slide, type Segment } from '@/fixtures/transcript';
import { withAlpha, fmtTime } from '@/utils/editorHelpers';

interface InstructorLike {
  name: string;
  credentials?: string | null;
  role?: string | null;
  short?: string | null;
  avatar_color?: string | null;
}

interface IilSignals {
  cadence_wpm?: number | null;
  filler_ratio?: number | null;
}

const props = defineProps<{
  slide: Slide | null | undefined;
  segments: readonly Segment[];
  time: number;
  totalDuration: number;
  slides: readonly Slide[];
  instructor?: InstructorLike | null;
  iil?: IilSignals | null;
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
  // Boundary-preferring: same rule as EditorView.activeSegment so clicks /
  // playback crossings don't keep the previous segment lit for 250 ms.
  const all = props.segments;
  const idx = all.indexOf(s);
  if (idx < 0) return false;
  const next = all[idx + 1];
  return props.time >= s.start && (!next || props.time < next.start);
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

    <template v-if="instructor">
      <div class="rightrail__sectionhead">Instructor</div>
      <div class="instructor-card">
        <div
          class="instructor-card__av"
          :style="instructor.avatar_color ? { background: instructor.avatar_color } : {}"
        >{{ instructor.short || instructor.name.split(/\s+/).map(p => p[0]).join('').slice(0,2).toUpperCase() }}</div>
        <div>
          <div class="instructor-card__name">
            {{ instructor.name }}<span v-if="instructor.credentials">, {{ instructor.credentials }}</span>
          </div>
          <div v-if="instructor.role" class="instructor-card__role">{{ instructor.role }}</div>
        </div>
      </div>
    </template>

    <template v-if="iil && (iil.cadence_wpm != null || iil.filler_ratio != null)">
      <div class="rightrail__sectionhead">IIL signals</div>
      <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '11px' }">
        <div v-if="iil.cadence_wpm != null" :style="{ padding: '6px 8px', background: 'var(--surface-bg)', border: '1px solid var(--border-subtle)', borderRadius: '6px' }">
          <div :style="{ color: 'var(--fg2)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 700 }">Cadence</div>
          <div :style="{ fontSize: '12px', fontWeight: 700, color: 'var(--fg1)' }">{{ Math.round(iil.cadence_wpm) }} wpm</div>
        </div>
        <div v-if="iil.filler_ratio != null" :style="{ padding: '6px 8px', background: 'var(--surface-bg)', border: '1px solid var(--border-subtle)', borderRadius: '6px' }">
          <div :style="{ color: 'var(--fg2)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 700 }">Filler ratio</div>
          <div :style="{ fontSize: '12px', fontWeight: 700, color: 'var(--fg1)' }">{{ (iil.filler_ratio * 100).toFixed(1) }}%</div>
        </div>
      </div>
    </template>
  </div>
</template>
