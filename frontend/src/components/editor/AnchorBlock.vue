<script setup lang="ts">
/**
 * AnchorBlock — verbatim port of editor.jsx::AnchorBlock (355-450).
 * Inline-in-transcript anchor: shows a chat message or a poll attached to a
 * segment; supports inline edit (toolbar + textarea) and remove.
 */
import { ref, computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import type { Slide } from '@/fixtures/transcript';
import type { ChatMessage, Poll } from '@/fixtures/chat_polls';
import { fmtTime } from '@/utils/editorHelpers';
import { toast } from '@/composables/useToast';

type AnchorItem = (ChatMessage & { kind: 'chat' }) | (Poll & { kind: 'chat' | 'poll' });

const props = defineProps<{
  item: AnchorItem;
  kind: 'chat' | 'poll';
  slide: Slide | null | undefined;
}>();

const emit = defineEmits<{ (e: 'remove', id: string): void }>();

const editing = ref(false);
const draft = ref(props.kind === 'chat' ? (props.item as ChatMessage).text : (props.item as Poll).question);

const accent = computed(() => (props.kind === 'poll' ? 'var(--color-green)' : 'var(--color-gold)'));

const headerTitle = computed(() => {
  if (props.kind === 'poll') {
    const q = (props.item as Poll).question;
    return `Poll · ${q.slice(0, 60)}${q.length > 60 ? '…' : ''}`;
  }
  return `Chat · ${(props.item as ChatMessage).author}`;
});

const maxVotes = computed(() => {
  if (props.kind !== 'poll') return 0;
  return Math.max(...(props.item as Poll).options.map((o) => o.votes));
});

function save(): void {
  toast.push(props.kind === 'chat' ? 'Chat message saved' : 'Poll saved', { tone: 'success' });
  editing.value = false;
}

function startEdit(): void {
  draft.value = props.kind === 'chat' ? (props.item as ChatMessage).text : (props.item as Poll).question;
  editing.value = true;
}
</script>

<template>
  <article
    :class="['segment', 'segment--anchor', `segment--anchor-${kind}`]"
    :data-anchor-id="item.id"
    :draggable="!editing"
    @dragstart.stop
  >
    <header class="segment__header">
      <span class="segment__slide-chip">
        <span :style="{ width: '6px', height: '6px', borderRadius: '50%', background: accent }" />
        <strong>{{ slide ? String(slide.n).padStart(2, '0') : '—' }}</strong>
        <span :style="{ opacity: 0.5 }">·</span>
        <span>{{ headerTitle }}</span>
      </span>
      <span class="segment__inline-actions">
        <span v-if="kind === 'poll'" class="chip chip--green" :style="{ fontSize: '9px', padding: '2px 7px' }">
          <Icon name="list" :size="9" /> Poll
        </span>
        <span v-else class="chip chip--gold" :style="{ fontSize: '9px', padding: '2px 7px' }">
          <Icon name="message" :size="9" /> Chat
        </span>
        <button v-if="!editing" class="segment__inline-action" @click.stop="startEdit">Edit</button>
        <button class="segment__inline-action segment__inline-action--danger" @click.stop="emit('remove', item.id)">
          <Icon name="x" :size="10" /> Remove
        </button>
      </span>
    </header>
    <div class="segment__body">
      <div class="segment__gutter">
        <span class="segment__time">{{ fmtTime(item.t) }}</span>
        <span class="segment__speaker-pill" :style="{ color: accent }">{{ kind === 'poll' ? 'Poll' : 'Chat' }}</span>
      </div>
      <div class="segment__main">
        <div v-if="editing" class="segment-editor" :style="{ width: '100%' }">
          <textarea
            v-model="draft"
            class="segment-editor__textarea"
            wrap="soft"
            :style="{ width: '100%', minHeight: kind === 'poll' ? '60px' : '110px' }"
            :rows="kind === 'poll' ? 2 : 4"
            @click.stop
          />
          <div v-if="kind === 'poll'" :style="{ padding: '8px 14px', borderTop: '1px solid var(--border-subtle)', background: 'var(--surface-bg)' }">
            <div class="impv-lbl" :style="{ marginBottom: '8px' }">Options ({{ (item as Poll).options.length }})</div>
            <div
              v-for="opt in (item as Poll).options"
              :key="opt.id"
              :style="{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }"
            >
              <input :value="opt.label" class="impv-input" :style="{ flex: 1, fontSize: '12.5px', padding: '5px 8px' }" />
              <span :style="{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--fg2)', width: '56px', textAlign: 'right' }">{{ opt.votes }} votes</span>
            </div>
          </div>
          <div class="segment-editor__foot">
            <button class="btn btn--secondary btn--sm" @click.stop="editing = false">Cancel</button>
            <button class="btn btn--sm" :style="{ background: 'var(--color-green)', color: '#fff' }" @click.stop="save">Save</button>
          </div>
        </div>
        <div v-else-if="kind === 'chat'" :style="{ fontSize: '14px', lineHeight: 1.55, color: 'var(--fg1)' }">
          <div :style="{ fontWeight: 700, marginBottom: '4px' }">{{ (item as ChatMessage).author }}:</div>
          <div>{{ (item as ChatMessage).text }}</div>
        </div>
        <div v-else class="anchor-poll">
          <div class="anchor-poll__q">{{ (item as Poll).question }}</div>
          <div
            v-for="opt in (item as Poll).options"
            :key="opt.id"
            :class="['anchor-poll__row', opt.votes === maxVotes ? 'is-winner' : '']"
          >
            <span class="anchor-poll__pct">{{ Math.round((opt.votes / (item as Poll).total) * 100) }}%</span>
            <div class="anchor-poll__bar"><span :style="{ width: `${Math.round((opt.votes / (item as Poll).total) * 100)}%` }" /></div>
            <span class="anchor-poll__lbl">{{ opt.label }}</span>
          </div>
          <div class="anchor-poll__total">{{ (item as Poll).total }} responses</div>
        </div>
      </div>
    </div>
  </article>
</template>
