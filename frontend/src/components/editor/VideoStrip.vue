<script setup lang="ts">
/**
 * VideoStrip — visual chrome (16:9 frame, scrubber, slide-chapter marks) plus
 * a real <video> or <audio> element so the editor can actually play the lecture.
 *
 * Element choice keyed on `mediaKind` prop:
 *   - 'video' → visible <video> filling .vstrip__frame (object-fit:contain),
 *     poster hidden. Operator can visually verify slide-on-speaker's-screen
 *     matches alignment's claimed active slide. MIC parity.
 *   - 'audio' → hidden <audio>, poster stays. Same behavior as the old code
 *     for sessions whose `sources` table has no role='video' row.
 *   - null  → no media yet; poster stays.
 *
 * Source of truth for playback is the media element. `time` / `playing` /
 * `rate` props are mirrored both ways via update:* emits. Parent (EditorView)
 * binds with v-model-style update events; no requestAnimationFrame simulation.
 *
 * `timeupdate` events are throttled to ~10 Hz (100 ms min between emits) with
 * leading + trailing edges, ported from MIC stores/playback.js:116-139. Without
 * this the unthrottled 30+ Hz default fires the per-word highlight watcher in
 * TranscriptPane too often on large sessions.
 */
import { computed, ref, watch, onUnmounted } from 'vue';
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
  mediaUrl?: string | null;
  mediaKind?: 'video' | 'audio' | null;
}>();

const emit = defineEmits<{
  (e: 'togglePlay'): void;
  (e: 'update:rate', r: number): void;
  (e: 'update:cc', v: boolean): void;
  (e: 'update:time', t: number): void;
  (e: 'update:playing', v: boolean): void;
  (e: 'update:total', t: number): void;
  (e: 'scrubClick', ev: MouseEvent): void;
}>();

const mediaEl = ref<HTMLMediaElement | null>(null);
const seeking = ref(false);

// 10 Hz throttle on timeupdate (MIC parity — port of stores/playback.js:116-139).
// Leading edge fires the first emit immediately; trailing edge guarantees the
// final value lands when a burst coalesces (prevents stale highlights on pause).
let timeUpdateLastMs = 0;
let timeUpdatePendingTimer: ReturnType<typeof setTimeout> | null = null;

const todayIso = new Date().toISOString().slice(0, 10);

const timeReadout = computed(() => {
  const t = fmtTime(props.time);
  if (t.split(':').slice(-1)[0] === '00') {
    return `00:${String(Math.floor(props.time / 60)).padStart(2, '0')}`;
  }
  return t;
});

const trackWidth = computed(() => {
  const pct = props.total > 0 ? (props.time / props.total) * 100 : 0;
  return `${Math.min(100, Math.max(0, pct))}%`;
});

interface ChapterMark { id: string; n: number; left: string }
const chapterMarks = computed<ChapterMark[]>(() =>
  props.slides
    .map((sl) => {
      const segs = props.segmentsBySlide.get(sl.id);
      if (!segs || !segs.length || props.total <= 0) return null;
      return { id: sl.id, n: sl.n, left: `${(segs[0]!.start / props.total) * 100}%` };
    })
    .filter((x): x is ChapterMark => x != null)
);

function shortPresenter(p?: string): string {
  return (p || '').replace(/^Dr\. /, 'Dr. ');
}

// ─── media ↔ props sync ──────────────────────────────────────────────────
function onTimeUpdate(): void {
  const el = mediaEl.value;
  if (!el || seeking.value) return;
  const now = performance.now();
  const since = now - timeUpdateLastMs;
  if (since >= 100) {
    timeUpdateLastMs = now;
    emit('update:time', el.currentTime);
  } else if (!timeUpdatePendingTimer) {
    timeUpdatePendingTimer = setTimeout(() => {
      timeUpdatePendingTimer = null;
      const el2 = mediaEl.value;
      if (!el2) return;
      timeUpdateLastMs = performance.now();
      emit('update:time', el2.currentTime);
    }, 100 - since);
  }
}

function onLoadedMetadata(): void {
  const el = mediaEl.value;
  if (!el) return;
  if (!Number.isFinite(el.duration) || el.duration <= 0) return;
  // Only override total if the parent's session.duration_sec was missing.
  if (props.total <= 0) emit('update:total', el.duration);
}

function onPlay(): void { emit('update:playing', true); }
function onPause(): void { emit('update:playing', false); }
function onEnded(): void { emit('update:playing', false); }

// Parent → media element pushes. Guard against feedback loops by checking
// whether the desired state already matches.
watch(() => props.time, (t) => {
  const el = mediaEl.value;
  if (!el) return;
  if (Math.abs(el.currentTime - t) > 0.4) {
    seeking.value = true;
    el.currentTime = t;
    // Release the seeking flag after the browser fires the seeked event.
    const release = () => { seeking.value = false; el.removeEventListener('seeked', release); };
    el.addEventListener('seeked', release);
  }
});

watch(() => props.playing, (p) => {
  const el = mediaEl.value;
  if (!el) return;
  if (p && el.paused) void el.play().catch(() => emit('update:playing', false));
  else if (!p && !el.paused) el.pause();
});

watch(() => props.rate, (r) => {
  const el = mediaEl.value;
  if (el && Math.abs(el.playbackRate - r) > 0.001) el.playbackRate = r;
});

onUnmounted(() => {
  if (timeUpdatePendingTimer) { clearTimeout(timeUpdatePendingTimer); timeUpdatePendingTimer = null; }
  const el = mediaEl.value;
  if (el && !el.paused) el.pause();
});
</script>

<template>
  <div class="vstrip" data-screen-label="Video Player">
    <div
      class="vstrip__frame"
      role="button"
      :aria-label="playing ? 'Pause video' : 'Play video'"
      @click="emit('togglePlay')"
    >
      <!-- Real <video> viewport. Mounts when backend returned role='video'. -->
      <video
        v-if="mediaUrl && mediaKind === 'video'"
        ref="mediaEl"
        class="vstrip__video"
        :src="mediaUrl"
        preload="metadata"
        playsinline
        @timeupdate="onTimeUpdate"
        @loadedmetadata="onLoadedMetadata"
        @play="onPlay"
        @pause="onPause"
        @ended="onEnded"
      />
      <!-- Hidden <audio> fallback for sessions without a video source. -->
      <audio
        v-else-if="mediaUrl && mediaKind === 'audio'"
        ref="mediaEl"
        :src="mediaUrl"
        preload="metadata"
        :style="{ display: 'none' }"
        @timeupdate="onTimeUpdate"
        @loadedmetadata="onLoadedMetadata"
        @play="onPlay"
        @pause="onPause"
        @ended="onEnded"
      />
      <!-- Poster shows when no media OR audio-only (slide info as fallback chrome). -->
      <div v-if="!mediaUrl || mediaKind !== 'video'" class="vstrip__poster">
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
