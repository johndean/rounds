<script setup lang="ts">
/**
 * SegmentText — port of components.jsx::SegmentText, upgraded for L2 word
 * highlighting on the AI Transcript tab.
 *
 * Three render paths:
 *   1. `liveAlignment` (preferred on AI Transcript) — render each Gemini word
 *      from `text.split()` as <span class="dw" data-ws data-we>. The (ws, we)
 *      attributes come from the word_alignment table (real STT timestamps).
 *      Unmatched Gemini words render without data-ws/data-we so the watcher
 *      in TranscriptPane.vue passes through them in zero time. This replaces
 *      MIC's broken proportional-time interpolation with 100%-accurate
 *      per-word anchoring on the words STT actually heard.
 *   2. `liveWords` (legacy — STT tab) — render the raw STT tokens with their
 *      own start_ms/end_ms. Used by STTPane / DiscrepanciesPane which want
 *      to display the literal STT output, not the Gemini text.
 *   3. Fallback — split `text` on whitespace and (optionally) highlight the
 *      `activeWordIdx`. Used for legacy sessions without alignment + without
 *      live STT words.
 *
 * Whitespace note: Vue's default `whitespace: 'condense'` compiler strips
 * literal whitespace inside otherwise-empty spans (so `<span> </span>` becomes
 * `<span></span>` at runtime, killing line-break opportunities and forcing
 * the whole segment onto one line). All paths therefore interleave words and
 * spaces as TEXT CONTENT of spans (`{{ item.tok }}`), which Vue preserves.
 * The STT pane uses the equivalent `{{ ' ' }}` idiom (STTPane.vue:247).
 */
import { computed } from 'vue';
import type { AiFlag } from '@/fixtures/transcript';

// Legacy STT-word shape (start_ms/end_ms in ms). Path 2.
interface LiveWord { word: string; start_ms: number; end_ms: number; }

// L2 alignment row. `s` and `e` are ms (or null when match_kind='unmatched').
// `g` is the Gemini token index — used to look up the alignment for a
// given word position in `text.split()`.
interface AlignmentEntry { g: number; s: number | null; e: number | null; k: 'exact' | 'unmatched'; }

const props = withDefaults(defineProps<{
  text: string;
  flags?: AiFlag[];
  activeWordIdx?: number;
  liveWords?: readonly LiveWord[];
  liveAlignment?: readonly AlignmentEntry[];
}>(), { flags: () => [], activeWordIdx: -1, liveWords: undefined, liveAlignment: undefined });

const emit = defineEmits<{ (e: 'wordClick', idx: number): void }>();

const useAlignment = computed(() => !!props.liveAlignment?.length);
const useLive = computed(() => !useAlignment.value && !!props.liveWords?.length);

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

// O(1) alignment lookup keyed by gemini_idx. Used only on the alignment path.
const alignmentByIdx = computed<Map<number, AlignmentEntry>>(() => {
  const m = new Map<number, AlignmentEntry>();
  (props.liveAlignment || []).forEach((a) => m.set(a.g, a));
  return m;
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

function alignClassFor(item: WordEntry): string {
  if (item.kind === 'space') return '';
  const entry = alignmentByIdx.value.get(item.idx);
  const matched = !!entry && entry.s !== null && entry.e !== null;
  const kind = flagByWord.value.get(item.idx);
  // Matched words carry the .dw class so the TranscriptPane time watcher
  // (`querySelectorAll('.dw[data-ws]')`) picks them up. Unmatched words
  // render as plain .word so the watcher skips them entirely.
  const parts = matched ? ['word', 'dw'] : ['word', 'word--unmatched'];
  if (kind) parts.push(`flag-${kind}`);
  return parts.join(' ');
}

function alignAttrsFor(item: WordEntry): Record<string, number> {
  if (item.kind === 'space') return {};
  const entry = alignmentByIdx.value.get(item.idx);
  if (!entry || entry.s === null || entry.e === null) return {};
  return { 'data-ws': entry.s / 1000, 'data-we': entry.e / 1000 };
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
  <span class="segment__text" :style="{ whiteSpace: 'pre-wrap' }">
    <template v-if="useAlignment">
      <span
        v-for="(item, i) in items"
        :key="i"
        :class="alignClassFor(item)"
        v-bind="alignAttrsFor(item)"
        @click="onClick(item, $event)"
      >{{ item.tok }}</span>
    </template>
    <template v-else-if="useLive">
      <span
        v-for="(w, i) in props.liveWords"
        :key="i"
        :class="liveClassFor(i)"
        :data-ws="w.start_ms / 1000"
        :data-we="w.end_ms / 1000"
        @click="onLiveClick(i, $event)"
      >{{ w.word }}{{ i < (props.liveWords?.length ?? 0) - 1 ? ' ' : '' }}</span>
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
