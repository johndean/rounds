<script setup lang="ts">
/**
 * Dashboard — /dashboard
 *
 * Same DOM as docs/port-source/dashboard.jsx::DashboardRoute (445 LOC).
 * Wired to GET /v1/sessions for real KPI counts + pipeline counts + queue.
 * Widgets that need historical/derived data (sparklines, age alerts,
 * hotspots, storage breakdown, jobs queue) render their visual chrome
 * with safe zero/empty values until the matching stats endpoints land.
 */
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import Icon from '@/components/shared/Icon.vue';
import StageBadge from '@/components/shared/StageBadge.vue';
import Sparkline from '@/components/dashboard/Sparkline.vue';
import { SOP_STAGES } from '@/fixtures/sop_stages';
import { sessions as sessionsApi, type SessionSummary } from '@/services/api';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/composables/useToast';

const router = useRouter();
const auth = useAuthStore();

const allSessions = ref<SessionSummary[]>([]);
const loading = ref(true);

onMounted(async () => {
  try { allSessions.value = await sessionsApi.list({}); }
  catch { /* zeros if backend fails */ }
  finally { loading.value = false; }
});

const pipelineFilter = ref<string>('All types');
const timeRange = ref<string>('7d');

const aiCount = computed(() => allSessions.value.length);
const readyCount = computed(() => allSessions.value.filter(s => s.status === 'ready' || s.status === 'complete').length);
const processingCount = computed(() => allSessions.value.filter(s => s.status === 'ingesting').length);
const segmentTotal = computed(() => allSessions.value.reduce((a, s) => a + (s.segment_count || 0), 0));
const wordTotal = computed(() => allSessions.value.reduce((a, s) => a + (s.word_count || 0), 0));

interface Kpi { label: string; value: string | number; sub: string; spark: number[]; color?: string; subCode?: string }
const topKpis = computed<Kpi[]>(() => [
  { label: 'AI Sessions',     value: aiCount.value,        sub: `${readyCount.value} ready · ${processingCount.value} processing`, spark: [] },
  { label: 'SOP Sessions',    value: aiCount.value,        sub: '8-stage workflow', spark: [] },
  { label: 'Segments',        value: segmentTotal.value.toLocaleString(), sub: '', subCode: 'words[]', spark: [] },
  { label: 'Words',           value: wordTotal.value.toLocaleString(),    sub: 'total transcribed', spark: [] },
  { label: 'CMS Published',   value: allSessions.value.filter(s => s.status === 'complete').length, sub: '', subCode: 'cms_documents', spark: [] },
  { label: 'Improvement RQs', value: 0,                    sub: 'see /improvements', spark: [] },
]);

const queue = computed(() => allSessions.value.slice(0, 3));

const opsKpis: Kpi[] = [
  { label: 'Unresolved Discrepancies', value: 0,  sub: 'global review backlog', spark: [], color: 'var(--text-accent)' },
  { label: 'QA Tasks',                 value: 0,  sub: '0 overdue · 0 passed',  spark: [] },
  { label: 'Storage Used',             value: '—', sub: 'across all sources',    spark: [] },
  { label: 'Avg Processing',           value: '—', sub: '0 samples',             spark: [] },
  { label: 'Avg Feedback',             value: '—', sub: '0 ratings',             spark: [] },
  { label: 'Fusion Runs',              value: 0,  sub: '',                       subCode: 'replay_log', spark: [] },
];

interface Sla { id: string; label: string; dAvg: number | null; target: number; sess: number; state: 'ok' | 'breach' | 'empty' }
const sla = computed<Sla[]>(() => SOP_STAGES.map((s) => ({
  id: s.id, label: s.name, dAvg: null, target: 2, sess: 0, state: 'empty' as const,
})));

