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
 *
 * Phase 3.5 + 4 (2026-06-06) — split/merge wiring:
 *   When the optional `sessionId` + `segmentId` props are provided AND the
 *   featureFlags store's `splitMergeEnabled` is true, the segment surface
 *   becomes interactive for structural edits:
 *     • Right-click → context menu with "Split here" / "Merge with previous"
 *       / "Merge with next". "Split here" is only enabled when the caret
 *       sits adjacent to a `.dw[data-w-idx]` word span (so we can resolve
 *       `after_word_index`). Merge entries are only enabled when the
 *       corresponding neighbor prop is set.
 *     • Keystrokes (when this segment has focus):
 *         Ctrl+Shift+S → split at the current caret word position
 *         Ctrl+Shift+M → merge-up (this with previous)
 *     • On success the component emits `segments-changed`; the parent
 *       (TranscriptPane / EditorView) is expected to refetch segments.
 *     • Error handling per plan §4.8:
 *         409 SPLIT_MERGE_BUSY        → toast + one retry after 1s
 *         409 MERGE_NEIGHBOR_CHANGED  → toast + emit `reload-required`
 *         503 SPLIT_MERGE_DISABLED    → defensive toast (flag should hide UI)
 *   See docs/plans/2026-06-06-002-phase-3.5-split-merge-executor-v2.md §4.6.
 */
import { computed, nextTick, onBeforeUnmount, ref, useTemplateRef } from 'vue';
import type { AiFlag } from '@/fixtures/transcript';
import { corrections as correctionsApi } from '@/services/api';
import { toast } from '@/composables/useToast';
import { ApiError } from '@/services/http';
import { useFeatureFlagsStore } from '@/stores/featureFlags';

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
  // Phase 3.5 + 4 — split/merge context. All optional so the existing
  // STTPane / DiscrepanciesPane callers (which don't need split/merge)
  // continue to render unchanged. When sessionId + segmentId are present
  // AND the featureFlags.splitMergeEnabled flag is true, the right-click
  // menu + keystrokes activate.
  sessionId?: string;
  segmentId?: string;
  prevSegmentId?: string | null;
  nextSegmentId?: string | null;
}>(), {
  flags: () => [],
  activeWordIdx: -1,
  liveWords: undefined,
  liveAlignment: undefined,
  sessionId: undefined,
  segmentId: undefined,
  prevSegmentId: null,
  nextSegmentId: null,
});

const emit = defineEmits<{
  (e: 'wordClick', idx: number): void;
  (e: 'segments-changed'): void;
  (e: 'reload-required'): void;
}>();

const featureFlags = useFeatureFlagsStore();
const splitMergeActive = computed(
  () => featureFlags.splitMergeEnabled && !!props.sessionId && !!props.segmentId,
);

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

// ─── Phase 3.5 + 4 — split/merge UI ────────────────────────────────────────

interface MenuState {
  x: number;
  y: number;
  afterWordIndex: number | null;  // null = caret not adjacent to a word span
}

const rootRef = useTemplateRef<HTMLSpanElement>('rootRef');
const menu = ref<MenuState | null>(null);

/**
 * Resolve `after_word_index` from the current selection / caret. Strategy:
 *   1. Walk up from the caret's anchor node until we find an element with
 *      data-w-idx (a `.dw` span). If the caret offset is at the very start
 *      of that element, treat the split as "after the previous word"
 *      (data-w-idx - 1). Otherwise treat as "after this word" (data-w-idx).
 *   2. If the caret sits in a whitespace text node between two .dw spans,
 *      use the previous-sibling's data-w-idx as `after_word_index`.
 * Returns null when the caret isn't inside this segment or is at the very
 * start (which would leave 0 words on the left).
 */
function readWordIdx(el: HTMLElement): number | null {
  const raw = el.dataset.wIdx;
  if (raw == null) return null;
  const idx = Number.parseInt(raw, 10);
  return Number.isNaN(idx) ? null : idx;
}

