<script setup lang="ts">
/**
 * SegmentText — port of components.jsx::SegmentText (266-292), upgraded for
 * MIC-parity real-time per-word highlighting.
 *
 * Two render paths:
 *   1. `liveWords` (preferred) — when STT word-level data is available for
 *      this segment, render each word as <span class="dw" data-ws data-we>.
 *      A watcher in TranscriptPane.vue walks these spans on every timeupdate
 *      and applies .dw-active to whichever span's [ws,we] window contains the
 *      current playback time. Highlighting is precise to the actual STT
 *      word boundary. MIC parity (mic/frontend/src/views/EditorView.vue:3147).
 *   2. Fallback — split `text` on whitespace, apply `is-current` to the
 *      word at `activeWordIdx` (the proportional estimate). Used when
 *      liveWords is absent for this segment (early in load, or sessions
 *      without per-word STT data).
 */
import { computed } from 'vue';
import type { AiFlag } from '@/fixtures/transcript';

// Same shape as WordRow from @/services/api — start_ms/end_ms in milliseconds.
// data-ws/data-we attributes are written in seconds (ms/1000) so the
// TranscriptPane time watcher can compare directly to playback time.
interface LiveWord { word: string; start_ms: number; end_ms: number; }

const props = withDefaults(defineProps<{
  text: string;
  flags?: AiFlag[];
  activeWordIdx?: number;
  liveWords?: readonly LiveWord[];
}>(), { flags: () => [], activeWordIdx: -1, liveWords: undefined });

const emit = defineEmits<{ (e: 'wordClick', idx: number): void }>();

const useLive = computed(() => !!props.liveWords?.length);

const tokens = computed(() => props.text.split(/(\s+)/));
const flagByWord = computed(() => {
  const m = new Map<number, AiFlag['kind']>();
  (props.flags || []).forEach((f) => m.set(f.w, f.kind));
  return m;
});

interface WordEntry { kind: 'space' | 'word'; tok: string; idx: number; }

const items = computed<WordEntry[]>(() => {
  const out: WordEntry[] = [];
  let wordIdx = -1;
  tokens.value.forEach((tok) => {
    if (/^\s+$/.test(tok)) {
      out.push({ kind: 'space', tok, idx: -1 });
    } else {
      wordIdx++;
      out.push({ kind: 'word', tok, idx: wordIdx });
    }
  });
  return out;
});

function classFor(item: WordEntry): string {
  if (item.kind === 'space') return '';
  const kind = flagByWord.value.get(item.idx);
  const isCur = item.idx === props.activeWordIdx;
  const parts = ['word'];
  if (kind) parts.push(`flag-${kind}`);
  if (isCur) parts.push('is-current');
  return parts.join(' ');
}

function liveClassFor(idx: number): string {
  const kind = flagByWord.value.get(idx);
  const parts = ['word', 'dw'];
  if (kind) parts.push(`flag-${kind}`);
  return parts.join(' ');
}

function onClick(item: WordEntry, e: MouseEvent): void {
  if (item.kind !== 'word') return;
  e.stopPropagation();
  emit('wordClick', item.idx);
}

function onLiveClick(idx: number, e: MouseEvent): void {
  e.stopPropagation();
  emit('wordClick', idx);
}
</script>

<template>
  <span class="segment__text">
    <template v-if="useLive">
      <template v-for="(w, i) in props.liveWords" :key="i">
        <span
          :class="liveClassFor(i)"
          :data-ws="w.start_ms / 1000"
          :data-we="w.end_ms / 1000"
          @click="onLiveClick(i, $event)"
        >{{ w.word }}</span>
        <span v-if="i < (props.liveWords?.length ?? 0) - 1"> </span>
      </template>
    </template>
    <template v-else>
      <span
        v-for="(item, i) in items"
        :key="i"
        :class="classFor(item)"
        @click="onClick(item, $event)"
      >{{ item.tok }}</span>
    </template>
  </span>
</template>
