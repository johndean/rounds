<script setup lang="ts">
/**
 * Improvements — /improvements
 *
 * Same DOM as React improvements.jsx::ImprovementsRoute. Wired:
 *   GET  /v1/improvements              — list
 *   POST /v1/improvements              — Suggest modal submit
 *   DELETE /v1/improvements/{id}       — row delete
 *
 * Empty state when the table is empty; row schema adapted to the
 * backend ImprovementSummary shape (no `created`/`url` columns yet).
 */
import { computed, onMounted, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import ImprovDetail from '@/components/improvements/ImprovDetail.vue';
import { improvements as improvApi, type ImprovementSummary } from '@/services/api';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';
import { modal } from '@/composables/useModal';
import SuggestImprovementModal from '@/components/overlays/SuggestImprovementModal.vue';

const items = ref<ImprovementSummary[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const statusTab = ref<string>('all');
const selectedId = ref<string | null>(null);
const searchQ = ref('');

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    items.value = await improvApi.list();
    if (!selectedId.value && items.value.length > 0) {
      selectedId.value = items.value[0]!.id;
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load';
  } finally {
    loading.value = false;
  }
}
onMounted(load);

const filters = computed(() => [
  { id: 'all',          label: 'All',          count: items.value.length },
  { id: 'pending',      label: 'Pending',      count: items.value.filter(i => i.status === 'pending').length },
  { id: 'under-review', label: 'Under Review', count: items.value.filter(i => i.status === 'under-review').length },
  { id: 'approved',     label: 'Approved',     count: items.value.filter(i => i.status === 'approved').length },
  { id: 'in-progress',  label: 'In Progress',  count: items.value.filter(i => i.status === 'in-progress').length },
  { id: 'rolled-out',   label: 'Rolled Out',   count: items.value.filter(i => i.status === 'rolled-out').length },
  { id: 'declined',     label: 'Declined',     count: items.value.filter(i => i.status === 'declined').length },
  { id: 'archived',     label: 'Archived',     count: items.value.filter(i => i.status === 'archived').length },
]);

const visibleItems = computed(() => {
  const pool = statusTab.value === 'all' ? items.value : items.value.filter(i => i.status === statusTab.value);
  if (!searchQ.value) return pool;
  const q = searchQ.value.toLowerCase();
  return pool.filter(i => (i.title || '').toLowerCase().includes(q));
});

const selected = computed(() => items.value.find(i => i.id === selectedId.value) ?? items.value[0] ?? null);

// Adapt the lighter API shape to the legacy ImprovDetail prop shape.
const selectedForDetail = computed(() => {
  const s = selected.value;
  if (!s) return null;
  return {
    id: s.id,
    surface: '—',
    title: s.title,
    author: s.submitted_by || '',
    priority: (s.priority as 'crit' | 'high' | 'med' | 'low'),
    risk: (s.risk as 'low' | 'medium' | 'high' | 'critical'),
    status: (s.status as 'pending' | 'under-review' | 'approved' | 'in-progress' | 'rolled-out' | 'declined' | 'archived'),
    created: s.submitted_at,
    url: '',
    area: '—',
    description: '(detail body loads from /v1/improvements/{id} once wired)',
  };
});

function priorityLabel(p: string): string {
  return p === 'crit' || p === 'critical' ? 'Critical' : p === 'high' ? 'High' : p === 'med' || p === 'medium' ? 'Medium' : 'Low';
}
function fmtCreated(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })}`;
}

function suggest(): void {
  void modal.open(SuggestImprovementModal, {
    onSubmit: async (s: { title: string; surface: string; priority: string; description: string }) => {
      try {
        const created = await improvApi.suggest({
          title: s.title,
          description: s.description,
          priority: s.priority,
          area: s.surface,
        });
        items.value = [created, ...items.value];
        selectedId.value = created.id;
        toast.push(`Submitted as ${created.id.slice(0, 8)}…`, { tone: 'success' });
      } catch (e) {
        toast.push(e instanceof Error ? e.message : 'Submit failed', { tone: 'error' });
      }
    },
  });
}

async function delRow(it: ImprovementSummary, e: Event): Promise<void> {
  e.stopPropagation();
  const ok = await confirm.open({
    title: 'Delete improvement?',
    body: `"${it.title}"`,
    danger: true,
    confirmLabel: 'Delete',
  });
  if (!ok) return;
  try {
    await improvApi.remove(it.id);
    items.value = items.value.filter(x => x.id !== it.id);
    toast.push('Improvement deleted', { tone: 'success' });
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Delete failed', { tone: 'error' });
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
          <div v-if="loading" :style="{ padding: '36px', textAlign: 'center', color: 'var(--fg2)', fontSize: '13px' }">Loading improvements…</div>
          <div v-else-if="error" :style="{ padding: '36px', textAlign: 'center', color: 'var(--color-red)', fontSize: '13px' }">{{ error }}</div>
          <div v-else-if="visibleItems.length === 0" :style="{ padding: '36px', textAlign: 'center', color: 'var(--fg2)', fontSize: '13px' }">
            <template v-if="items.length === 0">
              No improvements yet —
              <button class="btn btn--ghost btn--sm" :style="{ marginLeft: '6px' }" @click="suggest">suggest one</button>
            </template>
            <template v-else>No improvements match this filter.</template>
          </div>
          <div
            v-for="it in visibleItems"
            :key="it.id"
            :class="['improv-row2', { 'is-selected': it.id === selectedId }]"
            @click="selectedId = it.id"
          >
            <input type="checkbox" @click.stop />
            <div>
              <div class="improv-row2__title">{{ it.title }}</div>
              <div class="improv-row2__url">{{ it.submitted_by }}</div>
            </div>
            <div>
              <span v-if="it.status === 'pending'"     class="status-pill status-pill--pending">PENDING</span>
              <span v-else-if="it.status === 'rolled-out'" class="status-pill status-pill--rolled">ROLLED OUT</span>
              <span v-else class="status-pill" :style="{ textTransform: 'uppercase' }">{{ it.status }}</span>
            </div>
            <div>
              <span v-if="it.risk === 'critical'" class="risk-pill risk-pill--critical">CRITICAL</span>
              <span v-else-if="it.risk === 'high'" class="risk-pill risk-pill--high">HIGH</span>
              <span v-else-if="it.risk === 'medium'" class="risk-pill risk-pill--medium">MEDIUM</span>
              <span v-else class="risk-pill risk-pill--low">LOW</span>
            </div>
            <div class="improv-row2__priority">{{ priorityLabel(it.priority) }}</div>
            <div class="improv-row2__date">{{ fmtCreated(it.submitted_at) }}</div>
            <span
              class="improv-row2__del"
              :data-test-id="`improv-del-${it.id}`"
              @click="(e) => delRow(it, e)"
            >Del</span>
          </div>
        </div>
      </div>

      <div class="improv-detail">
        <ImprovDetail v-if="selectedForDetail" :item="selectedForDetail" @close="selectedId = null" />
      </div>
    </div>
  </main>
</template>
