<script setup lang="ts">
/**
 * SectionTeam — port of settings-pages.jsx::SectionTeam, fully wired to
 * /v1/settings/{people,groups} CRUD (Unit 1 of the MIC parity port).
 *
 * Two-pane: People list (rename + delete) + Groups list (rename, delete,
 * member-chip add/remove). Every action persists; toasts surface 409
 * duplicate-email / duplicate-name errors cleanly.
 */
import { computed, onMounted, ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import {
  settingsApi,
  type SettingsPerson,
  type SettingsGroup,
} from '@/services/api';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';
import { ApiError } from '@/services/http';

interface UiPerson { id: string; name: string; email: string }
interface UiGroup  { id: string; name: string; members: UiPerson[] }

const people     = ref<UiPerson[]>([]);
const groups     = ref<UiGroup[]>([]);
const newGroup   = ref('');
const loading    = ref(true);

// Track in-progress edits so the row swaps to an input inline (no modal).
const editingPersonId = ref<string | null>(null);
const editingPersonDraft = ref({ name: '', email: '' });
const editingGroupId = ref<string | null>(null);
const editingGroupDraft = ref('');

// ── Inline add-person form (replaces the legacy window.prompt() flow) ──
const newPersonName  = ref('');
const newPersonEmail = ref('');
const newPersonRole  = ref('');
const newPersonColor = ref<string>('#3b82f6');
const addingPerson   = ref(false);

const ADD_COLORS: readonly string[] = Object.freeze([
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#ec4899', '#14b8a6', '#64748b',
]);

function isEmailish(v: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim());
}

const canAddPerson = computed(() =>
  newPersonName.value.trim().length > 0 &&
  isEmailish(newPersonEmail.value),
);

const addPersonHint = computed(() => {
  const n = newPersonName.value.trim();
  const e = newPersonEmail.value.trim();
  if (!n && !e) return 'Enter a name and a valid email to enable Add person.';
  if (!n) return 'Name is required.';
  if (!e) return 'Email is required.';
  if (!isEmailish(e)) return `"${e}" doesn't look like a valid email.`;
  return 'Visible in stage-assignment chips. Role is free-form (e.g. "V@V", "Main Contact").';
});

async function hydrate(): Promise<void> {
  loading.value = true;
  try {
    const [pp, gg] = await Promise.all([
      settingsApi.people().catch(() => [] as SettingsPerson[]),
      settingsApi.groups().catch(() => [] as SettingsGroup[]),
    ]);
    people.value = pp.map((p) => ({ id: p.id, name: p.name, email: p.email }));

    // Fan-out per-group member fetches in parallel so each group's chips
    // come from the real /groups/{id}/members JOIN instead of the empty
    // placeholder array used before Unit 1.
    const memberLists = await Promise.all(
      gg.map((g) => settingsApi.groupMembers(g.id).catch(() => [] as SettingsPerson[])),
    );
    groups.value = gg.map((g, i) => ({
      id: g.id,
      name: g.name,
      members: memberLists[i]!.map((m) => ({ id: m.id, name: m.name, email: m.email })),
    }));
  } finally {
    loading.value = false;
  }
}

onMounted(hydrate);

function err(e: unknown): string {
  if (e instanceof ApiError) {
    // Backend's HTTPException detail is normalised by http.ts into `body`.
    // 409 duplicate/locked responses carry { code, message } — surface message
    // when present so the toast is human-readable.
    const body = e.body as { detail?: { message?: string; code?: string } | string } | undefined;
    const detail = body?.detail;
    if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
      return detail.message;
    }
    if (typeof detail === 'string') return detail;
    return e.message;
  }
  return e instanceof Error ? e.message : 'Request failed';
}

// ─── People ─────────────────────────────────────────────────────────────

async function addPerson(): Promise<void> {
  if (!canAddPerson.value || addingPerson.value) return;
  addingPerson.value = true;
  try {
    const created = await settingsApi.peopleAdd({
      name:         newPersonName.value.trim(),
      email:        newPersonEmail.value.trim().toLowerCase(),
      role:         newPersonRole.value.trim() || undefined,
      avatar_color: newPersonColor.value,
    });
    people.value = [...people.value, { id: created.id, name: created.name, email: created.email }];
    newPersonName.value  = '';
    newPersonEmail.value = '';
    newPersonRole.value  = '';
    newPersonColor.value = '#3b82f6';
    toast.push(`${created.name} added`, { tone: 'success' });
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  } finally {
    addingPerson.value = false;
  }
}

function startEditPerson(p: UiPerson): void {
  editingPersonId.value = p.id;
  editingPersonDraft.value = { name: p.name, email: p.email };
}

function cancelEditPerson(): void {
  editingPersonId.value = null;
}

