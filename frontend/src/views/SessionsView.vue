<script setup lang="ts">
/**
 * Sessions list — /sessions
 *
 * Wired to GET /v1/sessions. DOM structure matches React sessions.jsx
 * (.page, .page-eyebrow, .kpi-row, .toolbar, .filter-chip-row,
 * .sessions-table). Fixture import removed — fetches live rows; empty
 * state when no session has been uploaded yet.
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import Icon from '@/components/shared/Icon.vue';
import StageBadge from '@/components/shared/StageBadge.vue';
import { sessions as sessionsApi, type SessionSummary, type SessionFailureReason } from '@/services/api';
import { SOP_STAGE_BY_ID } from '@/fixtures/sop_stages';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';
import { ApiError } from '@/services/http';

const router = useRouter();
const route = useRoute();

const sessions = ref<SessionSummary[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const query = ref('');
const sortBy = ref('updated');
const activeFilter = ref<string>((route.query.f as string) ?? 'all');
const stageFilter = ref<string | null>((route.query.stage as string) ?? null);
const aiFilter = ref<string | null>((route.query.ai as string) ?? null);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    sessions.value = await sessionsApi.list({
      stage: stageFilter.value ?? undefined,
      ai: aiFilter.value ?? undefined,
      f: query.value || undefined,
    });
  } catch (e) {
    error.value = e instanceof ApiError ? `${e.status}: ${e.message}` : e instanceof Error ? e.message : 'Failed to load';
  } finally {
    loading.value = false;
  }
}

onMounted(load);

watch(
  () => [route.query.stage, route.query.ai, route.query.f],
  ([s, a, f]) => {
    stageFilter.value = (s as string) || null;
    aiFilter.value = (a as string) || null;
    if (f) activeFilter.value = f as string;
    void load();
  },
);

const filtered = computed<SessionSummary[]>(() => {
  let rows = [...sessions.value];
  if (activeFilter.value === 'active')     rows = rows.filter(s => s.status === 'ready' || s.status === 'ingesting');
  if (activeFilter.value === 'processing') rows = rows.filter(s => s.status === 'ingesting');
  if (activeFilter.value === 'complete')   rows = rows.filter(s => s.status === 'complete' || s.status === 'archived');
  if (query.value) {
    const q = query.value.toLowerCase();
    rows = rows.filter(s => s.title.toLowerCase().includes(q) || (s.presenter || '').toLowerCase().includes(q));
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
  { id: 'all',        label: 'All',          count: sessions.value.length },
  { id: 'active',     label: 'In Workflow',  count: sessions.value.filter(s => s.status === 'ready' || s.status === 'ingesting').length },
  { id: 'processing', label: 'Processing',   count: sessions.value.filter(s => s.status === 'ingesting').length },
  { id: 'complete',   label: 'Published',    count: sessions.value.filter(s => s.status === 'complete').length },
]);

function aiStatusFor(s: SessionSummary): { label: string; chip: string } {
  if (s.status === 'ingesting') return { label: 'Processing', chip: 'amber' };
  if (s.status === 'complete')  return { label: 'Published',  chip: 'green' };
  if (s.status === 'failed')    return { label: 'Failed',     chip: 'red'   };
  return { label: 'Ready', chip: 'green' };
}

function routeFor(s: SessionSummary): string {
  return s.status === 'ingesting' ? `/p/${s.id}` : `/s/${s.id}`;
}

function exportCsv(): void {
  toast.push('Sessions CSV download started', { tone: 'success' });
}

async function deleteRow(s: SessionSummary, e: Event): Promise<void> {
  e.stopPropagation();
  const ok = await confirm.open({
    title: `Delete ${s.code}?`,
    body: 'This will mark the session as deleted. Recoverable from Settings → Deleted Sessions for 30 days.',
    danger: true,
    confirmLabel: 'Delete',
  });
  if (!ok) return;
  try {
    await sessionsApi.remove(s.id);
    sessions.value = sessions.value.filter((x) => x.id !== s.id);
    toast.push(`Deleted ${s.code}`, { tone: 'success' });
  } catch (err) {
    const msg = err instanceof ApiError ? `${err.status} — ${err.message}` : (err instanceof Error ? err.message : 'Delete failed');
    toast.push(`Failed to delete ${s.code}: ${msg}`, { tone: 'error' });
  }
}

// ─── Failure-detail modal (click "Failed" status pill on a row) ─────────
const failureModal = ref<SessionFailureReason | null>(null);
const failureLoading = ref(false);

async function showFailureReason(s: SessionSummary, e: Event): Promise<void> {
  e.stopPropagation();
  failureLoading.value = true;
  try {
    failureModal.value = await sessionsApi.failureReason(s.id);
  } catch (err) {
    toast.push('Could not load failure reason', { tone: 'error' });
  } finally {
    failureLoading.value = false;
  }
}
function closeFailureModal(): void { failureModal.value = null; }
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

    <div class="kpi-row" :style="{ marginTop: '18px' }">
      <div class="kpi">
        <div class="kpi__label">In Workflow</div>
        <div class="kpi__value">{{ sessions.filter(s => s.status === 'ready' || s.status === 'ingesting').length }}</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">Processing</div>
        <div class="kpi__value">{{ sessions.filter(s => s.status === 'ingesting').length }}</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">Published</div>
        <div class="kpi__value">{{ sessions.filter(s => s.status === 'complete').length }}</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">Total</div>
        <div class="kpi__value">{{ sessions.length }}</div>
      </div>
    </div>

    <div class="toolbar">
      <div class="search">
        <Icon name="search" />
        <input v-model="query" placeholder="Search by title or presenter…" @keyup.enter="load" />
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
          <option value="code">Code</option>
          <option value="title">Title</option>
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
        <div>Words</div>
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
          <div class="sessions-table__sub">{{ s.presenter || '—' }}</div>
        </div>
        <div>
          <button
            v-if="s.status === 'failed'"
            type="button"
            :class="['chip', 'chip--red']"
            :data-test-id="`sessions-failure-${s.id}`"
            :style="{ cursor: 'pointer', border: 'none' }"
            title="Click for failure details"
            @click="(e) => showFailureReason(s, e)"
          >
            <span class="chip__dot" /> Failed · why?
          </button>
          <span v-else :class="['chip', `chip--${aiStatusFor(s).chip}`]">
            <span class="chip__dot" /> {{ aiStatusFor(s).label }}
          </span>
        </div>
        <div><StageBadge id="prep" /></div>
        <div class="sessions-table__meta" :style="{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: 'var(--fg1)' }">{{ s.segment_count || 0 }}</div>
        <div class="sessions-table__updated" :style="{ fontVariantNumeric: 'tabular-nums' }">{{ s.word_count || 0 }}</div>
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
      <div v-if="loading" :style="{ padding: '36px', textAlign: 'center', color: 'var(--fg2)' }">Loading sessions…</div>
      <div v-else-if="error" :style="{ padding: '36px', textAlign: 'center', color: 'var(--color-red)' }">{{ error }}</div>
      <div v-else-if="filtered.length === 0" :style="{ padding: '36px', textAlign: 'center', color: 'var(--fg2)' }">
        <template v-if="sessions.length === 0">
          No sessions yet —
          <button class="btn btn--ghost btn--sm" :style="{ marginLeft: '6px' }" @click="router.push('/upload')">upload one</button>
        </template>
        <template v-else>No sessions match this filter.</template>
      </div>
    </div>

    <!-- Failure-detail modal — surfaced from clicking the "Failed · why?" pill -->
    <div
      v-if="failureModal"
      class="modal-overlay"
      role="dialog"
      aria-modal="true"
      :style="{ position: 'fixed', inset: 0, background: 'rgba(8, 14, 24, 0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }"
      @click.self="closeFailureModal"
      @keydown.esc="closeFailureModal"
    >
      <div
        class="card"
        :style="{ background: 'var(--surface)', maxWidth: '640px', width: '90%', maxHeight: '80vh', overflowY: 'auto', padding: '20px 24px', borderRadius: '8px', boxShadow: '0 12px 32px rgba(8, 14, 24, 0.25)' }"
      >
        <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px', gap: '12px' }">
          <div>
            <div :style="{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--fg2)', fontWeight: 700, marginBottom: '4px' }">Session failed</div>
            <h3 :style="{ margin: 0, fontSize: '17px', fontWeight: 700, color: 'var(--fg1)' }">{{ failureModal.title }}</h3>
            <div :style="{ fontSize: '12px', color: 'var(--fg2)', fontFamily: 'var(--font-mono)', marginTop: '2px' }">{{ failureModal.code }}</div>
          </div>
          <button
            class="btn btn--ghost btn--icon btn--sm"
            data-test-id="failure-modal-close"
            title="Close"
            @click="closeFailureModal"
          ><Icon name="x" :size="12" /></button>
        </div>

        <div v-if="failureModal.reason || failureModal.category" :style="{ background: 'var(--surface-bg)', border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: '12px 14px', marginTop: '12px' }">
          <div v-if="failureModal.category" :style="{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--color-red)', fontWeight: 700, marginBottom: '6px' }">
            {{ failureModal.category }}
          </div>
          <div :style="{ fontSize: '13px', color: 'var(--fg1)', lineHeight: 1.55, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }">
            {{ failureModal.reason || '(no reason recorded)' }}
          </div>
          <div v-if="failureModal.ts || failureModal.actor" :style="{ fontSize: '11px', color: 'var(--fg2)', marginTop: '8px', fontFamily: 'var(--font-mono)' }">
            <span v-if="failureModal.ts">{{ failureModal.ts }}</span>
            <span v-if="failureModal.actor" :style="{ marginLeft: '10px' }">· {{ failureModal.actor }}</span>
          </div>
        </div>
        <div v-else :style="{ padding: '12px 0', color: 'var(--fg2)', fontSize: '13px' }">
          No specific failure reason recorded — check audit log for the full trail.
        </div>

        <div v-if="failureModal.log_tail && failureModal.log_tail.length" :style="{ marginTop: '16px' }">
          <div :style="{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--fg2)', fontWeight: 700, marginBottom: '6px' }">Recent transitions</div>
          <div
            v-for="(entry, i) in failureModal.log_tail.slice().reverse()"
            :key="i"
            :style="{ fontSize: '11.5px', fontFamily: 'var(--font-mono)', color: 'var(--fg2)', padding: '4px 0', borderTop: i > 0 ? '1px dashed var(--border-subtle)' : 'none' }"
          >
            <span v-if="entry.ts">{{ entry.ts }}</span>
            <span v-if="entry.prev || entry.next" :style="{ marginLeft: '8px', color: 'var(--fg1)' }">
              {{ entry.prev || '—' }} → {{ entry.next || '—' }}
            </span>
            <span v-if="entry.reason" :style="{ marginLeft: '8px' }">· {{ entry.reason }}</span>
          </div>
        </div>

        <div :style="{ marginTop: '18px', display: 'flex', justifyContent: 'flex-end', gap: '8px' }">
          <RouterLink :to="`/e/${failureModal.session_id}/audit`" class="btn btn--secondary btn--sm" @click="closeFailureModal">
            Open audit log
          </RouterLink>
          <button class="btn btn--primary btn--sm" @click="closeFailureModal">Close</button>
        </div>
      </div>
    </div>
  </main>
</template>
