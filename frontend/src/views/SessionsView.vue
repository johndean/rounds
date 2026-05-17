<script setup lang="ts">
/**
 * Sessions list — /sessions
 * Faithful 1:1 port of docs/port-source/sessions.jsx (184 LOC).
 * Same .sessions-table classes, .filter-chip-row, .kpi-row, .toolbar.
 * ?stage / ?ai / ?f query params honored.
 */
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import Icon from '@/components/shared/Icon.vue';
import StageBadge from '@/components/shared/StageBadge.vue';
import { SESSIONS } from '@/fixtures/sessions';
import { SOP_STAGES, SOP_STAGE_BY_ID } from '@/fixtures/sop_stages';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';

const router = useRouter();
const route = useRoute();

const query = ref('');
const sortBy = ref('updated');
const activeFilter = ref<string>((route.query.f as string) ?? 'all');
const stageFilter = ref<string | null>((route.query.stage as string) ?? null);
const aiFilter = ref<string | null>((route.query.ai as string) ?? null);

// Re-sync on hash change (pipeline-circle click on Dashboard, etc.)
watch(
  () => [route.query.stage, route.query.ai, route.query.f],
  ([s, a, f]) => {
    if (s) stageFilter.value = s as string; else stageFilter.value = null;
    if (a) aiFilter.value = a as string; else aiFilter.value = null;
    if (f) activeFilter.value = f as string;
    if (!s && !a && !f) { stageFilter.value = null; aiFilter.value = null; }
  },
);

const sessions = SESSIONS;

const filtered = computed(() => {
  let rows = [...sessions];
  if (stageFilter.value) rows = rows.filter(s => s.stage === stageFilter.value);
  if (aiFilter.value) {
    rows = rows.filter(s => {
      const inferred = s.status === 'processing' ? 'transcribe' : s.status === 'complete' ? 'ready' : 'ready';
      return inferred === aiFilter.value;
    });
  }
  if (activeFilter.value === 'active')     rows = rows.filter(s => s.status === 'active');
  if (activeFilter.value === 'processing') rows = rows.filter(s => s.status === 'processing');
  if (activeFilter.value === 'complete')   rows = rows.filter(s => s.status === 'complete');
  if (activeFilter.value === 'needs')      rows = rows.filter(s => s.needsReviewCount > 0);
  if (query.value) {
    const q = query.value.toLowerCase();
    rows = rows.filter(s => s.title.toLowerCase().includes(q) || s.presenter.toLowerCase().includes(q));
  }
  return rows;
});

const stageMeta = computed(() => stageFilter.value ? SOP_STAGE_BY_ID.get(stageFilter.value) : null);

function clearStageOrAi(): void {
  stageFilter.value = null;
  aiFilter.value = null;
  router.push('/sessions');
}

const filters = computed(() => [
  { id: 'all',        label: 'All',          count: sessions.length },
  { id: 'active',     label: 'In Workflow',  count: sessions.filter(s => s.status === 'active').length },
  { id: 'needs',      label: 'Needs Review', count: sessions.filter(s => s.needsReviewCount > 0).length },
  { id: 'processing', label: 'Processing',   count: sessions.filter(s => s.status === 'processing').length },
  { id: 'complete',   label: 'Published',    count: sessions.filter(s => s.status === 'complete').length },
]);

function aiStatusFor(s: typeof SESSIONS[number]): { label: string; chip: string } {
  if (s.status === 'processing') return { label: 'Processing', chip: 'amber' };
  if (s.status === 'complete')   return { label: 'Published',  chip: 'green' };
  return { label: 'Ready', chip: 'green' };
}

function routeFor(s: typeof SESSIONS[number]): string {
  return s.status === 'processing' ? `/p/${s.id}` : `/s/${s.id}`;
}

function exportCsv(): void {
  toast.push('Sessions CSV download started', { tone: 'success' });
}

async function deleteRow(s: typeof SESSIONS[number], e: Event): Promise<void> {
  e.stopPropagation();
  const ok = await confirm.open({
    title: `Delete ${s.code}?`,
    body: `This will mark the session as deleted. It can be restored from Settings → Deleted Sessions for 30 days.`,
    danger: true,
    confirmLabel: 'Delete',
  });
  if (ok) toast.push(`Deleted ${s.code}`, { tone: 'success' });
}

function formatRecorded(d: string): string {
  // 2026-05-14 → "05-14" then "05 · 14"
  return d.replace(/^\d{4}-/, '').replace(/-/, ' · ');
}

// Silence unused
void SOP_STAGES;
</script>