async function saveEditPerson(p: UiPerson): Promise<void> {
  const draft = editingPersonDraft.value;
  const diff: Record<string, string> = {};
  if (draft.name.trim() && draft.name !== p.name)   diff.name  = draft.name.trim();
  if (draft.email.trim() && draft.email !== p.email) diff.email = draft.email.trim();
  if (Object.keys(diff).length === 0) {
    editingPersonId.value = null;
    return;
  }
  try {
    const updated = await settingsApi.peopleUpdate(p.id, diff);
    people.value = people.value.map((x) =>
      x.id === p.id ? { id: updated.id, name: updated.name, email: updated.email } : x,
    );
    // Member chips elsewhere reference these names — refresh the lookup.
    groups.value = groups.value.map((g) => ({
      ...g,
      members: g.members.map((m) =>
        m.id === p.id ? { ...m, name: updated.name, email: updated.email } : m,
      ),
    }));
    toast.push(`${updated.name} updated`, { tone: 'success' });
    editingPersonId.value = null;
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  }
}

async function delPerson(p: UiPerson): Promise<void> {
  const ok = await confirm.open({
    title: `Delete ${p.name}?`,
    danger: true,
    confirmLabel: 'Delete',
  });
  if (!ok) return;
  try {
    await settingsApi.peopleRemove(p.id);
    people.value = people.value.filter((x) => x.id !== p.id);
    // Drop them from any group's member list so the chips disappear too.
    groups.value = groups.value.map((g) => ({
      ...g,
      members: g.members.filter((m) => m.id !== p.id),
    }));
    toast.push(`${p.name} deleted`, { tone: 'success' });
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  }
}

// ─── Groups ─────────────────────────────────────────────────────────────

async function addGroup(): Promise<void> {
  const name = newGroup.value.trim();
  if (!name) return;
  try {
    const created = await settingsApi.groupsAdd({ name });
    groups.value = [...groups.value, { id: created.id, name: created.name, members: [] }];
    newGroup.value = '';
    toast.push(`${created.name} added`, { tone: 'success' });
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  }
}

function startEditGroup(g: UiGroup): void {
  editingGroupId.value = g.id;
  editingGroupDraft.value = g.name;
}

function cancelEditGroup(): void {
  editingGroupId.value = null;
}

async function saveEditGroup(g: UiGroup): Promise<void> {
  const next = editingGroupDraft.value.trim();
  if (!next || next === g.name) {
    editingGroupId.value = null;
    return;
  }
  try {
    const updated = await settingsApi.groupsUpdate(g.id, { name: next });
    groups.value = groups.value.map((x) =>
      x.id === g.id ? { ...x, name: updated.name } : x,
    );
    toast.push(`Group renamed to ${updated.name}`, { tone: 'success' });
    editingGroupId.value = null;
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  }
}

async function delGroup(g: UiGroup): Promise<void> {
  const ok = await confirm.open({
    title: `Delete group ${g.name}?`,
    danger: true,
    confirmLabel: 'Delete',
  });
  if (!ok) return;
  try {
    await settingsApi.groupsRemove(g.id);
    groups.value = groups.value.filter((x) => x.id !== g.id);
    toast.push(`Group ${g.name} deleted`, { tone: 'success' });
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  }
}

async function removeMember(g: UiGroup, m: UiPerson): Promise<void> {
  try {
    await settingsApi.groupMemberRemove(g.id, m.id);
    groups.value = groups.value.map((x) =>
      x.id === g.id ? { ...x, members: x.members.filter((mm) => mm.id !== m.id) } : x,
    );
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  }
}

async function addMember(g: UiGroup, e: Event): Promise<void> {
  const sel = e.target as HTMLSelectElement;
  const personId = sel.value;
  sel.value = '';
  if (!personId) return;
  const person = people.value.find((p) => p.id === personId);
  if (!person) return;
  if (g.members.some((m) => m.id === personId)) return;     // already a member
  try {
    await settingsApi.groupMemberAdd(g.id, personId);
    groups.value = groups.value.map((x) =>
      x.id === g.id ? { ...x, members: [...x.members, person] } : x,
    );
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  }
}

function availableForGroup(g: UiGroup): UiPerson[] {
  const memberIds = new Set(g.members.map((m) => m.id));
  return people.value.filter((p) => !memberIds.has(p.id));
}
</script>

