<script setup lang="ts">
/**
 * Improvements — /improvements
 * Faithful 1:1 port of docs/port-source/improvements.jsx::ImprovementsRoute (5-129).
 */
import { computed, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import ImprovDetail from '@/components/improvements/ImprovDetail.vue';
import { IMPROVEMENTS, type ImprovementFixture } from '@/fixtures/improvements';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';

const extraItems = ref<ImprovementFixture[]>([]);
const items = computed<ImprovementFixture[]>(() => [...extraItems.value, ...IMPROVEMENTS]);

const statusTab = ref<string>('all');
const selectedId = ref<string | null>(items.value[1]?.id ?? items.value[0]?.id ?? null);
const searchQ = ref('');

const filters = computed(() => [
  { id: 'all',          label: 'All',          count: items.value.length },
  { id: 'pending',      label: 'Pending',      count: items.value.filter(i => i.status === 'pending').length },
  { id: 'under-review', label: 'Under Review', count: 0 },
  { id: 'approved',     label: 'Approved',     count: 0 },
  { id: 'in-progress',  label: 'In Progress',  count: 0 },
  { id: 'rolled-out',   label: 'Rolled Out',   count: items.value.filter(i => i.status === 'rolled-out').length },
  { id: 'declined',     label: 'Declined',     count: 0 },
  { id: 'archived',     label: 'Archived',     count: 0 },
]);

const visibleItems = computed(() => {
  const pool = statusTab.value === 'all' ? items.value : items.value.filter(i => i.status === statusTab.value);
  if (!searchQ.value) return pool;
  const q = searchQ.value.toLowerCase();
  return pool.filter(i => (i.title || '').toLowerCase().includes(q));
});

const selected = computed(() => items.value.find(i => i.id === selectedId.value) ?? items.value[0] ?? null);

function priorityLabel(p: string): string {
  return p === 'crit' ? 'Critical' : p === 'high' ? 'High' : p === 'med' ? 'Medium' : 'Low';
}
function fmtCreated(iso: string): string {
  const d = new Date(iso);
  return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })}`;
}

function suggest(): void {
  toast.push('Suggest Improvement modal (mock)', { tone: 'info' });
  // In the React app this opens wired.openSuggestImprovement modal.
  // Inline-modal port lands when wiring.jsx → composables port is complete.
}

async function delRow(it: ImprovementFixture, e: Event): Promise<void> {
  e.stopPropagation();
  const ok = await confirm.open({
    title: 'Delete improvement?',
    body: `"${it.title}"`,
    danger: true,
    confirmLabel: 'Delete',
  });
  if (ok) {
    extraItems.value = extraItems.value.filter(x => x.id !== it.id);
    toast.push('Improvement deleted', { tone: 'success' });
  }
}
</script>

<template>
  <main class="page" data-screen-label="Improvements">
    <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }">
      <div>
        <h1 class="page-title">Improvements</h1>
        <p class="page-desc">
          {{ items.length }} of {{ items.length }} · roadmap for product enhancements, bug fixes, and operator requests.
        </p>
      </div>
      <div class="page-actions">
        <div class="search" :style="{ flex: '0 0 240px' }">
          <Icon name="search" />
          <input v-model="searchQ" placeholder="Search…" data-test-id="improv-search" />
        </div>
        <button class="btn btn--primary" data-test-id="improv-suggest" @click="suggest">
          <Icon name="circle-dot" /> Suggest Improvement
        </button>
      </div>
    </div>

    <!-- Status tabs -->
    <div class="improv-tabs">
      <button
        v-for="f in filters"
        :key="f.id"
        :class="['improv-tab', { 'is-active': statusTab === f.id }]"
        @click="statusTab = f.id"
      >
        {{ f.label }} <span class="count">{{ f.count }}</span>
      </button>
    </div>

    <!-- Master/detail -->
    <div class="improv-master-detail">
      <div class="improv-master">
        <div class="improv-master__head">
          <input type="checkbox" />
          <span>TITLE</span>
          <span>STATUS</span>
          <span>RISK</span>
          <span>PRIORITY</span>
          <span>SUBMITTED</span>
        </div>
        <div class="improv-master__list">
          <div
            v-for="it in visibleItems"
            :key="it.id"
            :class="['improv-row2', { 'is-selected': it.id === selectedId }]"
            @click="selectedId = it.id"
          >
            <input type="checkbox" @click.stop />
            <div>
              <div class="improv-row2__title">{{ it.title }}</div>
              <div class="improv-row2__url">{{ it.url }}</div>
            </div>
            <div>
              <span v-if="it.status === 'pending'" class="status-pill status-pill--pending">PENDING</span>
              <span v-if="it.status === 'rolled-out'" class="status-pill status-pill--rolled">ROLLED OUT</span>
            </div>
            <div>
              <span v-if="it.risk === 'critical'" class="risk-pill risk-pill--critical">CRITICAL</span>
              <span v-if="it.risk === 'high'" class="risk-pill risk-pill--high">HIGH</span>
              <span v-if="it.risk === 'medium'" class="risk-pill risk-pill--medium">MEDIUM</span>
              <span v-if="it.risk === 'low'" class="risk-pill risk-pill--low">LOW</span>
            </div>
            <div class="improv-row2__priority">{{ priorityLabel(it.priority) }}</div>
            <div class="improv-row2__date">{{ fmtCreated(it.created) }}</div>
            <span
              class="improv-row2__del"
              :data-test-id="`improv-del-${it.id}`"
              @click="(e) => delRow(it, e)"
            >Del</span>
          </div>
        </div>
      </div>

      <!-- Detail pane -->
      <div class="improv-detail">
        <ImprovDetail v-if="selected" :item="selected" @close="selectedId = null" />
      </div>
    </div>
  </main>
</template>
