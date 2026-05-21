<script setup lang="ts">
/**
 * SectionTypes — verbatim port of settings-pages.jsx::SectionTypes (143-190).
 * Two-pane: Type list + 8-stage assignee matrix with email-on-entry checkbox.
 *
 * Phase C wiring:
 *   - On mount: GET /v1/settings/types → real DB rows (seeded by migration 031).
 *   - On active-Type click: GET /v1/settings/types/{id}/assignees → rebuild
 *     `matrix` + `emails` from real rows so each Type shows its own assignees.
 *   - Save matrix → PUT /v1/settings/types/{id}/assignees with all 8 stages.
 *   - Add/Remove type → POST/DELETE /v1/settings/types (admin-gated server-side).
 */
import { onMounted, ref, watch } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import { TEAM_PEOPLE, SESSION_TYPES, SOP_STAGE_KEYS } from '@/fixtures/settings';
import { settingsApi, type StageAssigneeRow } from '@/services/api';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';
import { ApiError } from '@/services/http';

interface TypeRow {
  id: string | null;        // null until persisted
  code: string;
  label: string;
  is_default?: boolean;
}

const types = ref<TypeRow[]>(SESSION_TYPES.map((c) => ({ id: null, code: c, label: c })));
const active = ref<TypeRow>(types.value[0]!);
const newType = ref('');
const saving = ref(false);
const loadingMatrix = ref(false);

const allAssignees: string[] = [
  '(unassigned)',
  ...TEAM_PEOPLE.map((p) => p.name),
  'Group: Content Team', 'Group: External', 'Group: V@V', 'Group: Main Contact',
];

// Per-stage assignee email + notify flag for the CURRENT active Type.
const matrix = ref<Record<string, string>>({});      // stage_id → display name
const emails = ref<Record<string, boolean>>({});

// Reverse lookup: display name → email (for serializing back to server).
function _emailForName(name: string): string {
  if (!name || name === '(unassigned)') return '';
  if (name.startsWith('Group: ')) return name;        // groups stored as "Group: X"
  const person = TEAM_PEOPLE.find((p) => p.name === name);
  return person ? person.email : name;
}
function _nameForEmail(email: string): string {
  if (!email) return '(unassigned)';
  if (email.startsWith('Group: ')) return email;
  const person = TEAM_PEOPLE.find((p) => p.email === email);
  return person ? person.name : email;
}

function _resetMatrix(): void {
  matrix.value = Object.fromEntries(SOP_STAGE_KEYS.map((s) => [s.id, '(unassigned)']));
  emails.value = Object.fromEntries(SOP_STAGE_KEYS.map((s) => [s.id, false]));
}

async function _loadMatrixFor(typeRow: TypeRow): Promise<void> {
  _resetMatrix();
  if (!typeRow.id) return;     // fixture-only row (not persisted yet)
  loadingMatrix.value = true;
  try {
    const rows = await settingsApi.typeAssignees(typeRow.id);
    for (const r of rows) {
      matrix.value[r.stage] = _nameForEmail(r.assignee_email);
      emails.value[r.stage] = r.notify_email;
    }
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Load matrix failed';
    toast.push(msg, { tone: 'error' });
  } finally {
    loadingMatrix.value = false;
  }
}

onMounted(async () => {
  try {
    const rows = await settingsApi.types();
    if (rows && rows.length) {
      types.value = rows.map((r) => ({ id: r.id, code: r.code, label: r.label, is_default: r.is_default }));
      // Preserve current active selection by code if possible; default to first.
      const found = types.value.find((t) => t.code === active.value.code) ?? types.value[0]!;
      active.value = found;
      await _loadMatrixFor(active.value);
    } else {
      _resetMatrix();
    }
  } catch {
    _resetMatrix();
  }
});

watch(active, (t) => { void _loadMatrixFor(t); });

async function addType(): Promise<void> {
  const code = newType.value.trim();
  if (!code) return;
  try {
    const row = await settingsApi.typesAdd({ code, label: code });
    types.value = [...types.value.filter((t) => t.code !== code), { id: row.id, code: row.code, label: row.label }];
    newType.value = '';
    active.value = types.value.find((t) => t.code === code)!;
    toast.push(`Added type ${code}`, { tone: 'success' });
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Add type failed';
    toast.push(msg, { tone: 'error' });
  }
}

async function removeType(t: TypeRow): Promise<void> {
  if (t.is_default || t.code === 'default') return;
  const ok = await confirm.open({ title: `Remove ${t.code}?`, danger: true, confirmLabel: 'Remove' });
  if (!ok) return;
  if (!t.id) {
    // Fixture-only row; just drop locally.
    types.value = types.value.filter((x) => x.code !== t.code);
    return;
  }
  try {
    await settingsApi.typesRemove(t.id);
    types.value = types.value.filter((x) => x.id !== t.id);
    if (active.value.id === t.id) active.value = types.value[0]!;
    toast.push(`Removed type ${t.code}`, { tone: 'success' });
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Remove failed';
    toast.push(msg, { tone: 'error' });
  }
}

async function saveMatrix(): Promise<void> {
  if (saving.value) return;
  if (!active.value.id) {
    toast.push('Type not yet persisted — Add it first.', { tone: 'warn' });
    return;
  }
  saving.value = true;
  try {
    const rows: StageAssigneeRow[] = SOP_STAGE_KEYS.map((s) => ({
      stage:          s.id,
      assignee_email: _emailForName(matrix.value[s.id] || '(unassigned)'),
      notify_email:   !!emails.value[s.id],
    })).filter((r) => r.assignee_email);
    await settingsApi.setTypeAssignees(active.value.id, rows);
    toast.push(`Matrix saved for ${active.value.code}`, { tone: 'success' });
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Save failed';
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
        :key="t.code"
        :class="['set-row', 'set-row--clickable', active.code === t.code ? 'is-active' : '']"
        @click="active = t"
      >
        <span>
          {{ t.code }}
          <span v-if="t.is_default || t.code === 'default'" class="set-default-pill">DEFAULT</span>
        </span>
        <button
          v-if="!(t.is_default || t.code === 'default')"
          class="set-link set-link--danger"
          @click.stop="removeType(t)"
        >Remove</button>
      </div>
    </div>
    <div class="set-pane">
      <div class="set-pane__head">
        <span class="set-eyebrow">
          STAGE ASSIGNEES FOR <strong :style="{ color: 'var(--fg1)' }">{{ active.code }}</strong>
          <em v-if="loadingMatrix" :style="{ marginLeft: '8px', color: 'var(--fg2)' }">loading…</em>
        </span>
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
        <button class="btn btn--tertiary" :disabled="saving || !active.id" @click="saveMatrix">
          {{ saving ? 'Saving…' : 'Save matrix' }}
        </button>
      </div>
    </div>
  </div>
</template>