function findEnclosingWordSpan(node: Node | null, root: HTMLElement): HTMLElement | null {
  let cursor: Node | null = node;
  while (cursor && cursor !== root) {
    if (cursor.nodeType === 1 && (cursor as HTMLElement).dataset.wIdx != null) {
      return cursor as HTMLElement;
    }
    cursor = cursor.parentNode;
  }
  return null;
}

function previousWordIdxSibling(start: Node): number | null {
  let probe: Node | null = start.previousSibling;
  while (probe) {
    if (probe.nodeType === 1 && (probe as HTMLElement).dataset.wIdx != null) {
      return readWordIdx(probe as HTMLElement);
    }
    probe = probe.previousSibling;
  }
  return null;
}

function resolveAfterWordIndex(): number | null {
  const root = rootRef.value;
  if (!root) return null;
  const sel = globalThis.getSelection();
  if (!sel || sel.rangeCount === 0) return null;
  const range = sel.getRangeAt(0);
  const node: Node = range.startContainer;
  if (!root.contains(node)) return null;

  const el = findEnclosingWordSpan(node, root);
  if (el) {
    const idx = readWordIdx(el);
    if (idx == null) return null;
    // If caret is at very start of this word span, split BEFORE it
    // (i.e., after idx-1). Otherwise split AFTER it.
    if (node.nodeType === 3 && range.startOffset === 0 && node === el.firstChild) {
      return idx - 1;
    }
    return idx;
  }
  // Caret in whitespace between word spans — use previous .dw sibling.
  if (node.nodeType === 3) return previousWordIdxSibling(node);
  return null;
}

function closeMenu(): void {
  menu.value = null;
}

function coerceCaretFromPoint(x: number, y: number): void {
  const doc = document as Document & {
    caretRangeFromPoint?: (x: number, y: number) => Range | null;
    caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null;
  };
  const sel = globalThis.getSelection();
  if (!sel) return;
  if (typeof doc.caretRangeFromPoint === 'function') {
    const r = doc.caretRangeFromPoint(x, y);
    if (r) { sel.removeAllRanges(); sel.addRange(r); }
    return;
  }
  if (typeof doc.caretPositionFromPoint === 'function') {
    const pos = doc.caretPositionFromPoint(x, y);
    if (pos) {
      const r = document.createRange();
      r.setStart(pos.offsetNode, pos.offset);
      r.collapse(true);
      sel.removeAllRanges();
      sel.addRange(r);
    }
  }
}

function onContextMenu(e: MouseEvent): void {
  if (!splitMergeActive.value) return;
  e.preventDefault();
  e.stopPropagation();
  // Some browsers don't set the caret on right-click; coerce it.
  try { coerceCaretFromPoint(e.clientX, e.clientY); } catch { /* best-effort */ }
  const afterWordIndex = resolveAfterWordIndex();
  menu.value = { x: e.clientX, y: e.clientY, afterWordIndex };
}

// Dismiss the menu on any outside interaction.
function onDocClick(e: MouseEvent): void {
  if (!menu.value) return;
  const target = e.target as Node | null;
  // If the click lands inside the menu itself, the menu handlers deal with it.
  const menuEl = document.getElementById('segment-text-context-menu');
  if (menuEl && target && menuEl.contains(target)) return;
  closeMenu();
}
function onDocEsc(e: KeyboardEvent): void {
  if (e.key === 'Escape') closeMenu();
}
document.addEventListener('click', onDocClick, true);
document.addEventListener('keydown', onDocEsc, true);
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick, true);
  document.removeEventListener('keydown', onDocEsc, true);
});