const aiPipeline = computed(() => [
  { id: 'upload',     label: 'Upload',     code: 'UPLOAD',     count: 0,                       state: 'idle'   },
  { id: 'transcribe', label: 'Transcribe', code: 'TRANSCRIBE', count: processingCount.value,   state: processingCount.value > 0 ? 'active' : 'idle' },
  { id: 'normalize',  label: 'Normalize',  code: 'NORMALIZE',  count: 0,                       state: 'idle'   },
  { id: 'align',      label: 'Align',      code: 'ALIGN',      count: 0,                       state: 'idle'   },
  { id: 'fuse',       label: 'Fuse',       code: 'FUSE',       count: 0,                       state: 'idle'   },
  { id: 'ready',      label: 'Ready',      code: 'READY',      count: readyCount.value,        state: readyCount.value > 0 ? 'active' : 'idle' },
  { id: 'failed',     label: 'Failed',     code: 'FAILED',     count: allSessions.value.filter(s => s.status === 'failed').length, state: 'failed' },
]);

interface SopPipelineEntry { id: string; count: number; attn?: boolean }
const sopPipeline = computed<SopPipelineEntry[]>(() => SOP_STAGES.map((s) => ({ id: s.id, count: 0 })));

const stageById = (id: string) => SOP_STAGES.find(s => s.id === id);

const typeChips = ['All types', 'ARAV', 'NAVAS'];

const greeting = computed(() => {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
});
const dateLabel = computed(() =>
  new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }).toUpperCase(),
);
const userFirstName = computed(() => {
  const handle = auth.email?.split('@')[0] ?? 'there';
  return handle.split(/[._-]/)[0]!.charAt(0).toUpperCase() + handle.split(/[._-]/)[0]!.slice(1);
});

function openClaim(e: Event): void {
  e.preventDefault();
  toast.push('Claim flow lands when ingest produces an unassigned queue', { tone: 'info' });
}
</script>

