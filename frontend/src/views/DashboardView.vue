<script setup lang="ts">
/**
 * Dashboard — /dashboard
 * Faithful 1:1 port of docs/port-source/dashboard.jsx (445 lines).
 * Same .dash-* class names, same data-test-ids, same DOM tree, same fixture shapes.
 * Fixture data is hard-coded here (matches the React source verbatim) until
 * the corresponding backend KPI endpoints land; user name + greeting are
 * derived from auth.email.
 */
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import Icon from '@/components/shared/Icon.vue';
import StageBadge from '@/components/shared/StageBadge.vue';
import Sparkline from '@/components/dashboard/Sparkline.vue';
import { SOP_STAGES } from '@/fixtures/sop_stages';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/composables/useToast';

const router = useRouter();
const auth = useAuthStore();

const pipelineFilter = ref<string>('All types');
const timeRange = ref<string>('7d');

// ── Top KPI strip — 6 cards w/ sparklines ────────────────────────────
interface Kpi { label: string; value: string | number; sub: string; spark: number[]; color?: string; subCode?: string }
const topKpis: Kpi[] = [
  { label: 'AI Sessions',     value: 19,      sub: '19 ready · 0 processing',  spark: [12,14,15,17,16,18,19] },
  { label: 'SOP Sessions',    value: 23,      sub: '8-stage workflow',          spark: [18,19,21,20,22,22,23] },
  { label: 'Segments',        value: '1,607', sub: '',                          subCode: 'words[]', spark: [800,1020,1190,1310,1420,1530,1607] },
  { label: 'Artifacts',       value: 1,       sub: '0 lineage rows',            spark: [0,0,0,0,0,1,1] },
  { label: 'CMS Published',   value: 0,       sub: '',                          subCode: 'cms_documents', spark: [0,0,0,0,0,0,0] },
  { label: 'Improvement RQs', value: 4,       sub: '0 pending',                 spark: [1,2,2,3,4,4,4] },
];

// ── Your Queue ───────────────────────────────────────────────────────
const queue = [
  { code: '010525_Lykins',    stage: 'copy_final', stageLabel: 'Copy Edit (final)', title: 'VIN/ARAV Rounds: A Spectacle to Behold',        segs: 100, aligned: true, due: 'Due in 2d', status: 'Review and lock copy' },
  { code: '040226_Williams',  stage: 'medical',    stageLabel: 'Medical Review',    title: 'Controlled Substances: Addressing Drug Diversion', segs: 56,  aligned: true, due: 'Due in 3d', status: 'Medical accuracy pass' },
  { code: '010925_Gottlieb',  stage: 'copy_draft', stageLabel: 'Copy Edit (draft)', title: 'VIN/IVAPM Rounds: Chronic Pain',                  segs: 62,  aligned: true, due: 'Due in 4d', status: 'Apply copy edits' },
];

// ── Operations KPIs — 6 cards w/ sparklines ──────────────────────────
const opsKpis: Kpi[] = [
  { label: 'Unresolved Discrepancies', value: '1,574', sub: 'global review backlog', spark: [1800,1720,1690,1640,1610,1590,1574], color: 'var(--text-accent)' },
  { label: 'QA Tasks',                 value: 0,       sub: '0 overdue · 0 passed',  spark: [3,2,4,1,2,1,0] },
  { label: 'Storage Used',             value: '3.7 GB', sub: 'across all sources',   spark: [2.4,2.7,3.0,3.2,3.4,3.6,3.7] },
  { label: 'Avg Processing',           value: '3.9m',  sub: '19 samples',            spark: [4.5,4.4,4.2,4.1,4.0,3.95,3.9] },
  { label: 'Avg Feedback',             value: '—',     sub: '0 ratings',             spark: [] },
  { label: 'Fusion Runs',              value: 0,       sub: '',                       subCode: 'replay_log', spark: [] },
];

