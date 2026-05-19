<script setup lang="ts">
/**
 * SpeakerEditPanel — right-rail editable speaker roster.
 *
 * Each speaker renders as a card (avatar circle + name + role pill).
 * Tap the name to rename inline; tap the role pill to toggle
 * Moderator ↔ Speaker. Tap × to remove. One Add Speaker button at
 * the bottom expands to a single-line entry, defaulting role to
 * "speaker" — change the role on the resulting card.
 *
 * Backed by /v1/sessions/{id}/speakers CRUD endpoints.
 */
import { ref, computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { speakers as speakersApi, type SessionSpeaker } from '@/services/api';
import { toast } from '@/composables/useToast';
import { ApiError } from '@/services/http';

const props = defineProps<{
  sessionId: string;
  liveSpeakers: readonly SessionSpeaker[];
}>();

const emit = defineEmits<{ (e: 'changed'): void }>();

const collapsed = ref(false);
const adding = ref(false);
const newName = ref('');
const savingId = ref<string | null>(null);

function initials(name: string | null | undefined): string {
  const n = (name || '').trim();
  if (!n) return '?';
  const parts = n.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return (parts[0]!.charAt(0) + parts[parts.length - 1]!.charAt(0)).toUpperCase();
}

function roleLabel(r: string | null | undefined): 'MODERATOR' | 'SPEAKER' {
  return (r || '').toLowerCase() === 'moderator' ? 'MODERATOR' : 'SPEAKER';
}

const cards = computed(() => props.liveSpeakers.map((s) => ({
  id: s.id,
  name: (s.name || '').trim() || '(unnamed)',
  role: roleLabel(s.role),
  avatar_color: s.avatar_color ?? null,
  initials: initials(s.name),
})));

async function renameSpeaker(id: string, name: string): Promise<void> {
  const trimmed = name.trim();
  if (!trimmed) { toast.push('Name cannot be empty', { tone: 'warn' }); emit('changed'); return; }
  savingId.value = id;
  try {
    await speakersApi.edit(props.sessionId, id, { name: trimmed });
    emit('changed');
  } catch (e) {
    toast.push(e instanceof ApiError ? `${e.status} — ${e.message}` : 'Save failed', { tone: 'error' });
  } finally {
    savingId.value = null;
  }
}

async function toggleRole(id: string, current: 'MODERATOR' | 'SPEAKER'): Promise<void> {
  const next = current === 'MODERATOR' ? 'speaker' : 'moderator';
  savingId.value = id;
  try {
    await speakersApi.edit(props.sessionId, id, { role: next });
    emit('changed');
  } catch (e) {
    toast.push(e instanceof ApiError ? `${e.status} — ${e.message}` : 'Save failed', { tone: 'error' });
  } finally {
    savingId.value = null;
  }
}

async function addSpeaker(): Promise<void> {
  const n = newName.value.trim();
  if (!n) { toast.push('Enter a speaker name', { tone: 'warn' }); return; }
  try {
    await speakersApi.add(props.sessionId, { name: n, role: 'speaker' });
    newName.value = '';
    adding.value = false;
    emit('changed');
  } catch (e) {
    toast.push(e instanceof ApiError ? `${e.status} — ${e.message}` : 'Add failed', { tone: 'error' });
  }
}

async function removeSpeaker(id: string, name: string): Promise<void> {
  if (!confirm(`Remove "${name}"?`)) return;
  try {
    await speakersApi.remove(props.sessionId, id);
    emit('changed');
  } catch (e) {
    toast.push(e instanceof ApiError ? `${e.status} — ${e.message}` : 'Remove failed', { tone: 'error' });
  }
}

function onNameBlur(card: { id: string; name: string }, ev: FocusEvent): void {
  const el = ev.target as HTMLInputElement;
  if (el.value.trim() === card.name) return;
  void renameSpeaker(card.id, el.value);
}
</script>

<template>
  <div class="speaker-panel" :class="{ 'is-collapsed': collapsed }">
    <div
      class="speaker-panel__head"
      role="button"
      :aria-expanded="!collapsed"
      @click="collapsed = !collapsed"
    >
      <h4>Speakers · {{ cards.length }}</h4>
      <Icon name="chevron-down" :size="14" :style="{ transform: collapsed ? 'rotate(-90deg)' : 'none', transition: 'transform 120ms' }" />
    </div>

    <div v-if="!collapsed" class="speaker-panel__body">
      <article
        v-for="c in cards"
        :key="c.id"
        class="speaker-card"
        :class="{ 'speaker-card--moderator': c.role === 'MODERATOR' }"
      >
        <div
          class="speaker-card__av"
          :style="c.avatar_color ? { background: c.avatar_color } : {}"
        >{{ c.initials }}</div>
        <div class="speaker-card__body">
          <input
            class="speaker-card__name"
            :value="c.name"
            :disabled="savingId === c.id"
            @blur="(e) => onNameBlur(c, e)"
            @keydown.enter="(e) => (e.target as HTMLInputElement).blur()"
          />
          <button
            class="speaker-card__role"
            :class="`speaker-card__role--${c.role.toLowerCase()}`"
            :title="`Toggle to ${c.role === 'MODERATOR' ? 'Speaker' : 'Moderator'}`"
            @click="toggleRole(c.id, c.role)"
          >{{ c.role }}</button>
        </div>
        <button
          class="speaker-card__remove"
          :data-test-id="`speaker-remove-${c.id}`"
          title="Remove"
          @click="removeSpeaker(c.id, c.name)"
        ><Icon name="x" :size="11" /></button>
      </article>

      <div v-if="!adding" class="speaker-panel__add-cta">
        <button class="btn btn--secondary btn--sm" data-test-id="speaker-add-open" @click="adding = true">
          <Icon name="plus" :size="12" /> Add speaker
        </button>
      </div>
      <div v-else class="speaker-card speaker-card--new">
        <div class="speaker-card__av speaker-card__av--ghost">+</div>
        <div class="speaker-card__body">
          <input
            v-model="newName"
            autofocus
            class="speaker-card__name"
            placeholder="Speaker name…"
            @keyup.enter="addSpeaker"
            @keyup.escape="() => { adding = false; newName = ''; }"
          />
          <button class="speaker-card__role speaker-card__role--speaker">SPEAKER (change after Add)</button>
        </div>
        <button
          class="speaker-card__remove"
          title="Cancel"
          @click="() => { adding = false; newName = ''; }"
        ><Icon name="x" :size="11" /></button>
        <button
          class="btn btn--primary btn--sm speaker-card__save"
          data-test-id="speaker-add-confirm"
          :disabled="!newName.trim()"
          @click="addSpeaker"
        >Add</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.speaker-panel {
  background: var(--surface-bg);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  margin-top: 12px;
  overflow: hidden;
}
.speaker-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
}
.speaker-panel__head h4 {
  margin: 0;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 700;
  color: var(--fg2);
}
.speaker-panel__body {
  padding: 4px 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.speaker-card {
  display: grid;
  grid-template-columns: 32px 1fr auto;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--surface-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  transition: border-color 120ms;
}
.speaker-card--moderator {
  border-left: 3px solid var(--color-amber);
  padding-left: 8px;
}
.speaker-card--new {
  grid-template-columns: 32px 1fr auto auto;
  border-style: dashed;
}
.speaker-card__av {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-steel);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.speaker-card__av--ghost {
  background: transparent;
  color: var(--fg2);
  border: 1px dashed var(--border-subtle);
}
.speaker-card__body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.speaker-card__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--fg1);
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 2px 4px;
  margin: -2px -4px;
  width: 100%;
}
.speaker-card__name:hover:not(:disabled),
.speaker-card__name:focus {
  background: var(--surface-bg);
  border-color: var(--border-subtle);
  outline: none;
}
.speaker-card__role {
  align-self: flex-start;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 999px;
  border: 1px solid currentColor;
  background: transparent;
  cursor: pointer;
}
.speaker-card__role--moderator { color: var(--color-amber); }
.speaker-card__role--speaker   { color: var(--color-steel); }
.speaker-card__role:hover { background: rgba(0, 0, 0, 0.04); }
.speaker-card__remove {
  background: transparent;
  border: none;
  color: var(--fg2);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  align-self: start;
}
.speaker-card__remove:hover { color: var(--color-red); background: rgba(217, 75, 75, 0.08); }
.speaker-card__save {
  align-self: stretch;
}
.speaker-panel__add-cta {
  display: flex;
  justify-content: center;
  margin-top: 2px;
}
</style>
