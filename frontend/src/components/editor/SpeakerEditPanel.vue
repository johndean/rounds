<script setup lang="ts">
/**
 * SpeakerEditPanel — right-rail editable speaker roster. CRUD on
 * session_speakers via the existing /v1/sessions/{id}/speakers endpoints.
 *
 * Renders an Add Speaker affordance plus one editable row per existing
 * speaker (name + role). Saves are debounced; a stale-write check is not
 * implemented because the endpoint is last-writer-wins by design.
 *
 * Risk-bounded surface:
 * - Edits are session-scoped (don't mutate the global speakers table).
 * - Soft semantics: delete sends DELETE which the backend handles; we do
 *   NOT cascade-clear segment.speaker_id from the frontend. If the backend
 *   returns 409 (segments still reference the speaker), we surface a toast.
 */
import { ref } from 'vue';
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
const saving = ref<Record<string, boolean>>({});
const newName = ref('');
const newRole = ref<'moderator' | 'speaker'>('speaker');

async function patchSpeaker(id: string, patch: { name?: string; role?: string }): Promise<void> {
  saving.value = { ...saving.value, [id]: true };
  try {
    await speakersApi.edit(props.sessionId, id, patch);
    emit('changed');
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Save failed';
    toast.push(msg, { tone: 'error' });
  } finally {
    saving.value = { ...saving.value, [id]: false };
  }
}

async function addSpeaker(): Promise<void> {
  const n = newName.value.trim();
  if (!n) { toast.push('Speaker name required', { tone: 'warn' }); return; }
  try {
    await speakersApi.add(props.sessionId, { name: n, role: newRole.value });
    newName.value = '';
    newRole.value = 'speaker';
    emit('changed');
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Add failed';
    toast.push(msg, { tone: 'error' });
  }
}

async function removeSpeaker(id: string, name: string | null): Promise<void> {
  if (!confirm(`Remove speaker "${name || id}"?`)) return;
  try {
    await speakersApi.remove(props.sessionId, id);
    emit('changed');
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Remove failed';
    toast.push(msg, { tone: 'error' });
  }
}

function roleLabel(r: string | null): string {
  if (!r) return 'SPEAKER';
  return r.toUpperCase();
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
      <h4>Speakers · {{ liveSpeakers.length }}</h4>
      <Icon name="chevron-down" :size="14" :style="{ transform: collapsed ? 'rotate(-90deg)' : 'none', transition: 'transform 120ms' }" />
    </div>

    <div v-if="!collapsed" class="speaker-panel__body">
      <div v-for="sp in liveSpeakers" :key="sp.id" class="speaker-row">
        <div class="speaker-row__role">{{ roleLabel(sp.role) }}</div>
        <input
          class="speaker-row__name"
          :value="sp.name ?? ''"
          placeholder="Name"
          :disabled="saving[sp.id] === true"
          @change="(e) => patchSpeaker(sp.id, { name: (e.target as HTMLInputElement).value })"
        />
        <select
          class="speaker-row__role-select"
          :value="(sp.role || 'speaker').toLowerCase()"
          :disabled="saving[sp.id] === true"
          @change="(e) => patchSpeaker(sp.id, { role: (e.target as HTMLSelectElement).value })"
        >
          <option value="speaker">Speaker</option>
          <option value="moderator">Moderator</option>
        </select>
        <button
          class="speaker-row__remove"
          :data-test-id="`speaker-remove-${sp.id}`"
          title="Remove"
          @click="removeSpeaker(sp.id, sp.name)"
        ><Icon name="x" :size="11" /></button>
      </div>

      <div class="speaker-row speaker-row--new">
        <select v-model="newRole" class="speaker-row__role-select">
          <option value="speaker">Speaker</option>
          <option value="moderator">Moderator</option>
        </select>
        <input
          v-model="newName"
          class="speaker-row__name"
          placeholder="Add speaker name…"
          @keyup.enter="addSpeaker"
        />
        <button
          class="btn btn--secondary btn--sm"
          data-test-id="speaker-add"
          :disabled="!newName.trim()"
          @click="addSpeaker"
        ><Icon name="plus" :size="11" /> Add</button>
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
.speaker-row {
  display: grid;
  grid-template-columns: 76px 1fr 92px 22px;
  gap: 6px;
  align-items: center;
}
.speaker-row--new {
  grid-template-columns: 92px 1fr 70px;
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px dashed var(--border-subtle);
}
.speaker-row__role {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--fg2);
}
.speaker-row__name,
.speaker-row__role-select {
  font-size: 12px;
  padding: 4px 6px;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  background: var(--surface-card);
}
.speaker-row__remove {
  background: transparent;
  border: none;
  color: var(--fg2);
  cursor: pointer;
  padding: 2px;
  border-radius: 3px;
}
.speaker-row__remove:hover { color: var(--color-red); background: rgba(217, 75, 75, 0.08); }
</style>