<template>
  <main class="page" data-screen-label="Sessions List">
    <div class="page-eyebrow">
      <span>Workspace</span><span class="sep">/</span><span>Sessions</span>
    </div>
    <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '20px', marginBottom: '8px' }">
      <div>
        <h1 class="page-title">Sessions</h1>
        <p class="page-desc">Continuing-education recordings in the v4 transcription pipeline. Click any row to open the editor, or use the SOP workflow to advance a session through review.</p>
      </div>
      <div class="page-actions">
        <button class="btn btn--secondary" data-test-id="sessions-export" @click="exportCsv">
          <Icon name="download" /> Export CSV
        </button>
        <button class="btn btn--primary" data-test-id="sessions-new-upload" @click="router.push('/upload')">
          <Icon name="circle-dot" /> New upload
        </button>
      </div>
    </div>

    <!-- KPI strip -->
    <div class="kpi-row" :style="{ marginTop: '18px' }">
      <div class="kpi">
        <div class="kpi__label">In Workflow</div>
        <div class="kpi__value">{{ sessions.filter(s => s.status === 'active').length }}</div>
        <div class="kpi__delta">▲ 2 since last week</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">Awaiting Medical Review</div>
        <div class="kpi__value">{{ sessions.filter(s => s.stage === 'medical').length }}</div>
        <div class="kpi__delta kpi__delta--down">▼ 1 since yesterday</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">Open Discrepancies</div>
        <div class="kpi__value">42</div>
        <div class="kpi__delta kpi__delta--down">▼ 11 since this morning</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">Published this Month</div>
        <div class="kpi__value">14</div>
        <div class="kpi__delta">▲ 3 vs Apr</div>
      </div>
    </div>

    <div class="toolbar">
      <div class="search">
        <Icon name="search" />
        <input v-model="query" placeholder="Search by title or presenter…" />
      </div>
      <div class="filter-chip-row">
        <span
          v-if="stageFilter || aiFilter"
          class="chip chip--solid"
          :style="{ display: 'inline-flex', alignItems: 'center', gap: '6px' }"
        >
          <template v-if="stageFilter">SOP: <strong>{{ stageMeta?.name }}</strong></template>
          <template v-else>AI: <strong>{{ aiFilter }}</strong></template>
          <button
            :style="{ background: 'transparent', border: 'none', color: 'inherit', fontSize: '13px', cursor: 'pointer', padding: 0, marginLeft: '4px' }"
            @click="clearStageOrAi"
          >×</button>
        </span>
        <button
          v-for="f in filters"
          :key="f.id"
          :class="['chip', { 'chip--solid': activeFilter === f.id }]"
          :style="{ cursor: 'pointer', border: '1px solid var(--border-subtle)' }"
          @click="activeFilter = f.id"
        >
          {{ f.label }} <span :style="{ opacity: 0.7 }">· {{ f.count }}</span>
        </button>
      </div>
      <div :style="{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center', fontSize: '12px', color: 'var(--fg2)' }">
        Sort
        <select v-model="sortBy" class="btn btn--secondary btn--sm" :style="{ paddingRight: '24px' }">
          <option value="updated">Last updated</option>
          <option value="recorded">Recorded date</option>
          <option value="stage">Stage</option>
          <option value="attendees">Attendees</option>
        </select>
      </div>
    </div>

    <div class="sessions-table" role="table" aria-label="Sessions">
      <div class="sessions-table__row sessions-table__row--head" role="row">
        <div>Code</div>
        <div>Session</div>
        <div>AI Status</div>
        <div>SOP</div>
        <div>Segs</div>
        <div>Created</div>
        <div></div>
      </div>
      <div
        v-for="s in filtered"
        :key="s.id"
        role="row"
        class="sessions-table__row sessions-table__row--body"
        @click="router.push(routeFor(s))"
      >
        <div class="sessions-table__code">{{ s.code || s.id }}</div>
        <div>
          <div class="sessions-table__title">{{ s.title }}</div>
          <div class="sessions-table__sub">{{ (s.code || s.id) + (s.status === 'processing' ? '_audio.mp3' : '_trim.mp3') }}</div>
        </div>
        <div>
          <span :class="['chip', `chip--${aiStatusFor(s).chip}`]">
            <span class="chip__dot" /> {{ aiStatusFor(s).label }}
          </span>
        </div>
        <div><StageBadge :id="s.stage" /></div>
        <div class="sessions-table__meta" :style="{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: 'var(--fg1)' }">{{ s.segs || 0 }}</div>
        <div class="sessions-table__updated">{{ formatRecorded(s.recorded) }}</div>
        <div :style="{ textAlign: 'right' }">
          <button
            class="btn btn--ghost btn--icon btn--sm"
            :data-test-id="`sessions-delete-${s.id}`"
            title="Delete"
            @click="(e) => deleteRow(s, e)"
          >
            <Icon name="x" :size="12" />
          </button>
        </div>
      </div>
      <div v-if="filtered.length === 0" :style="{ padding: '36px', textAlign: 'center', color: 'var(--fg2)' }">
        No sessions match this filter.
      </div>
    </div>
  </main>
</template>
