<script setup lang="ts">
/**
 * ActiveSlideCard — verbatim port of editor.jsx::ActiveSlideCard (135-173).
 * Right-rail "Active Slide" panel with accent border, slide preview, minimap,
 * and a Reassign-to-slide button.
 */
import { computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { SLIDES, SEGMENTS, slideAccent, type Slide } from '@/fixtures/transcript';
import { withAlpha } from '@/utils/editorHelpers';
import { toast } from '@/composables/useToast';

const props = defineProps<{
  slide: Slide | null | undefined;
  segmentCount: number;
  collapsed: boolean;
  time: number;
  totalDuration: number;
}>();

const emit = defineEmits<{ (e: 'toggle'): void }>();

const accent = computed(() => (props.slide ? slideAccent(props.slide.id) : '#4D6995'));

const previewStyle = computed(() => {
  const a = accent.value;
  return {
    background: `linear-gradient(160deg, ${a} 0%, ${withAlpha(a, 'cc')} 100%)`,
    backgroundImage: `radial-gradient(ellipse at 80% 50%, rgba(255,255,255,0.10) 0%, transparent 60%), repeating-linear-gradient(-45deg, rgba(255,255,255,0.05) 0, rgba(255,255,255,0.05) 1px, transparent 1px, transparent 10px), linear-gradient(160deg, ${a} 0%, ${withAlpha(a, 'cc')} 100%)`,
  };
});

interface MapRect { id: string; x: number; w: number; fill: string; isCurrent: boolean; }
const minimapRects = computed<MapRect[]>(() => {
  if (!props.slide) return [];
  const out: MapRect[] = [];
  SLIDES.forEach((s) => {
    const segs = SEGMENTS.filter((g) => g.slide_id === s.id);
    if (!segs.length) return;
    const x1 = (segs[0]!.start / props.totalDuration) * 200;
    const x2 = (segs[segs.length - 1]!.end / props.totalDuration) * 200;
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

// Phase 1 (audit remediation): used to toast a mock; demoted to an
// honest warning. Real bulk-reassign ships with Phase 4 corrections.
function reassign(): void {
  toast.push('Bulk slide reassign ships with Phase 4 corrections audit.', { tone: 'warn' });
}
</script>

<template>
  <div
    v-if="slide"
    :class="['rightrail__activeslide', collapsed ? 'is-collapsed' : '']"
    :style="{ borderLeft: `4px solid ${accent}` }"
  >
    <div
      class="rightrail__activeslide-header"
      role="button"
      :aria-expanded="!collapsed"
      @click="emit('toggle')"
    >
      <h4 :style="{ color: accent }">Active Slide</h4>
      <Icon name="chevron-down" :size="14" class="chev" />
    </div>
    <div class="rightrail__activeslide-body">
      <div class="slide-preview" :style="previewStyle">
        <div class="slide-preview__no">Slide {{ String(slide.n).padStart(2, '0') }} of {{ SLIDES.length }}</div>
        <div class="slide-preview__title">{{ slide.title }}</div>
        <div class="slide-preview__foot">
          <span>{{ slide.kind }}</span>
          <span>{{ segmentCount }} seg</span>
        </div>
      </div>
      <div class="minimap" aria-label="Session timeline minimap">
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
      <button class="btn btn--secondary btn--sm" :style="{ width: '100%' }" @click="reassign">
        <Icon name="slide" :size="12" /> Re-assign segments to slide
      </button>
    </div>
  </div>
</template>
