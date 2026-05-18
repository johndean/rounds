<script setup lang="ts">
/**
 * SectionTeam — verbatim port of settings-pages.jsx::SectionTeam (80-141).
 * Two-pane: People list + Groups list with chip member-add.
 */
import { ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import { TEAM_PEOPLE, TEAM_GROUPS, type TeamPerson, type TeamGroup } from '@/fixtures/settings';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';

const people = ref<TeamPerson[]>([...TEAM_PEOPLE]);
const groups = ref<TeamGroup[]>(TEAM_GROUPS.map((g) => ({ ...g, members: [...g.members] })));
const newGroup = ref('');

function addPerson(): void {
  const n = window.prompt('Name?');
  if (!n) return;
  const e = window.prompt('Email?') || '';
  people.value = [...people.value, { name: n, email: e }];
  toast.push(`${n} added`, { tone: 'success' });
}
function editPerson(i: number): void {
  const n = window.prompt('Name?', people.value[i]!.name);
  if (!n) return;
  people.value = people.value.map((x, j) => (j === i ? { ...x, name: n } : x));
  toast.push('Updated', { tone: 'success' });
}
async function delPerson(i: number): Promise<void> {
  const ok = await confirm.open({
    title: `Delete ${people.value[i]!.name}?`,
    danger: true,
    confirmLabel: 'Delete',
  });
  if (!ok) return;
  const nm = people.value[i]!.name;
  people.value = people.value.filter((_, j) => j !== i);
  toast.push(`${nm} deleted`, { tone: 'success' });
}

function addGroup(): void {
  if (!newGroup.value) return;
  groups.value = [...groups.value, { name: newGroup.value, members: [] }];
  toast.push(`${newGroup.value} added`, { tone: 'success' });
  newGroup.value = '';
}
async function delGroup(gi: number): Promise<void> {
  const ok = await confirm.open({
    title: `Delete group ${groups.value[gi]!.name}?`,
    danger: true,
    confirmLabel: 'Delete',
  });
  if (!ok) return;
  groups.value = groups.value.filter((_, i) => i !== gi);
  toast.push('Group deleted', { tone: 'success' });
}
function removeMember(gi: number, mi: number): void {
  groups.value = groups.value.map((x, i) =>
    i === gi ? { ...x, members: x.members.filter((_, j) => j !== mi) } : x
  );
}
function addMember(gi: number, e: Event): void {
  const sel = e.target as HTMLSelectElement;
  const v = sel.value;
  if (!v) return;
  if (groups.value[gi]!.members.includes(v)) return;
  groups.value = groups.value.map((x, i) => (i === gi ? { ...x, members: [...x.members, v] } : x));
  sel.value = '';
}
</script>

<template>
  <SettingsHeader title="Team & roles" lead="People who can be assigned stages, and groups used for routing." />
  <div class="set-twocol">
    <div class="set-pane">
      <div class="set-pane__head">
        <span class="set-eyebrow">PEOPLE · {{ people.length }}</span>
        <button class="btn btn--tertiary" @click="addPerson">+ Add person</button>
      </div>
      <div v-for="(p, i) in people" :key="i" class="set-row">
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
      <div v-for="(g, gi) in groups" :key="gi" class="set-row set-row--col">
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