function handleApiError(e: unknown, op: 'split' | 'merge'): 'busy' | 'neighbor' | 'disabled' | 'other' {
  if (!(e instanceof ApiError)) return 'other';
  const body = e.body as { error?: { code?: string; message?: string } } | null;
  const code = body?.error?.code || '';
  if (e.status === 409 && code === 'SPLIT_MERGE_BUSY') {
    toast.push('Another edit in progress. Retrying...', { tone: 'warn' });
    return 'busy';
  }
  if (e.status === 409 && code === 'MERGE_NEIGHBOR_CHANGED') {
    toast.push('The segment after this changed. Reloading.', { tone: 'warn' });
    emit('reload-required');
    return 'neighbor';
  }
  if (e.status === 503 && code === 'SPLIT_MERGE_DISABLED') {
    toast.push('Split/merge disabled.', { tone: 'warn' });
    return 'disabled';
  }
  toast.push(body?.error?.message || `${op === 'split' ? 'Split' : 'Merge'} failed.`, { tone: 'error' });
  return 'other';
}

async function callSplitOnce(afterWordIndex: number): Promise<void> {
  await correctionsApi.splitSegment(props.sessionId!, props.segmentId!, afterWordIndex);
  emit('segments-changed');
}

async function callMergeOnce(leftId: string, rightId: string): Promise<void> {
  await correctionsApi.mergeSegment(props.sessionId!, leftId, rightId);
  emit('segments-changed');
}

async function doSplit(afterWordIndex: number): Promise<void> {
  if (!props.sessionId || !props.segmentId) return;
  if (afterWordIndex < 0) {
    toast.push('Place the cursor between two words to split.', { tone: 'warn' });
    return;
  }
  try {
    await callSplitOnce(afterWordIndex);
  } catch (e) {
    const kind = handleApiError(e, 'split');
    if (kind === 'busy') {
      setTimeout(() => {
        callSplitOnce(afterWordIndex).catch((error_) => handleApiError(error_, 'split'));
      }, 1000);
    }
  }
}

async function doMerge(leftId: string, rightId: string): Promise<void> {
  if (!props.sessionId) return;
  try {
    await callMergeOnce(leftId, rightId);
  } catch (e) {
    const kind = handleApiError(e, 'merge');
    if (kind === 'busy') {
      setTimeout(() => {
        callMergeOnce(leftId, rightId).catch((error_) => handleApiError(error_, 'merge'));
      }, 1000);
    }
  }
}

function onMenuSplit(): void {
  const idx = menu.value?.afterWordIndex;
  closeMenu();
  if (idx == null) return;
  doSplit(idx).catch(() => { /* handled inside */ });
}
function onMenuMergePrev(): void {
  closeMenu();
  if (!props.prevSegmentId || !props.segmentId) return;
  doMerge(props.prevSegmentId, props.segmentId).catch(() => { /* handled inside */ });
}
function onMenuMergeNext(): void {
  closeMenu();
  if (!props.segmentId || !props.nextSegmentId) return;
  doMerge(props.segmentId, props.nextSegmentId).catch(() => { /* handled inside */ });
}

function onKeyDown(e: KeyboardEvent): void {
  if (!splitMergeActive.value) return;
  // Match Ctrl+Shift+S / Ctrl+Shift+M, but also accept Cmd on macOS so the
  // shortcut survives on both platforms. Avoid stomping Ctrl+S (browser save).
  const isMod = e.ctrlKey || e.metaKey;
  if (!isMod || !e.shiftKey) return;
  const key = e.key.toLowerCase();
  if (key === 's') {
    e.preventDefault();
    const idx = resolveAfterWordIndex();
    if (idx == null) {
      toast.push('Place the cursor between two words to split.', { tone: 'warn' });
      return;
    }
    doSplit(idx).catch(() => { /* handled inside */ });
  } else if (key === 'm') {
    e.preventDefault();
    if (!props.prevSegmentId || !props.segmentId) {
      toast.push('No previous segment to merge with.', { tone: 'warn' });
      return;
    }
    doMerge(props.prevSegmentId, props.segmentId).catch(() => { /* handled inside */ });
  }
}

