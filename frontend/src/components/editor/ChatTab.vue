<script setup lang="ts">
/**
 * ChatTab — verbatim port of editor.jsx::ChatTab (237-300).
 * Right-rail "Chat" sub-tab: chat list grouped by slide divider, draggable to
 * a segment in the transcript pane, with placed-state pill + remove control.
 */
import { computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import Avatar from '@/components/shared/Avatar.vue';
import type { ChatMessage } from '@/fixtures/chat_polls';
import type { Slide, Segment } from '@/fixtures/transcript';
import { fmtTime } from '@/utils/editorHelpers';

const props = defineProps<{
  chat: readonly ChatMessage[];
  slides: readonly Slide[];
  segmentsById: Map<string, Segment>;
  placements: Record<string, string | null>;
}>();

const emit = defineEmits<{
  (e: 'unplace', id: string): void;
  (e: 'placeAtActive', id: string): void;
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
        :class="['chat-msg', placements[row.msg.id] ? 'is-placed' : '']"
        :draggable="!placements[row.msg.id]"
        @dragstart="(e) => onDragStart(e as DragEvent, row.msg.id)"
      >
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
