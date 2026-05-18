<script setup lang="ts">
/**
 * SegmentText — verbatim port of components.jsx::SegmentText (266-292).
 * Renders a segment's words as clickable spans with per-word AI-flag classes
 * and karaoke-style is-current highlight on the active word.
 */
import { computed } from 'vue';
import type { AiFlag } from '@/fixtures/transcript';

const props = withDefaults(defineProps<{
  text: string;
  flags?: AiFlag[];
  activeWordIdx?: number;
}>(), { flags: () => [], activeWordIdx: -1 });

const emit = defineEmits<{ (e: 'wordClick', idx: number): void }>();

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

function onClick(item: WordEntry, e: MouseEvent): void {
  if (item.kind !== 'word') return;
  e.stopPropagation();
  emit('wordClick', item.idx);
}
</script>

<template>
  <span class="segment__text">
    <span
      v-for="(item, i) in items"
      :key="i"
      :class="classFor(item)"
      @click="onClick(item, $event)"
    >{{ item.tok }}</span>
  </span>
</template>
