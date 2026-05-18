<script setup lang="ts">
/**
 * VideoStrip — verbatim port of editor.jsx::VideoStrip (72-132).
 * Faux 16:9 video frame + compact audio transport (play / rate / CC / scrubber).
 */
import { computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import type { Slide, Segment } from '@/fixtures/transcript';
import { fmtTime } from '@/utils/editorHelpers';

interface SessionLite { id: string; presenter?: string; recorded?: string }

const props = defineProps<{
  session: SessionLite;
  activeSlide: Slide | null | undefined;
  slides: readonly Slide[];
  time: number;
  total: number;
  playing: boolean;
  rate: number;
  cc: boolean;
  segmentsBySlide: Map<string, Segment[]>;
}>();

const emit = defineEmits<{
  (e: 'togglePlay'): void;
  (e: 'update:rate', r: number): void;
  (e: 'update:cc', v: boolean): void;
  (e: 'scrubClick', ev: MouseEvent): void;
}>();

const todayIso = new Date().toISOString().slice(0, 10);

const timeReadout = computed(() => {
  const t = fmtTime(props.time);
  if (t.split(':').slice(-1)[0] === '00') {
    return `00:${String(Math.floor(props.time / 60)).padStart(2, '0')}`;
  }
  return t;
});

const trackWidth = computed(() => `${(props.time / props.total) * 100}%`);

interface ChapterMark { id: string; n: number; left: string }
const chapterMarks = computed<ChapterMark[]>(() =>
  props.slides
    .map((sl) => {
      const segs = props.segmentsBySlide.get(sl.id);
      if (!segs || !segs.length) return null;
      return { id: sl.id, n: sl.n, left: `${(segs[0]!.start / props.total) * 100}%` };
    })
    .filter((x): x is ChapterMark => x != null)
);

function shortPresenter(p?: string): string {
  return (p || '').replace(/^Dr\. /, 'Dr. ');
}
</script>

<template>
  <div class="vstrip" data-screen-label="Video Player">
    <div
      class="vstrip__frame"
      role="button"
      :aria-label="playing ? 'Pause video' : 'Play video'"
      @click="emit('togglePlay')"
    >
      <div class="vstrip__poster">
        <div class="vstrip__slide-no">{{ activeSlide ? activeSlide.title.split(' ')[0]!.toUpperCase() : '—' }}</div>
        <div class="vstrip__slide-title">{{ activeSlide?.title || '—' }}</div>
        <div class="vstrip__slide-meta">
          <span>{{ shortPresenter(session.presenter) }}</span>
          <span>VIN / NAVAS ROUNDS</span>
          <span>{{ session.recorded || 'JANUARY 12, 2025' }}</span>
        </div>
      </div>
      <div class="vstrip__scan" />
      <div v-if="!playing" class="vstrip__overlay">
        <div class="vstrip__center-play"><Icon name="play" :size="26" /></div>
      </div>
      <div class="vstrip__hud">
        <span class="vstrip__hud-icons">
          <Icon name="skip-back" :size="11" /><Icon name="edit" :size="11" />
          <Icon name="search" :size="11" /><Icon name="slide" :size="11" />
          <Icon name="more" :size="11" />
        </span>
        <span class="vstrip__timecode">{{ todayIso }} {{ fmtTime(time) }} / {{ fmtTime(total) }}</span>
      </div>
    </div>
    <div class="vstrip__bar">
      <button
        class="vstrip__play"
        :title="playing ? 'Pause' : 'Play'"
        @click="emit('togglePlay')"
      ><Icon :name="playing ? 'pause' : 'play'" :size="12" /></button>
      <select
        class="vstrip__rate"
        :value="rate"
        @change="emit('update:rate', parseFloat(($event.target as HTMLSelectElement).value))"
      >
        <option value="0.75">0.75×</option>
        <option value="1">1×</option>
        <option value="1.25">1.25×</option>
        <option value="1.5">1.5×</option>
        <option value="2">2×</option>
      </select>
      <button
        :class="['vstrip__cc', cc ? 'is-on' : '']"
        title="Captions"
        @click="emit('update:cc', !cc)"
      >CC</button>
      <div
        class="vstrip__scrubber"
        role="slider"
        :aria-valuenow="time"
        :aria-valuemin="0"
        :aria-valuemax="total"
        @click="emit('scrubClick', $event)"
      >
        <div class="vstrip__track"><span :style="{ width: trackWidth }" /></div>
        <div class="vstrip__chapter-marks">
          <span v-for="m in chapterMarks" :key="m.id" :style="{ left: m.left }" :title="`Slide ${m.n}`" />
        </div>
        <div class="vstrip__head" :style="{ left: trackWidth }" />
      </div>
      <span class="vstrip__time">{{ timeReadout }}</span>
    </div>
  </div>
</template>