// Position the floating menu after Vue paints it, so its computed size
// stays inside the viewport.
function clampMenuPos(): void {
  if (!menu.value) return;
  nextTick(() => {
    const el = document.getElementById('segment-text-context-menu');
    if (!el || !menu.value) return;
    const rect = el.getBoundingClientRect();
    const vw = globalThis.innerWidth;
    const vh = globalThis.innerHeight;
    let x = menu.value.x;
    let y = menu.value.y;
    if (x + rect.width + 4 > vw) x = Math.max(4, vw - rect.width - 4);
    if (y + rect.height + 4 > vh) y = Math.max(4, vh - rect.height - 4);
    if (x !== menu.value.x || y !== menu.value.y) {
      menu.value = { ...menu.value, x, y };
    }
  }).catch(() => { /* no-op */ });
}
</script>

<template>
  <span
    ref="rootRef"
    class="segment__text"
    :style="{ whiteSpace: 'pre-wrap' }"
    :tabindex="splitMergeActive ? 0 : undefined"
    @contextmenu="onContextMenu"
    @keydown="onKeyDown"
  >
    <template v-if="useAlignment">
      <span
        v-for="(item, i) in items"
        :key="i"
        :class="alignClassFor(item)"
        :data-w-idx="item.kind === 'word' ? item.idx : undefined"
        v-bind="alignAttrsFor(item)"
        @click="onClick(item, $event)"
      >{{ item.tok }}</span>
    </template>
    <template v-else-if="useLive">
      <span
        v-for="(w, i) in props.liveWords"
        :key="i"
        :class="liveClassFor(i)"
        :data-w-idx="i"
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
        :data-w-idx="item.kind === 'word' ? item.idx : undefined"
        @click="onClick(item, $event)"
      >{{ item.tok }}</span>
    </template>

    <Teleport v-if="menu && splitMergeActive" to="body">
      <div
        id="segment-text-context-menu"
        role="menu"
        :style="{
          position: 'fixed',
          left: menu.x + 'px',
          top: menu.y + 'px',
          zIndex: 10000,
          background: 'var(--bg2, #1b2027)',
          color: 'var(--fg, #e9eef5)',
          border: '1px solid rgba(255,255,255,0.10)',
          borderRadius: '8px',
          padding: '4px',
          minWidth: '180px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
          fontSize: '12.5px',
        }"
        @click.stop
        v-on:vue:mounted="clampMenuPos"
      >
        <button
          role="menuitem"
          :disabled="menu.afterWordIndex == null || menu.afterWordIndex < 0"
          :style="{
            display: 'block', width: '100%', textAlign: 'left',
            padding: '6px 10px', border: 'none', background: 'transparent',
            color: 'inherit', cursor: menu.afterWordIndex != null && menu.afterWordIndex >= 0 ? 'pointer' : 'not-allowed',
            opacity: menu.afterWordIndex != null && menu.afterWordIndex >= 0 ? 1 : 0.4,
            borderRadius: '4px',
          }"
          @click="onMenuSplit"
        >Split here</button>
        <button
          role="menuitem"
          :disabled="!prevSegmentId"
          :style="{
            display: 'block', width: '100%', textAlign: 'left',
            padding: '6px 10px', border: 'none', background: 'transparent',
            color: 'inherit', cursor: prevSegmentId ? 'pointer' : 'not-allowed',
            opacity: prevSegmentId ? 1 : 0.4,
            borderRadius: '4px',
          }"
          @click="onMenuMergePrev"
        >Merge with previous</button>
        <button
          role="menuitem"
          :disabled="!nextSegmentId"
          :style="{
            display: 'block', width: '100%', textAlign: 'left',
            padding: '6px 10px', border: 'none', background: 'transparent',
            color: 'inherit', cursor: nextSegmentId ? 'pointer' : 'not-allowed',
            opacity: nextSegmentId ? 1 : 0.4,
            borderRadius: '4px',
          }"
          @click="onMenuMergeNext"
        >Merge with next</button>
      </div>
    </Teleport>
  </span>
</template>