// ── SLA by stage · dwell vs target ────────────────────────────────────
interface Sla { id: string; label: string; dAvg: number | null; target: number; sess: number; state: 'ok' | 'breach' | 'empty' }
const sla: Sla[] = [
  { id: 'prep',       label: 'Prep',              dAvg: 2.1,  target: 3, sess: 17, state: 'ok' },
  { id: 'copy_draft', label: 'Copy Edit (draft)', dAvg: 1.4,  target: 2, sess: 1,  state: 'ok' },
  { id: 'medical',    label: 'Medical Review',    dAvg: 3.3,  target: 2, sess: 1,  state: 'breach' },
  { id: 'copy_final', label: 'Copy Edit (final)', dAvg: 1.8,  target: 2, sess: 3,  state: 'ok' },
  { id: 'cms',        label: 'CMS Published',     dAvg: 0.9,  target: 1, sess: 1,  state: 'ok' },
  { id: 'captions',   label: 'Captions',          dAvg: null, target: 1, sess: 0,  state: 'empty' },
  { id: 'qa',         label: 'QA',                dAvg: null, target: 1, sess: 0,  state: 'empty' },
  { id: 'complete',   label: 'Complete',          dAvg: null, target: 0, sess: 0,  state: 'empty' },
];

// ── AI processing pipeline — 7 stages ────────────────────────────────
const aiPipeline = [
  { id: 'upload',     label: 'Upload',     code: 'UPLOAD',     count: 0,  state: 'idle' },
  { id: 'transcribe', label: 'Transcribe', code: 'TRANSCRIBE', count: 0,  state: 'idle' },
  { id: 'normalize',  label: 'Normalize',  code: 'NORMALIZE',  count: 0,  state: 'idle' },
  { id: 'align',      label: 'Align',      code: 'ALIGN',      count: 0,  state: 'idle' },
  { id: 'fuse',       label: 'Fuse',       code: 'FUSE',       count: 0,  state: 'idle' },
  { id: 'ready',      label: 'Ready',      code: 'READY',      count: 19, state: 'active' },
  { id: 'failed',     label: 'Failed',     code: 'FAILED',     count: 0,  state: 'failed' },
] as const;

// ── SOP pipeline — 8 stages ──────────────────────────────────────────
interface SopPipelineEntry { id: string; count: number; attn?: boolean }
const sopPipeline: SopPipelineEntry[] = [
  { id: 'prep',       count: 17 },
  { id: 'copy_draft', count: 1 },
  { id: 'medical',    count: 1, attn: true },
  { id: 'copy_final', count: 3 },
  { id: 'cms',        count: 1 },
  { id: 'captions',   count: 0 },
  { id: 'qa',         count: 0 },
  { id: 'complete',   count: 0 },
];

const stageById = (id: string) => SOP_STAGES.find(s => s.id === id);

// ── Side widgets ──────────────────────────────────────────────────────
const ageAlerts = [
  { title: 'Crafting a Neurodivergent Career in Veterinary Practice',                 stage: 'Prep',     age: '3.4d' },
  { title: 'VIN/IVAPM Rounds: Chronic Pain',                                          stage: 'Prep',     age: '3.4d' },
  { title: 'Controlled Substances, Uncontrolled Access: Addressing Drug Diversion…',  stage: 'Prep',     age: '3.4d' },
  { title: 'VIN/AEMV Rounds: Exotic Companion Mammal Enrichment and Training',        stage: 'CE Final', age: '3.4d' },
  { title: 'VIN/IVAPM Rounds: Chronic Pain',                                          stage: 'Medical',  age: '3.4d' },
];
const hotspots = [
  { title: 'Session 2026-04-18 14:41',                                                 edits: 16, pct: 100 },
  { title: 'VIN/ARAV Rounds: A Spectacle to Behold: Snake Ophthalmology Cas…',          edits: 9,  pct: 56 },
  { title: 'Cage-side Radiology Rounds: Various Cases. January 6, 2025',                edits: 5,  pct: 31 },
  { title: 'Tuesday Topic: Understanding Separation-Related Behaviors',                 edits: 3,  pct: 19 },
  { title: 'Tuesday Topic: Equine Dermatology: Bacterial Dermatitis in the Horse:…',     edits: 2,  pct: 12 },
];
const storageTop = [
  { title: 'VIN/VECCS Rounds: Snake Envenomation Management in Pets',                   size: '364 MB', pct: 100 },
  { title: 'VIN/ARAV Rounds: A Spectacle to Behold: Snake Ophthalmology Ca…',            size: '231 MB', pct: 63 },
  { title: 'VIN/AEMV Rounds: Exotic Companion Mammal Enrichment and Train…',             size: '228 MB', pct: 62 },
  { title: 'Cage-Side Radiology Rounds: Various Cases',                                  size: '217 MB', pct: 59 },
  { title: 'Lessons Learned From Human Commercial Labs: HbA1C in Europe',                size: '196 MB', pct: 54 },
];
const jobs = [
  { name: 'transcribe',  ok: 19, err: 0 },
  { name: 'normalize',   ok: 19, err: 0 },
  { name: 'align',       ok: 19, err: 0 },
  { name: 'fuse',        ok: 19, err: 0 },
  { name: 'publish_cms', ok: 0,  err: 0 },
];
const storage = [
  { name: 'Audio (raw)',   hint: 'audio/*',  size: '2.84 GB', pct: 100 },
  { name: 'Transcripts',   hint: 'words[]',  size: '410 MB',  pct: 14 },
  { name: 'Slide exports', hint: 'png/pdf',  size: '280 MB',  pct: 10 },
  { name: 'Artifacts',     hint: 'docx/srt', size: '110 MB',  pct: 4 },
  { name: 'Audit + logs',  hint: 'jsonl',    size: '60 MB',   pct: 2 },
];
const coverage = [
  { name: 'Tina Pratt',     role: 'Editor',    load: 3, cap: 5 },
  { name: 'Heather Howell', role: 'Moderator', load: 2, cap: 6 },
  { name: 'Kelsey Lykins',  role: 'Medical',   load: 1, cap: 4 },
];
const typeChips = ['All types', 'ARAV', 'NAVAS'];

