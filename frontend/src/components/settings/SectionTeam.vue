<script setup lang="ts">
/**
 * SectionTeam — verbatim port of settings-pages.jsx::SectionTeam (80-141).
 * Two-pane: People list + Groups list with chip member-add.
 *
 * Phase 2 (audit remediation): people add/delete + group add are wired
 * to real backend endpoints (/v1/settings/people POST/DELETE, /v1/settings/groups
 * POST — already exist in app/api/settings.py). People-edit, group-delete,
 * and group-member edit have no backend yet — those handlers now toast
 * honest warn-tone "not persisted" instead of fake success.
 */
import { onMounted, ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import { settingsApi, type SettingsPerson, type SettingsGroup } from '@/services/api';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';
import { ApiError } from '@/services/http';

interface UiPerson { id: string; name: string; email: string }
interface UiGroup { id: string; name: string; members: string[] }

const people = ref<UiPerson[]>([]);
const groups = ref<UiGroup[]>([]);
const newGroup = ref('');
const loading = ref(true);

async function hydrate(): Promise<void> {
  loading.value = true;
  try {
    const [pp, gg] = await Promise.all([
      settingsApi.people().catch(() => [] as SettingsPerson[]),
      settingsApi.groups().catch(() => [] as SettingsGroup[]),
    ]);
    people.value = pp.map((p) => ({ id: p.id, name: p.name, email: p.email }));
    // Backend has no group_members table yet → members stay empty UI-side until Phase 6 wiring.
    groups.value = gg.map((g) => ({ id: g.id, name: g.name, members: [] }));
  } finally {
    loading.value = false;
  }
}

onMounted(hydrate);

function err(e: unknown): string {
  if (e instanceof ApiError) return `${e.status} — ${e.message}`;
  return e instanceof Error ? e.message : 'Request failed';
}

async function addPerson(): Promise<void> {
  const name = window.prompt('Name?');
  if (!name) return;
  const email = window.prompt('Email?') || '';
  if (!email) {
    toast.push('Email required to add a person', { tone: 'warn' });
    return;
  }
  try {
    const created = await settingsApi.peopleAdd({ name, email });
    people.value = [...people.value, { id: created.id, name: created.name, email: created.email }];
    toast.push(`${created.name} added`, { tone: 'success' });
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  }
}

function editPerson(i: number): void {
  // Backend has no PATCH /v1/settings/people/{id}. Honest warn-toast.
  toast.push('Person edit not persisted — name/email edit ships with Phase 9 team CRUD.', { tone: 'warn' });
  void i;
}

async function delPerson(i: number): Promise<void> {
  const person = people.value[i];
  if (!person) return;
  const ok = await confirm.open({
    title: `Delete ${person.name}?`,
    danger: true,
    confirmLabel: 'Delete',
  });
  if (!ok) return;
  try {
    await settingsApi.peopleRemove(person.id);
    people.value = people.value.filter((_, j) => j !== i);
    toast.push(`${person.name} deleted`, { tone: 'success' });
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  }
}

async function addGroup(): Promise<void> {
  if (!newGroup.value) return;
  const name = newGroup.value;
  try {
    const created = await settingsApi.groupsAdd({ name });
    groups.value = [...groups.value, { id: created.id, name: created.name, members: [] }];
    toast.push(`${created.name} added`, { tone: 'success' });
    newGroup.value = '';
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  }
}

async function delGroup(gi: number): Promise<void> {
  const group = groups.value[gi];
  if (!group) return;
  const ok = await confirm.open({
    title: `Delete group ${group.name}?`,
    danger: true,
    confirmLabel: 'Delete',
  });
  if (!ok) return;
  // Backend has no DELETE /v1/settings/groups/{id}. Honest warn.
  toast.push('Group delete not persisted — group removal ships with Phase 6 SOP plane.', { tone: 'warn' });
}

function removeMember(_gi: number, _mi: number): void {
  toast.push('Group member edits ship with Phase 6 SOP plane — change not persisted.', { tone: 'warn' });
}
function addMember(_gi: number, e: Event): void {
  const sel = e.target as HTMLSelectElement;
  sel.value = '';
  toast.push('Group member edits ship with Phase 6 SOP plane — change not persisted.', { tone: 'warn' });
}
</script>

<template>
  <SettingsHeader title="Team & roles" lead="People who can be assigned stages, and groups used for routing." />
  <div v-if="loading" :style="{ padding: '20px', color: 'var(--fg2)' }">Loading team…</div>
  <div v-else class="set-twocol">
    <div class="set-pane">
      <div class="set-pane__head">
        <span class="set-eyebrow">PEOPLE · {{ people.length }}</span>
        <button class="btn btn--tertiary" @click="addPerson">+ Add person</button>
      </div>
      <div v-for="(p, i) in people" :key="p.id" class="set-row">
        <div>
          <div class="set-row__name">{{ p.name }}</div>
          <div class="set-row__sub">{{ p.email }}</div>
        </div>
        <div class="set-row__actions">
          <button class="set-link" @click="editPerson(i)">Edit</button>
          <button class="set-link set-link--danger" @click="delPerson(i)">Delete</button>
        </div>
      </div>
    </div>
    <div class="set-pane">
      <div class="set-pane__head">
        <span class="set-eyebrow">GROUPS · {{ groups.length }}</span>
        <span :style="{ display: 'inline-flex', gap: '6px' }">
          <input v-model="newGroup" class="set-input set-input--sm" placeholder="New group name" />
          <button class="btn btn--tertiary" @click="addGroup">+ Add</button>
        </span>
      </div>
      <div v-for="(g, gi) in groups" :key="g.id" class="set-row set-row--col">
        <div class="set-row__top">
          <div class="set-row__name">{{ g.name }}</div>
          <button class="set-link set-link--danger" @click="delGroup(gi)">Delete</button>
        </div>
        <div class="set-chip-row">
          <span v-for="(m, mi) in g.members" :key="mi" class="chip chip--blue">
            {{ m }}
            <button class="set-chip-x" @click="removeMember(gi, mi)">×</button>
          </span>
          <select class="set-input set-input--sm" :value="''" @change="(e) => addMember(gi, e)">
            <option value="">+ Add member</option>
            <option v-for="p in people.filter((p) => !g.members.includes(p.name))" :key="p.email" :value="p.name">{{ p.name }}</option>
          </select>
        </div>
      </div>
    </div>
  </div>
</template>
