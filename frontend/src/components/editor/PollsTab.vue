<script setup lang="ts">
/**
 * PollsTab — verbatim port of editor.jsx::PollsTab (302-352).
 * Right-rail "Polls" sub-tab: poll cards with winner-highlighted bars,
 * draggable to segments, placed-state pill + place/remove.
 */
import { computed } from 'vue';
import type { Poll } from '@/fixtures/chat_polls';
import type { Slide, Segment } from '@/fixtures/transcript';

const props = defineProps<{
  polls: readonly Poll[];
  segmentsById: Map<string, Segment>;
  slides: readonly Slide[];
  placements: Record<string, string | null>;
}>();

const emit = defineEmits<{
  (e: 'unplace', id: string): void;
  (e: 'placeAtActive', id: string): void;
}>();

const placedCount = computed(() => props.polls.filter((p) => props.placements[p.id]).length);

function placedSlide(pollId: string): Slide | null {
  const segId = props.placements[pollId];
  if (!segId) return null;
  const seg = props.segmentsById.get(segId);
  if (!seg) return null;
  return props.slides.find((s) => s.id === seg.slide_id) ?? null;
}

function maxVotes(p: Poll): number {
  return Math.max(...p.options.map((o) => o.votes));
}

function onDragStart(e: DragEvent, pollId: string): void {
  if (!e.dataTransfer) return;
  e.dataTransfer.setData('application/vnd.mic.anchor', pollId);
  e.dataTransfer.effectAllowed = 'move';
}
</script>

<template>
  <div>
    <div class="rightrail__sectionhead" :style="{ display: 'flex', justifyContent: 'space-between' }">
      <span>Polls · {{ polls.length }}</span>
      <span :style="{ color: 'var(--color-green)' }">{{ placedCount }} placed</span>
    </div>
    <div
      v-for="p in polls"
      :key="p.id"
      :class="['poll-card', placements[p.id] ? 'is-placed' : '']"
      :draggable="!placements[p.id]"
      @dragstart="(e) => onDragStart(e as DragEvent, p.id)"
    >
      <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }">
        <span v-if="placements[p.id]" class="chat-msg__placed">
          PLACED · Slide {{ placedSlide(p.id) ? String(placedSlide(p.id)!.n).padStart(2, '0') : '?' }}
        </span>
        <span v-else class="chip chip--gold" :style="{ fontSize: '9px' }">Poll · {{ p.status }}</span>
        <button
          v-if="placements[p.id]"
          class="chat-msg__unplace"
          @click="emit('unplace', p.id)"
        >× Remove</button>
        <button v-else class="chat-msg__place" @click="emit('placeAtActive', p.id)">Place</button>
      </div>
      <p class="poll-card__q">{{ p.question }}</p>
      <div v-for="opt in p.options" :key="opt.id" :class="['poll-card__opt', opt.votes === maxVotes(p) ? 'is-winner' : '']">
        <div class="poll-card__opt-bar" :style="{ width: `${Math.round((opt.votes / p.total) * 100)}%` }" />
        <div class="poll-card__opt-row">
          <span class="poll-card__opt-label">{{ opt.label }}</span>
          <span class="poll-card__opt-pct">{{ Math.round((opt.votes / p.total) * 100) }}% · {{ opt.votes }}</span>
        </div>
      </div>
      <div class="poll-card__foot">
        <span>Total: {{ p.total }} votes</span>
        <span v-if="!placements[p.id]" :style="{ color: 'var(--fg2)', fontSize: '11px' }">⠿ drag to segment</span>
      </div>
    </div>
  </div>
</template>
