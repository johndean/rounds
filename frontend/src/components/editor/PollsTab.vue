<script setup lang="ts">
/**
 * PollsTab — verbatim port of editor.jsx::PollsTab (302-352).
 * Right-rail "Polls" sub-tab: poll cards with winner-highlighted bars,
 * draggable to segments, placed-state pill + place/remove.
 *
 * Phase 6.2 (2026-06-05): adds a dedicated grip handle per row for list
 * reordering. Mirror of ChatTab.vue — uses a separate mime type so the
 * existing segment-placement drag remains the row body's behavior.
 */
import { computed, ref } from 'vue';
import type { Poll } from '@/fixtures/chat_polls';
import type { Slide, Segment } from '@/fixtures/transcript';

const REORDER_MIME = 'application/vnd.rounds.reorder-poll';

const props = defineProps<{
  polls: readonly Poll[];
  segmentsById: Map<string, Segment>;
  slides: readonly Slide[];
  placements: Record<string, string | null>;
}>();

const emit = defineEmits<{
  (e: 'unplace', id: string): void;
  (e: 'placeAtActive', id: string): void;
  (e: 'reorder', ids: string[]): void;
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

// ── Reorder drag (Phase 6.2) — same shape as ChatTab.vue ─────────────
const dropTargetId = ref<string | null>(null);
let reorderSourceId: string | null = null;

function onReorderStart(e: DragEvent, pollId: string): void {
  if (!e.dataTransfer) return;
  e.stopPropagation();
  reorderSourceId = pollId;
  e.dataTransfer.setData(REORDER_MIME, pollId);
  e.dataTransfer.effectAllowed = 'move';
}

function onReorderOver(e: DragEvent, targetPollId: string): void {
  if (!e.dataTransfer) return;
  const types = e.dataTransfer.types;
  if (!Array.from(types).includes(REORDER_MIME)) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  dropTargetId.value = targetPollId;
}

function onReorderLeave(targetPollId: string): void {
  if (dropTargetId.value === targetPollId) dropTargetId.value = null;
}

function onReorderDrop(e: DragEvent, targetPollId: string): void {
  dropTargetId.value = null;
  if (!e.dataTransfer) return;
  const sourceId = e.dataTransfer.getData(REORDER_MIME) || reorderSourceId;
  reorderSourceId = null;
  if (!sourceId || sourceId === targetPollId) return;
  e.preventDefault();
  e.stopPropagation();
  const ids = props.polls.map((p) => p.id);
  const fromIdx = ids.indexOf(sourceId);
  const toIdx = ids.indexOf(targetPollId);
  if (fromIdx < 0 || toIdx < 0) return;
  ids.splice(fromIdx, 1);
  ids.splice(toIdx, 0, sourceId);
  emit('reorder', ids);
}

function onReorderEnd(): void {
  dropTargetId.value = null;
  reorderSourceId = null;
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
      :class="['poll-card', placements[p.id] ? 'is-placed' : '', dropTargetId === p.id ? 'is-reorder-target' : '']"
      :draggable="!placements[p.id]"
      @dragstart="(e) => onDragStart(e as DragEvent, p.id)"
      @dragover="(e) => onReorderOver(e as DragEvent, p.id)"
      @dragleave="() => onReorderLeave(p.id)"
      @drop="(e) => onReorderDrop(e as DragEvent, p.id)"
    >
      <span
        class="poll-card__reorder-grip"
        draggable="true"
        title="Drag to reorder"
        @dragstart="(e) => onReorderStart(e as DragEvent, p.id)"
        @dragend="onReorderEnd"
      >⇅</span>
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

<style scoped>
.poll-card { position: relative; }
.poll-card__reorder-grip {
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
  z-index: 1;
}
.poll-card:hover .poll-card__reorder-grip { opacity: 0.7; }
.poll-card__reorder-grip:hover { opacity: 1; background: var(--surface-hover, rgba(0,0,0,0.05)); }
.poll-card__reorder-grip:active { cursor: grabbing; }
.poll-card.is-reorder-target {
  border-top: 2px solid var(--color-blue, #0861CE);
  margin-top: -1px;
}
</style>