<template>
  <SettingsHeader title="Team & roles" lead="People who can be assigned stages, and groups used for routing." />
  <div v-if="loading" :style="{ padding: '20px', color: 'var(--fg2)' }">Loading team…</div>
  <div v-else class="set-twocol">
    <div class="set-pane">
      <div class="set-pane__head">
        <span class="set-eyebrow">PEOPLE · {{ people.length }}</span>
      </div>

      <!-- Inline add-person form (replaces window.prompt). Always visible
           so there's no "where do I click" mystery. Button is disabled
           until name + valid email are present; helper text below explains
           the current state. -->
      <div
        class="set-row set-row--col"
        :style="{ background: 'var(--surface-muted, rgba(0,0,0,0.02))', borderRadius: '6px', padding: '10px', marginBottom: '10px' }"
      >
        <div :style="{ display: 'grid', gridTemplateColumns: '1.2fr 1.6fr 0.8fr auto auto', gap: '8px', alignItems: 'center' }">
          <input
            v-model="newPersonName"
            class="set-input set-input--sm"
            type="text"
            placeholder="Full name"
            data-test-id="add-person-name"
            @keyup.enter="addPerson"
          />
          <input
            v-model="newPersonEmail"
            class="set-input set-input--sm"
            type="email"
            placeholder="email@vin.com"
            autocomplete="off"
            data-test-id="add-person-email"
            @keyup.enter="addPerson"
          />
          <input
            v-model="newPersonRole"
            class="set-input set-input--sm"
            type="text"
            placeholder="Role (e.g. V@V)"
            data-test-id="add-person-role"
            @keyup.enter="addPerson"
          />
          <div
            :style="{ display: 'flex', gap: '4px', alignItems: 'center' }"
            data-test-id="add-person-color-picker"
          >
            <button
              v-for="c in ADD_COLORS"
              :key="c"
              type="button"
              :title="c"
              :style="{
                background: c,
                width: '18px', height: '18px', borderRadius: '50%',
                border: newPersonColor === c ? '2px solid var(--fg1)' : '1px solid var(--border)',
                padding: 0, cursor: 'pointer',
              }"
              @click="newPersonColor = c"
            />
          </div>
          <button
            class="btn btn--primary btn--sm"
            :disabled="!canAddPerson || addingPerson"
            data-test-id="add-person-submit"
            @click="addPerson"
          >{{ addingPerson ? 'Adding…' : 'Add person' }}</button>
        </div>
        <div
          :style="{
            fontSize: '11px',
            marginTop: '6px',
            color: canAddPerson ? 'var(--fg2)' : 'var(--color-warn, #b45309)',
          }"
        >{{ addPersonHint }}</div>
      </div>

      <div v-for="p in people" :key="p.id" class="set-row">
        <template v-if="editingPersonId === p.id">
          <div :style="{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }">
            <input v-model="editingPersonDraft.name" class="set-input set-input--sm" placeholder="Name" />
            <input v-model="editingPersonDraft.email" class="set-input set-input--sm" placeholder="Email" />
          </div>
          <div class="set-row__actions">
            <button class="set-link" @click="saveEditPerson(p)">Save</button>
            <button class="set-link" @click="cancelEditPerson">Cancel</button>
          </div>
        </template>
        <template v-else>
          <div>
            <div class="set-row__name">{{ p.name }}</div>
            <div class="set-row__sub">{{ p.email }}</div>
          </div>
          <div class="set-row__actions">
            <button class="set-link" @click="startEditPerson(p)">Edit</button>
            <button class="set-link set-link--danger" @click="delPerson(p)">Delete</button>
          </div>
        </template>
      </div>
    </div>
    <div class="set-pane">
      <div class="set-pane__head">
        <span class="set-eyebrow">GROUPS · {{ groups.length }}</span>
        <span :style="{ display: 'inline-flex', gap: '6px' }">
          <input v-model="newGroup" class="set-input set-input--sm" placeholder="New group name" @keyup.enter="addGroup" />
          <button class="btn btn--tertiary" @click="addGroup">+ Add</button>
        </span>
      </div>
      <div v-for="g in groups" :key="g.id" class="set-row set-row--col">
        <div class="set-row__top">
          <template v-if="editingGroupId === g.id">
            <input v-model="editingGroupDraft" class="set-input set-input--sm" @keyup.enter="saveEditGroup(g)" />
            <span :style="{ display: 'inline-flex', gap: '6px' }">
              <button class="set-link" @click="saveEditGroup(g)">Save</button>
              <button class="set-link" @click="cancelEditGroup">Cancel</button>
            </span>
          </template>
          <template v-else>
            <div class="set-row__name" :style="{ cursor: 'text' }" @click="startEditGroup(g)">{{ g.name }}</div>
            <span :style="{ display: 'inline-flex', gap: '6px' }">
              <button class="set-link" @click="startEditGroup(g)">Rename</button>
              <button class="set-link set-link--danger" @click="delGroup(g)">Delete</button>
            </span>
          </template>
        </div>
        <div class="set-chip-row">
          <span v-for="m in g.members" :key="m.id" class="chip chip--blue">
            {{ m.name }}
            <button class="set-chip-x" @click="removeMember(g, m)" title="Remove member">×</button>
          </span>
          <select
            v-if="availableForGroup(g).length > 0"
            class="set-input set-input--sm"
            :value="''"
            @change="(e) => addMember(g, e)"
          >
            <option value="">+ Add member</option>
            <option v-for="p in availableForGroup(g)" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
      </div>
    </div>
  </div>
</template>
