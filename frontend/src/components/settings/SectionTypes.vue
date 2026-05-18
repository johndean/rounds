<script setup lang="ts">
/**
 * SectionTypes — verbatim port of settings-pages.jsx::SectionTypes (143-190).
 * Two-pane: Type list + 8-stage assignee matrix with email-on-entry checkbox.
 *
 * Phase 2 (audit remediation): types hydrate from /v1/settings/types (real
 * DB rows). saveMatrix persists to /v1/settings/{stage_matrix.<active>}
 * via settingsApi.set. Add/remove type require POST/DELETE /v1/settings/types
 * which Phase 2.2 / Phase 6 will add — those handlers now warn-toast.
 */
import { onMounted, ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import { TEAM_PEOPLE, SESSION_TYPES, SOP_STAGE_KEYS } from '@/fixtures/settings';
import { settingsApi } from '@/services/api';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';
import { ApiError } from '@/services/http';

const types = ref<string[]>([...SESSION_TYPES]);
const active = ref<string>('default');
const newType = ref('');
const saving = ref(false);

const allAssignees: string[] = [
  '(unassigned)',
  ...TEAM_PEOPLE.map((p) => p.name),
  'Group: Content Team', 'Group: External', 'Group: V@V', 'Group: Main Contact',
];

const matrix = ref<Record<string, string>>({
  prep: 'Tina Payton',
  copy_draft: 'Tina Payton',
  medical: 'Group: External',
  copy_final: 'Tina Payton',
  cms: 'Tina Payton',
  captions: 'Erica Hulse',
  qa: 'Lacy Sanders',
  complete: 'Carla Burris',
});
const emails = ref<Record<string, boolean>>({ complete: true });

onMounted(async () => {
  try {
    const rows = await settingsApi.types();
    if (rows && rows.length) {
      // Replace fixture list with real type codes; preserve 'default' if not in DB.
      const codes = rows.map((r) => r.code);
      types.value = codes.includes('default') ? codes : ['default', ...codes];
    }
  } catch { /* fall back to fixture list */ }
});

function addType(): void {
  if (!newType.value) return;
  // Backend has no POST /v1/settings/types yet (Phase 2.2 / Phase 6).
  toast.push('Add Type not persisted — type management ships with Phase 6 SOP plane.', { tone: 'warn' });
}
async function removeType(t: string): Promise<void> {
  const ok = await confirm.open({ title: `Remove ${t}?`, danger: true, confirmLabel: 'Remove' });
  if (!ok) return;
  toast.push('Remove Type not persisted — type management ships with Phase 6 SOP plane.', { tone: 'warn' });
}
async function saveMatrix(): Promise<void> {
  if (saving.value) return;
  saving.value = true;
  try {
    // Persist as a single jsonb blob under stage_matrix.<active>.
    await settingsApi.set(`stage_matrix.${active.value}`, {
      assignees: matrix.value,
      emails:    emails.value,
    });
    toast.push(`Matrix saved for ${active.value}`, { tone: 'success' });
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : (e instanceof Error ? e.message : 'Save failed');
    toast.push(msg, { tone: 'error' });
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <SettingsHeader
    title="Types & stage defaults"
    lead="Each Type defines a default assignee and notify-on-entry flag per stage. New sessions auto-populate from the selected Type's matrix row."
  />
  <div class="set-twocol set-twocol--340">
    <div class="set-pane">
      <div class="set-pane__head">
        <input v-model="newType" class="set-input set-input--sm" placeholder="New Type name" />
        <button class="btn btn--tertiary" @click="addType">+ Add type</button>
      </div>
      <div
        v-for="t in types"
        :key="t"
        :class="['set-row', 'set-row--clickable', active === t ? 'is-active' : '']"
        @click="active = t"
      >
        <span>
          {{ t }}
          <span v-if="t === 'default'" class="set-default-pill">DEFAULT</span>
        </span>
        <button
          v-if="t !== 'default'"
          class="set-link set-link--danger"
          @click.stop="removeType(t)"
        >Remove</button>
      </div>
    </div>
    <div class="set-pane">
      <div class="set-pane__head">
        <span class="set-eyebrow">STAGE ASSIGNEES FOR <strong :style="{ color: 'var(--fg1)' }">{{ active }}</strong></span>
      </div>
      <div v-for="s in SOP_STAGE_KEYS" :key="s.id" class="set-matrix-row">
        <label>{{ s.label }}</label>
        <select
          class="set-input"
          :value="matrix[s.id] || '(unassigned)'"
          @change="(e) => (matrix[s.id] = (e.target as HTMLSelectElement).value)"
        >
          <option v-for="a in allAssignees" :key="a" :value="a">{{ a }}</option>
        </select>
        <label class="set-matrix-row__email">
          <input
            type="checkbox"
            :checked="!!emails[s.id]"
            @change="(e) => (emails[s.id] = (e.target as HTMLInputElement).checked)"
          />
          Email
        </label>
      </div>
      <div :style="{ textAlign: 'right', marginTop: '14px' }">
        <button class="btn btn--tertiary" :disabled="saving" @click="saveMatrix">
          {{ saving ? 'Saving…' : 'Save matrix' }}
        </button>
      </div>
    </div>
  </div>
</template>