<template>
  <main class="page dash-page" data-screen-label="Dashboard">
    <div class="dash-header">
      <div>
        <div class="dash-eyebrow">Today · {{ dateLabel }}</div>
        <h1 class="dash-title">{{ greeting }}, {{ userFirstName }}</h1>
        <p class="dash-lead">
          <template v-if="loading">Loading sessions…</template>
          <template v-else>Dual-pipeline system · {{ aiCount }} session{{ aiCount === 1 ? '' : 's' }} · {{ readyCount }} ready · {{ processingCount }} processing</template>
        </p>
      </div>
      <div class="page-actions">
        <button class="btn btn--secondary" data-test-id="dash-filters" @click="toast.push('Filter panel — coming soon')">
          <Icon name="filter" /> Filters
        </button>
        <button class="btn btn--primary" @click="router.push('/upload')">
          <Icon name="circle-dot" /> New upload
        </button>
      </div>
    </div>

    <div class="dash-kpis dash-kpis--6">
      <div v-for="k in topKpis" :key="k.label" class="dash-kpi">
        <div class="dash-kpi__label">{{ k.label }}</div>
        <div class="dash-kpi__value">{{ k.value }}</div>
        <div class="dash-kpi__sub">
          {{ k.sub }}<code v-if="k.subCode">{{ k.subCode }}</code>
        </div>
        <Sparkline :data="k.spark" />
      </div>
    </div>

    <section class="dash-section">
      <div class="dash-section__head">
        <span class="dash-section__title">Your Queue</span>
        <span class="dash-section__sub">Most recent sessions</span>
        <RouterLink to="/sessions" class="dash-section__action">View all →</RouterLink>
      </div>
      <div class="dash-queue">
        <div
          v-for="q in queue"
          :key="q.id"
          class="dash-queue__card"
          @click="router.push(q.status === 'ingesting' ? `/p/${q.id}` : `/e/${q.id}`)"
        >
          <div class="dash-queue__head">
            <div class="dash-queue__code">{{ q.code }}</div>
            <StageBadge id="prep" />
          </div>
          <div class="dash-queue__title">{{ q.title }}</div>
          <div class="dash-queue__meta">
            <span>{{ q.segment_count || 0 }} segs</span><span>·</span>
            <span>{{ q.status }}</span>
          </div>
          <div class="dash-queue__foot">
            <span class="dash-queue__status">{{ q.presenter || '—' }}</span>
            <button class="btn btn--primary btn--sm">Open <Icon name="chevron-right" :size="11" /></button>
          </div>
        </div>
        <div v-if="!loading && queue.length === 0" :style="{ padding: '40px 18px', color: 'var(--fg2)', fontSize: '13px', textAlign: 'center', gridColumn: '1 / -1' }">
          No sessions yet —
          <button class="btn btn--ghost btn--sm" :style="{ marginLeft: '6px' }" @click="router.push('/upload')">upload one</button>
        </div>
      </div>
    </section>

    <section class="dash-section">
      <div class="dash-section__head">
        <span class="dash-section__title">Pipeline</span>
        <span class="dash-section__sub">{{ aiCount }} session{{ aiCount === 1 ? '' : 's' }} · 7 AI stages + 8 SOP stages</span>
        <div class="dash-section__filter">
          <button
            v-for="t in typeChips"
            :key="t"
            :class="['chip', { 'chip--solid': pipelineFilter === t }]"
            :style="{ cursor: 'pointer' }"
            @click="pipelineFilter = t"
          >{{ t }}</button>
        </div>
      </div>

      <div class="dash-pipeline-card">
        <div class="dash-pipeline-card__eyebrow">
          Pipeline 1 · AI Processing · <code>session.status</code> · 7 stages
        </div>
        <div class="dash-pipeline">
          <template v-for="(s, i) in aiPipeline" :key="s.id">
            <button
              type="button"
              class="dash-pipe-step"
              :data-test-id="`pipe-ai-${s.id}`"
              @click="router.push(`/sessions?ai=${s.id}`)"
            >
              <div :class="['dash-pipe-circle', `dash-pipe-circle--${s.state}`, { 'is-populated': s.count > 0 }]">{{ s.count }}</div>
              <div class="dash-pipe-name">{{ s.label }}</div>
              <div class="dash-pipe-code">{{ s.code }}</div>
            </button>
            <span v-if="i < aiPipeline.length - 1" class="dash-pipe-arrow">›</span>
          </template>
        </div>
      </div>

      <div class="dash-pipeline-card" :style="{ marginTop: '10px' }">
        <div class="dash-pipeline-card__eyebrow">
          Pipeline 2 · SOP Control Layer · <code>sop_state.stage</code> · 8 stages
        </div>
        <div class="dash-pipeline">
          <template v-for="(s, i) in sopPipeline" :key="s.id">
            <button
              type="button"
              class="dash-pipe-step"
              :data-test-id="`pipe-sop-${s.id}`"
              @click="router.push(`/sessions?stage=${s.id}`)"
            >
              <div :class="['dash-pipe-circle', s.count > 0 ? 'dash-pipe-circle--active' : 'dash-pipe-circle--idle', { 'is-attn': s.attn }]">{{ s.count }}</div>
              <div class="dash-pipe-name">{{ stageById(s.id)?.name }}</div>
              <div class="dash-pipe-code">{{ s.id.toUpperCase() }}</div>
              <div v-if="s.attn" class="dash-pipe-attn">ATTN</div>
            </button>
            <span v-if="i < sopPipeline.length - 1" class="dash-pipe-arrow">›</span>
          </template>
        </div>
      </div>
    </section>

    <section class="dash-section dash-section--ops">
      <div class="dash-section__head">
        <div>
          <div class="dash-section__eyebrow">Operations · Workflow Health, Throughput, Storage</div>
          <span class="dash-section__title dash-section__title--big">System overview</span>
        </div>
        <div class="dash-section__filter dash-tabs">
          <button
            v-for="t in ['7d', '30d', '90d', 'All']"
            :key="t"
            :class="['dash-tab', { 'is-active': timeRange === t }]"
            @click="timeRange = t"
          >{{ t }}</button>
        </div>
      </div>

      <div class="dash-kpis dash-kpis--6">
        <div v-for="k in opsKpis" :key="k.label" class="dash-kpi">
          <div class="dash-kpi__label">{{ k.label }}</div>
          <div class="dash-kpi__value" :style="k.color ? { color: k.color } : undefined">{{ k.value }}</div>
          <div class="dash-kpi__sub">
            {{ k.sub }}<code v-if="k.subCode">{{ k.subCode }}</code>
          </div>
          <Sparkline :data="k.spark" />
        </div>
      </div>

      <div class="dash-sla">
        <div class="dash-sla__head">
          <div class="dash-section__eyebrow">SLA BY STAGE · DWELL TIME VS TARGET</div>
          <div class="dash-sla__legend">
            <span><span class="dot" :style="{ background: 'var(--color-green)' }" /> on target</span>
            <span><span class="dot" :style="{ background: 'var(--color-blue)' }" /> at risk</span>
            <span><span class="dot" :style="{ background: 'var(--color-red)' }" /> breach</span>
          </div>
        </div>
        <div class="dash-sla__grid">
          <div
            v-for="s in sla"
            :key="s.id"
            :class="['dash-sla__cell', `dash-sla__cell--${s.state}`]"
          >
            <div class="dash-sla__label">{{ s.label }}</div>
            <div class="dash-sla__value">
              <strong v-if="s.dAvg != null">{{ s.dAvg }}</strong>
              <strong v-else :style="{ color: 'var(--fg2)' }">—</strong>
              <span v-if="s.dAvg != null"> d avg</span>
            </div>
            <div class="dash-sla__bar"><span :style="{ width: '0%' }" /></div>
            <div class="dash-sla__foot">
              <span>{{ s.sess }} sess</span>
              <span>target {{ s.target }}d</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div class="dash-three">
      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">SOP Age Alerts</span>
          <span class="dash-section__sub">Oldest first</span>
          <a class="dash-section__action" href="#/sessions">All →</a>
        </div>
        <div class="dash-widget__body">
          <div :style="{ padding: '20px', color: 'var(--fg2)', fontSize: '12px', textAlign: 'center' }">No data yet.</div>
        </div>
      </div>
      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">Correction Hotspots</span>
          <span class="dash-section__sub">Top 5 edited</span>
          <a class="dash-section__action" href="#/sessions">All →</a>
        </div>
        <div class="dash-widget__body">
          <div :style="{ padding: '20px', color: 'var(--fg2)', fontSize: '12px', textAlign: 'center' }">No data yet.</div>
        </div>
      </div>
      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">Storage Top Sessions</span>
          <span class="dash-section__sub">By size</span>
          <a class="dash-section__action" href="#/sessions">All →</a>
        </div>
        <div class="dash-widget__body">
          <div :style="{ padding: '20px', color: 'var(--fg2)', fontSize: '12px', textAlign: 'center' }">No data yet.</div>
        </div>
      </div>
    </div>

    <div class="dash-three">
      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">Jobs Queue</span>
          <span class="dash-section__sub">Last 24h</span>
        </div>
        <div class="dash-widget__body">
          <div :style="{ padding: '20px', color: 'var(--fg2)', fontSize: '12px', textAlign: 'center' }">Celery queue is empty.</div>
        </div>
      </div>
      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">Storage Breakdown</span>
        </div>
        <div class="dash-widget__body">
          <div :style="{ padding: '20px', color: 'var(--fg2)', fontSize: '12px', textAlign: 'center' }">No data yet.</div>
        </div>
      </div>
      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">Assignment Coverage</span>
        </div>
        <div class="dash-widget__body">
          <div class="dash-coverage-row dash-coverage-row--unassigned">
            <div :style="{ flex: 1 }">
              <div class="dash-coverage-row__name" :style="{ color: 'var(--text-accent)' }">Unassigned</div>
              <div class="dash-coverage-row__role">pool</div>
            </div>
            <div class="dash-coverage-row__load">{{ aiCount }}</div>
            <a
              class="dash-section__action"
              href="#/sessions"
              :style="{ fontSize: '11px' }"
              data-test-id="dash-claim"
              @click="openClaim"
            >claim →</a>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>
