<script setup lang="ts">
/**
 * ChatTab — verbatim port of editor.jsx::ChatTab (237-300).
 * Right-rail "Chat" sub-tab: chat list grouped by slide divider, draggable to
 * a segment in the transcript pane, with placed-state pill + remove control.
 *
 * Phase 6.2 (2026-06-05): adds a dedicated grip handle per row for list
 * reordering. The grip uses a separate `application/vnd.rounds.reorder-chat`
 * mime type so reorder drags can't be consumed by segment placement drop
 * targets (which only look at `application/vnd.mic.anchor`). The whole-row
 * placement drag is unchanged — grabbing the row body still drags it to
 * a segment as before.
 */
import { computed, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import Avatar from '@/components/shared/Avatar.vue';
import type { ChatMessage } from '@/fixtures/chat_polls';
import type { Slide, Segment } from '@/fixtures/transcript';
import { fmtTime } from '@/utils/editorHelpers';

const REORDER_MIME = 'application/vnd.rounds.reorder-chat';

const props = defineProps<{
  chat: readonly ChatMessage[];
  slides: readonly Slide[];
  segmentsById: Map<string, Segment>;
  placements: Record<string, string | null>;
}>();

const emit = defineEmits<{
  (e: 'unplace', id: string): void;
  (e: 'placeAtActive', id: string): void;
  (e: 'reorder', ids: string[]): void;
}>();

interface DividerRow { divider: true; slide: Slide; }
interface MsgRow { divider: false; msg: ChatMessage; seg: Segment | undefined; }
type Row = DividerRow | MsgRow;

const grouped = computed<Row[]>(() => {
  const out: Row[] = [];
  let curSlide: string | null = null;
  props.chat.forEach((c) => {
    const seg = props.segmentsById.get(c.anchor);
    const sl = seg ? props.slides.find((s) => s.id === seg.slide_id) : null;
    if (sl && sl.id !== curSlide) {
      out.push({ divider: true, slide: sl });
      curSlide = sl.id;
    }
    out.push({ divider: false, msg: c, seg });
  });
  return out;
});

const placedCount = computed(() => props.chat.filter((c) => props.placements[c.id]).length);

function placedSlide(msgId: string): Slide | null {
  const segId = props.placements[msgId];
  if (!segId) return null;
  const seg = props.segmentsById.get(segId);
  if (!seg) return null;
  return props.slides.find((s) => s.id === seg.slide_id) ?? null;
}

function onDragStart(e: DragEvent, msgId: string): void {
  if (!e.dataTransfer) return;
  e.dataTransfer.setData('application/vnd.mic.anchor', msgId);
  e.dataTransfer.effectAllowed = 'move';
}

// ── Reorder drag (Phase 6.2) ─────────────────────────────────────────
// Reorder operates on the *flat* chat list, not the grouped (divider +
// row) array. Grouping is purely visual; ordering is by id sequence.
const dropTargetId = ref<string | null>(null);
let reorderSourceId: string | null = null;

function onReorderStart(e: DragEvent, msgId: string): void {
  if (!e.dataTransfer) return;
  e.stopPropagation();
  reorderSourceId = msgId;
  e.dataTransfer.setData(REORDER_MIME, msgId);
  e.dataTransfer.effectAllowed = 'move';
}

function onReorderOver(e: DragEvent, targetMsgId: string): void {
  if (!e.dataTransfer) return;
  // Only show drop indicator if the active drag is a reorder. types[]
  // is the only way to inspect the data store mid-drag without firing
  // a drop — getData() returns empty during dragover.
  const types = e.dataTransfer.types;
  if (!Array.from(types).includes(REORDER_MIME)) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  dropTargetId.value = targetMsgId;
}

function onReorderLeave(targetMsgId: string): void {
  if (dropTargetId.value === targetMsgId) dropTargetId.value = null;
}

function onReorderDrop(e: DragEvent, targetMsgId: string): void {
  dropTargetId.value = null;
  if (!e.dataTransfer) return;
  const sourceId = e.dataTransfer.getData(REORDER_MIME) || reorderSourceId;
  reorderSourceId = null;
  if (!sourceId || sourceId === targetMsgId) return;
  e.preventDefault();
  e.stopPropagation();
  const ids = props.chat.map((c) => c.id);
  const fromIdx = ids.indexOf(sourceId);
  const toIdx = ids.indexOf(targetMsgId);
  if (fromIdx < 0 || toIdx < 0) return;
  ids.splice(fromIdx, 1);
  ids.splice(toIdx, 0, sourceId);
  emit('reorder', ids);
}

function onReorderEnd(): void {
  dropTargetId.value = null;
  reorderSourceId = null;
}

function trim32(t: string): string {
  return t.length > 32 ? t.slice(0, 32) + '…' : t;
}
</script>

<template>
  <div>
    <div class="rightrail__sectionhead" :style="{ display: 'flex', justifyContent: 'space-between' }">
      <span>Chat · {{ chat.length }}</span>
      <span :style="{ color: 'var(--color-green)' }">{{ placedCount }} placed</span>
    </div>
    <template v-for="(row, i) in grouped" :key="i">
      <div v-if="row.divider" class="chat-divider">
        Slide {{ String(row.slide.n).padStart(2, '0') }} · {{ trim32(row.slide.title) }}
      </div>
      <div
        v-else
        :class="['chat-msg', placements[row.msg.id] ? 'is-placed' : '', dropTargetId === row.msg.id ? 'is-reorder-target' : '']"
        :draggable="true"
        @dragstart="(e) => onDragStart(e as DragEvent, row.msg.id)"
        @dragover="(e) => onReorderOver(e as DragEvent, row.msg.id)"
        @dragleave="() => onReorderLeave(row.msg.id)"
        @drop="(e) => onReorderDrop(e as DragEvent, row.msg.id)"
      >
        <span
          class="chat-msg__reorder-grip"
          draggable="true"
          title="Drag to reorder"
          @dragstart="(e) => onReorderStart(e as DragEvent, row.msg.id)"
          @dragend="onReorderEnd"
        >⇅</span>
        <div class="chat-msg__head">
          <Avatar :name="row.msg.author.replace(/^Dr\. /, '')" :size="20" :ring="false" />
          <span class="chat-msg__author">{{ row.msg.author }}</span>
          <span class="chat-msg__t">{{ fmtTime(row.msg.t) }}</span>
        </div>
        <div class="chat-msg__body">{{ row.msg.text }}</div>
        <div class="chat-msg__foot">
          <template v-if="placements[row.msg.id]">
            <span class="chat-msg__placed">
              <Icon name="anchor" :size="10" /> PLACED · Slide {{ placedSlide(row.msg.id) ? String(placedSlide(row.msg.id)!.n).padStart(2, '0') : '?' }}
            </span>
            <button class="chat-msg__unplace" @click="emit('unplace', row.msg.id)">× Remove</button>
          </template>
          <template v-else>
            <span class="chat-msg__draghint">⠿ drag to segment</span>
            <button class="chat-msg__place" @click="emit('placeAtActive', row.msg.id)">Place at active</button>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.chat-msg { position: relative; }
.chat-msg__reorder-grip {
  position: absolute;
  top: 6px;
  right: 6px;
  font-size: 11px;
  line-height: 1;
  color: var(--fg2, #6b7280);
  cursor: grab;
  user-select: none;
  padding: 2px 4px;
  border-radius: 3px;
  opacity: 0;
  transition: opacity 0.12s;
}
.chat-msg:hover .chat-msg__reorder-grip { opacity: 0.7; }
.chat-msg__reorder-grip:hover { opacity: 1; background: var(--surface-hover, rgba(0,0,0,0.05)); }
.chat-msg__reorder-grip:active { cursor: grabbing; }
.chat-msg.is-reorder-target {
  border-top: 2px solid var(--color-blue, #0861CE);
  margin-top: -1px;
}
</style>
