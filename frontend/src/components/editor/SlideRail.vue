<script setup lang="ts">
/**
 * SlideRail — verbatim port of editor.jsx::SlideRail (6-70).
 * Slide list with Focus/Filter toggle + 3-branch nav style + Clear-focus pill.
 */
import { computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { slideAccent, type Slide, type Segment } from '@/fixtures/transcript';
import { withAlpha } from '@/utils/editorHelpers';

const props = defineProps<{
  slides: readonly Slide[];
  activeSlideId?: string | null;
  focusedSlideId: string | null;
  mode: 'focus' | 'filter';
  segmentsBySlide: Map<string, Segment[]>;
}>();

const emit = defineEmits<{
  (e: 'modeChange', m: 'focus' | 'filter'): void;
  (e: 'slideClick', id: string): void;
  (e: 'clearFocus'): void;
}>();

interface SlideRow {
  slide: Slide;
  segs: Segment[];
  accent: string;
  isActive: boolean;
  isFocused: boolean;
  isEmpty: boolean;
  cls: string;
  style: Record<string, string>;
}

interface SlideBase {
  slide: Slide;
  segs: Segment[];
  accent: string;
  isEmpty: boolean;
  inactiveStyle: Record<string, string>;
  activeStyle: Record<string, string>;
}

// Per-slide static data — accent, empty/non-empty style snapshots — depends
// only on slides + segmentsBySlide. Stable across active/focused clicks.
const slideBase = computed<SlideBase[]>(() =>
  props.slides.map((sl) => {
    const segs = props.segmentsBySlide.get(sl.id) || [];
    const accent = slideAccent(sl.id);
    const isEmpty = segs.length === 0;
    const activeStyle: Record<string, string> = {
      background: withAlpha(accent, '22'),
      borderColor: accent,
      boxShadow: `inset 3px 0 0 ${accent}`,
    };
    const inactiveStyle: Record<string, string> = isEmpty
      ? { opacity: '0.55', boxShadow: `inset 3px 0 0 ${withAlpha(accent, '33')}` }
      : {
          background: withAlpha(accent, '12'),
          borderColor: withAlpha(accent, '44'),
          boxShadow: `inset 3px 0 0 ${accent}`,
        };
    return { slide: sl, segs, accent, isEmpty, inactiveStyle, activeStyle };
  })
);

// Shallow overlay — only recomputes the active/focused classes + which
// style snapshot to use. The per-slide objects above don't reallocate.
const rows = computed<SlideRow[]>(() =>
  slideBase.value.map((b) => {
    const isActive = b.slide.id === props.activeSlideId;
    const isFocused = b.slide.id === props.focusedSlideId;
    const cls = ['slide-card'];
    if (isActive) cls.push('is-active');
    if (isFocused && props.mode === 'focus') cls.push('is-focused-target');
    if (b.isEmpty) cls.push('is-empty');
    return {
      slide:     b.slide,
      segs:      b.segs,
      accent:    b.accent,
      isActive,
      isFocused,
      isEmpty:   b.isEmpty,
      cls:       cls.join(' '),
      style:     isActive ? b.activeStyle : b.inactiveStyle,
    };
  })
);

function trimTitle(t: string): string {
  return t.replace(/^(Title — |Case Study \d+ — )/, '');
}

function thumbStyle(accent: string): Record<string, string> {
  return {
    background: `linear-gradient(160deg, ${accent} 0%, ${withAlpha(accent, 'cc')} 100%)`,
    borderColor: accent,
  };
}

function countStyle(row: SlideRow): Record<string, string> | null {
  if (row.isActive) return null;
  if (row.segs.length) return { color: row.accent };
  return null;
}
</script>

<template>
  <div class="sliderail" aria-label="Slide rail" data-screen-label="Slide Rail">
    <div class="sliderail__head">
      <h4>Slides · {{ slides.length }}</h4>
      <div class="sliderail__toggle" role="radiogroup" aria-label="Slide click mode">
        <button
          :class="mode === 'focus' ? 'is-active' : ''"
          role="radio"
          :aria-checked="mode === 'focus'"
          title="Focus mode — click a slide to scroll to it; all segments stay visible"
          @click="emit('modeChange', 'focus')"
        ><Icon name="circle-dot" :size="11" /> Focus</button>
        <button
          :class="mode === 'filter' ? 'is-active' : ''"
          role="radio"
          :aria-checked="mode === 'filter'"
          title="Filter mode — click a slide to show only its segments (legacy)"
          @click="emit('modeChange', 'filter')"
        ><Icon name="filter" :size="11" /> Filter</button>
      </div>
      <button
        v-if="focusedSlideId"
        class="sliderail__clear"
        :title="mode === 'focus' ? 'Clear focus' : 'Show all'"
        @click.stop="emit('clearFocus')"
      >{{ mode === 'focus' ? 'Clear focus' : 'Show all' }}</button>
    </div>
    <ul class="sliderail__list">
      <li v-for="row in rows" :key="row.slide.id">
        <div
          :class="row.cls"
          :style="row.style"
          :title="row.slide.title"
          @click="emit('slideClick', row.slide.id)"
        >
          <div class="slide-card__thumb" :style="thumbStyle(row.accent)">
            {{ String(row.slide.n).padStart(2, '0') }}
          </div>
          <div class="slide-card__title">{{ trimTitle(row.slide.title) }}</div>
          <span class="slide-card__count" :style="countStyle(row) ?? {}">{{ row.segs.length }}</span>
        </div>
      </li>
    </ul>
  </div>
</template>