// ── Header derived values ─────────────────────────────────────────────
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
  toast.push('Claimed 1 unassigned session', { tone: 'success' });
}
</script>

<template>
  <main class="page dash-page" data-screen-label="Dashboard">
    <div class="dash-header">
      <div>
        <div class="dash-eyebrow">Today · {{ dateLabel }}</div>
        <h1 class="dash-title">{{ greeting }}, {{ userFirstName }}</h1>
        <p class="dash-lead">Dual-pipeline system · 23 SOP sessions · 19 AI sessions</p>
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

    <!-- Top KPI strip -->
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

    <!-- Your Queue -->
    <section class="dash-section">
      <div class="dash-section__head">
        <span class="dash-section__title">Your Queue</span>
        <span class="dash-section__sub">Assigned to you, ordered by due date</span>
        <RouterLink to="/sessions" class="dash-section__action">View all →</RouterLink>
      </div>
      <div class="dash-queue">
        <div v-for="q in queue" :key="q.code" class="dash-queue__card" @click="router.push('/e/se_001')">
          <div class="dash-queue__head">
            <div class="dash-queue__code">{{ q.code }}</div>
            <StageBadge :id="q.stage" />
          </div>
          <div class="dash-queue__title">{{ q.title }}</div>
          <div class="dash-queue__meta">
            <span>{{ q.segs }} segs</span><span>·</span>
            <span>Aligned</span><span>·</span>
            <span :style="{ color: 'var(--text-accent)', fontWeight: 700 }">{{ q.due }}</span>
          </div>
          <div class="dash-queue__foot">
            <span class="dash-queue__status">{{ q.status }}</span>
            <button class="btn btn--primary btn--sm">Open <Icon name="chevron-right" :size="11" /></button>
          </div>
        </div>
      </div>
    </section>

    <!-- Pipeline -->
    <section class="dash-section">
      <div class="dash-section__head">
        <span class="dash-section__title">Pipeline</span>
        <span class="dash-section__sub">23 sessions · 7 AI stages + 8 SOP stages</span>
        <div class="dash-section__filter">
          <button
            v-for="t in typeChips"
            :key="t"
            :class="['chip', { 'chip--solid': pipelineFilter === t }]"
            :style="{ cursor: 'pointer' }"
            @click="pipelineFilter = t"
          >{{ t }}</button>
          <button
            class="chip"
            :style="{ cursor: 'pointer', color: 'var(--fg2)' }"
            data-test-id="dash-types-more"
            @click="toast.push('Showing 5 more type filters: TTOPIC · VSPN · IVAPM · VVI · AFVF')"
          >+5</button>
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
          Pipeline 2 · SOP Control Layer · <code>sop_sessions.state</code> · 8 stages
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

    <!-- System overview -->
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

      <!-- SLA by stage -->
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
              <template v-if="s.dAvg != null"><strong>{{ s.dAvg }}</strong> <span>d avg</span></template>
              <strong v-else :style="{ color: 'var(--fg2)' }">—</strong>
            </div>
            <div class="dash-sla__bar">
              <span :style="{ width: s.dAvg ? `${Math.min(100, (s.dAvg / Math.max(s.target, 4)) * 100)}%` : '0%' }" />
            </div>
            <div class="dash-sla__foot">
              <span>{{ s.sess }} sess</span>
              <span>target {{ s.target }}d</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Three-column widget row -->
    <div class="dash-three">
      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">SOP Age Alerts</span>
          <span class="dash-section__sub">Oldest first</span>
          <a class="dash-section__action" href="#/sessions">All →</a>
        </div>
        <div class="dash-widget__body">
          <div v-for="(a, i) in ageAlerts" :key="i" class="dash-widget__row">
            <div :style="{ flex: 1, minWidth: 0 }">
              <div class="dash-widget__title">{{ a.title }}</div>
              <div class="dash-widget__sub">{{ a.stage }}</div>
            </div>
            <div class="dash-widget__age">{{ a.age }}</div>
          </div>
        </div>
      </div>

      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">Correction Hotspots</span>
          <span class="dash-section__sub">Top 5 edited</span>
          <a class="dash-section__action" href="#/sessions">All →</a>
        </div>
        <div class="dash-widget__body">
          <div v-for="(h, i) in hotspots" :key="i" class="dash-bar-row">
            <div class="dash-bar-row__top">
              <div class="dash-bar-row__title">{{ h.title }}</div>
              <div class="dash-bar-row__val">{{ h.edits }} edits</div>
            </div>
            <div class="dash-bar-row__bar"><span :style="{ width: `${h.pct}%` }" /></div>
          </div>
        </div>
      </div>

      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">Storage Top Sessions</span>
          <span class="dash-section__sub">By size</span>
          <a class="dash-section__action" href="#/sessions">All →</a>
        </div>
        <div class="dash-widget__body">
          <div v-for="(s, i) in storageTop" :key="i" class="dash-bar-row">
            <div class="dash-bar-row__top">
              <div class="dash-bar-row__title">{{ s.title }}</div>
              <div class="dash-bar-row__val">{{ s.size }}</div>
            </div>
            <div class="dash-bar-row__bar"><span :style="{ width: `${s.pct}%` }" /></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom widget row -->
    <div class="dash-three">
      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">Jobs Queue</span>
          <span class="dash-section__sub">Last 24h</span>
        </div>
        <div class="dash-widget__body">
          <div v-for="j in jobs" :key="j.name" class="dash-jobs-row">
            <span class="dash-jobs-row__name">{{ j.name }}</span>
            <span class="dash-jobs-row__ok">{{ j.ok }} ok</span>
            <span :class="['dash-jobs-row__err', { 'is-error': j.err > 0 }]">{{ j.err }} err</span>
          </div>
        </div>
      </div>

      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">Storage Breakdown</span>
        </div>
        <div class="dash-widget__body">
          <div v-for="s in storage" :key="s.name" class="dash-bar-row">
            <div class="dash-bar-row__top">
              <div class="dash-bar-row__title">
                {{ s.name }} <code :style="{ marginLeft: '4px', fontSize: '10.5px', color: 'var(--fg2)' }">{{ s.hint }}</code>
              </div>
              <div class="dash-bar-row__val">{{ s.size }}</div>
            </div>
            <div class="dash-bar-row__bar"><span :style="{ width: `${s.pct}%` }" /></div>
          </div>
        </div>
      </div>

      <div class="dash-widget">
        <div class="dash-widget__head">
          <span class="dash-section__title">Assignment Coverage</span>
        </div>
        <div class="dash-widget__body">
          <div v-for="c in coverage" :key="c.name" class="dash-coverage-row">
            <div :style="{ flex: 1, minWidth: 0 }">
              <div class="dash-coverage-row__name">{{ c.name }}</div>
              <div class="dash-coverage-row__role">{{ c.role }}</div>
            </div>
            <div class="dash-coverage-row__load">{{ c.load }}/{{ c.cap }}</div>
            <div class="dash-coverage-row__bar"><span :style="{ width: `${(c.load / c.cap) * 100}%` }" /></div>
          </div>
          <div class="dash-coverage-row dash-coverage-row--unassigned">
            <div :style="{ flex: 1 }">
              <div class="dash-coverage-row__name" :style="{ color: 'var(--text-accent)' }">Unassigned</div>
              <div class="dash-coverage-row__role">pool</div>
            </div>
            <div class="dash-coverage-row__load">17</div>
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
