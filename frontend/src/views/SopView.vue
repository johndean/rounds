<script setup lang="ts">
/**
 * SOP Workflow — /e/:id/sop
 * Faithful 1:1 port of docs/port-source/sop.jsx (381 LOC).
 */
import { computed, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import StageBadge from '@/components/shared/StageBadge.vue';
import { SESSIONS } from '@/fixtures/sessions';
import { SOP_STAGES } from '@/fixtures/sop_stages';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';

const props = defineProps<{ id: string }>();

const session = computed(() => SESSIONS.find(s => s.id === props.id) ?? SESSIONS[0]!);
const stages = SOP_STAGES;
const currentIdx = computed(() => stages.findIndex(s => s.id === session.value.stage));
const current = computed(() => stages[currentIdx.value]!);
const next = computed(() => stages[currentIdx.value + 1]);

// Per-stage assignment matrix
interface StageMeta { assignee: string; role: string; avatar: string; color: string }
const palette: StageMeta[] = [
  { assignee: 'system',           role: 'Auto-ingest',       avatar: 'SY', color: '#4D6995' },
  { assignee: 'Kate Schultz',     role: 'Copy Editor',       avatar: 'KS', color: '#0861CE' },
  { assignee: 'Dr. Mueller',      role: 'Medical Reviewer',  avatar: 'PM', color: '#C54644' },
  { assignee: 'Ruth Schoonover',  role: 'Copy Editor',       avatar: 'RS', color: '#B75D04' },
  { assignee: 'Content Team',     role: 'CMS Owner',         avatar: 'CT', color: '#0097A9' },
  { assignee: 'Content Team',     role: 'Captions',          avatar: 'CT', color: '#B9975B' },
  { assignee: 'QA Group',         role: 'QA',                avatar: 'QA', color: '#007D61' },
  { assignee: '—',                role: '—',                 avatar: '—',  color: '#002855' },
];
const stageMeta = computed<Record<string, StageMeta>>(() => {
  const out: Record<string, StageMeta> = {};
  stages.forEach((s, i) => { out[s.id] = palette[i] || palette[palette.length - 1]!; });
  return out;
});

interface CheckState { label: string; state: 'pass' | 'fail' | 'pending'; meta: string; actor: string }
const checkStates = computed<CheckState[]>(() =>
  current.value.checks.map((label, i): CheckState => {
    const state: 'pass' | 'fail' = i < current.value.checks.length - 1 ? 'pass' : 'fail';
    return {
      label,
      state,
      meta: state === 'pass' ? 'verified · 12 min ago' : 'blocked · awaiting reviewer attestation',
      actor: state === 'pass' ? 'Kate Schultz' : '—',
    };
  }),
);

const selectedStage = ref<string>(current.value.id);
const view = computed(() => stages.find(s => s.id === selectedStage.value)!);
const viewIdx = computed(() => stages.findIndex(s => s.id === selectedStage.value));
const viewIsCurrent = computed(() => view.value.id === current.value.id);
const viewIsDone    = computed(() => viewIdx.value < currentIdx.value);
const viewIsPending = computed(() => viewIdx.value > currentIdx.value);
const viewMeta = computed(() => stageMeta.value[view.value.id]!);
const viewChecks = computed<CheckState[]>(() => {
  if (viewIsCurrent.value) return checkStates.value;
  if (viewIsDone.value) {
    return view.value.checks.map(l => ({ label: l, state: 'pass', meta: 'verified · stage closed', actor: stageMeta.value[view.value.id]?.assignee || '—' }));
  }
  return view.value.checks.map(l => ({ label: l, state: 'pending', meta: 'queued · prior stage not complete', actor: '—' }));
});

const canAdvance = computed(() => checkStates.value.every(c => c.state === 'pass'));

interface Transition { from: string; to: string; at: string; actor: string; actorRole: string; actorColor: string; actorAvatar: string; note: string }
const transitions = computed<Transition[]>(() => {
  const out: Transition[] = [];
  for (let i = 0; i < currentIdx.value; i++) {
    const from = stages[i]!.id;
    const to = stages[i + 1]!.id;
    const day = 14 - currentIdx.value + i + 1;
    const hr = 7 + i * 2;
    out.push({
      from, to,
      at: `2026-05-${String(day).padStart(2, '0')}T${String(hr).padStart(2, '0')}:01:00Z`,
      actor: stageMeta.value[to]!.assignee,
      actorRole: stageMeta.value[to]!.role,
      actorColor: stageMeta.value[to]!.color,
      actorAvatar: stageMeta.value[to]!.avatar,
      note: i === 0 ? 'Auto-advanced — ingest pipeline reported READY.' :
            i === 1 ? 'Draft copy edit pass complete.' :
            i === 2 ? 'Medical review attestation signed.' :
            'Stage advanced.',
    });
  }
  return out;
});

const currentSince = computed(() => transitions.value.length ? transitions.value[transitions.value.length - 1]!.at : '2026-05-14T07:42:00Z');
const currentSinceDate = computed(() => new Date(currentSince.value));
const dwellHours = computed(() => Math.max(1, Math.floor((Date.now() - currentSinceDate.value.getTime()) / (1000 * 60 * 60)) % 96));

const approvers = computed(() =>
  stages.slice(0, currentIdx.value).map(s => ({
    stage: s,
    by: stageMeta.value[s.id]!.assignee,
    role: stageMeta.value[s.id]!.role,
    avatar: stageMeta.value[s.id]!.avatar,
    color: stageMeta.value[s.id]!.color,
    at: transitions.value.find(t => t.from === s.id)?.at ?? '',
  })),
);

const completionPct = computed(() => Math.round((currentIdx.value / stages.length) * 100));
const blockers = computed(() => checkStates.value.filter(c => c.state !== 'pass').length);

function resolveCheck(label: string): void { toast.push(`Resolve "${label.slice(0, 40)}…" (mock)`); }
async function advance(): Promise<void> {
  if (!next.value) return;
  const ok = await confirm.open({
    title: `Advance to ${next.value.name}?`,
    body: `This is an append-only transition for ${session.value.title}.`,
    confirmLabel: `Advance to ${next.value.name}`,
  });
  if (ok) {
    toast.push(`Advanced to ${next.value.name}`, { tone: 'success' });
    selectedStage.value = next.value.id;
  }
}
function reassign(name: string): void { toast.push(`Reassign ${name} — picker (mock)`); }
function ping(name: string): void { toast.push(`Pinged ${name} on Slack (mock)`); }

function fmtIso(iso: string): string { return new Date(iso).toISOString().slice(0, 16).replace('T', ' '); }
function fmtLocal(iso: string): string {
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: false });
}
</script>

<template>
  <main class="page" data-screen-label="SOP Workflow">
    <div class="page-eyebrow">
      <RouterLink to="/sessions">Sessions</RouterLink><span class="sep">/</span>
      <RouterLink :to="`/s/${session.id}`">{{ session.code || session.id }}</RouterLink><span class="sep">/</span>
      <span>SOP Workflow</span>
    </div>

    <!-- Session identity header -->
    <div class="sop-header">
      <div class="sop-header__left">
        <div class="sop-header__code">{{ session.code || session.id }}</div>
        <h1 class="sop-header__title">{{ session.title }}</h1>
        <div class="sop-header__meta">
          <span><strong>{{ session.presenter }}</strong></span>
          <span class="sep">·</span>
          <span>Recorded {{ session.recorded }}</span>
          <span class="sep">·</span>
          <span>{{ session.duration }}</span>
          <span class="sep">·</span>
          <span>{{ (session.segs || 0).toLocaleString() }} segments · {{ (session.words || 0).toLocaleString() }} words</span>
          <span class="sep">·</span>
          <span>{{ (session.attendees || 0).toLocaleString() }} attendees</span>
        </div>
      </div>
      <div class="sop-header__right">
        <RouterLink :to="`/e/${session.id}`" class="btn btn--secondary"><Icon name="chevron-left" /> Back to editor</RouterLink>
        <RouterLink :to="`/v/${session.id}`" class="btn btn--ghost"><Icon name="external" /> Viewer</RouterLink>
      </div>
    </div>

    <!-- Workflow KPI strip -->
    <div class="sop-kpis">
      <div class="sop-kpi">
        <div class="sop-kpi__label">Current Stage</div>
        <div class="sop-kpi__value"><StageBadge :id="current.id" /></div>
        <div class="sop-kpi__sub">Stage {{ current.order }} of {{ stages.length }}</div>
      </div>
      <div class="sop-kpi">
        <div class="sop-kpi__label">Assigned to</div>
        <div class="sop-kpi__value sop-kpi__value--avatar">
          <span class="sop-avatar" :style="{ background: stageMeta[current.id]!.color }">{{ stageMeta[current.id]!.avatar }}</span>
          <span :style="{ fontWeight: 700, color: 'var(--fg1)' }">{{ stageMeta[current.id]!.assignee }}</span>
        </div>
        <div class="sop-kpi__sub">{{ stageMeta[current.id]!.role }}</div>
      </div>
      <div class="sop-kpi">
        <div class="sop-kpi__label">Dwell in stage</div>
        <div class="sop-kpi__value" :style="{ color: dwellHours > 48 ? 'var(--color-amber)' : 'var(--fg1)' }">{{ dwellHours }}h</div>
        <div class="sop-kpi__sub">since {{ currentSinceDate.toISOString().slice(0, 16).replace('T', ' ') }}</div>
      </div>
      <div class="sop-kpi">
        <div class="sop-kpi__label">Acceptance checks</div>
        <div class="sop-kpi__value">{{ checkStates.filter(c => c.state === 'pass').length }}<span :style="{ color: 'var(--fg2)', fontWeight: 500, fontSize: '18px' }">/{{ checkStates.length }}</span></div>
        <div class="sop-kpi__sub" :style="{ color: blockers ? 'var(--color-amber)' : 'var(--color-green)' }">
          {{ blockers ? `${blockers} blocker${blockers === 1 ? '' : 's'}` : 'all passing' }}
        </div>
      </div>
      <div class="sop-kpi">
        <div class="sop-kpi__label">Pipeline progress</div>
        <div class="sop-kpi__value">{{ completionPct }}%</div>
        <div class="sop-kpi__progress"><span :style="{ width: `${completionPct}%` }" /></div>
      </div>
    </div>

    <!-- 8-stage stepper -->
    <div class="sop-stepper" role="list">
      <button
        v-for="(s, i) in stages"
        :key="s.id"
        :class="['sop-step', {
          'is-current': s.id === current.id,
          'is-done': i < currentIdx,
          'is-pending': i > currentIdx,
          'is-selected': s.id === selectedStage && s.id !== current.id,
        }]"
        role="listitem"
        @click="selectedStage = s.id"
      >
        <div class="sop-step__n">
          <Icon v-if="i < currentIdx" name="check" :size="11" />
          <template v-else>{{ s.order }}</template>
        </div>
        <div class="sop-step__name">{{ s.name }}</div>
        <div class="sop-step__meta">{{ s.id === current.id ? 'current' : i < currentIdx ? 'complete' : 'pending' }}</div>
        <div class="sop-step__owner" :title="`${stageMeta[s.id]!.assignee} · ${stageMeta[s.id]!.role}`">
          <span class="sop-avatar sop-avatar--sm" :style="{ background: stageMeta[s.id]!.color, opacity: i > currentIdx ? 0.4 : 1 }">
            {{ stageMeta[s.id]!.avatar }}
          </span>
          <span :style="{ fontSize: '10.5px', color: i > currentIdx ? 'var(--fg2)' : 'var(--fg1)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }">
            {{ stageMeta[s.id]!.assignee }}
          </span>
        </div>
      </button>
    </div>

    <!-- Main detail grid -->
    <div class="sop-detail-grid">
      <div class="sop-check-card">
        <div class="sop-check-card__head">
          <div>
            <div :style="{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }">
              <h3 :style="{ margin: 0 }">Stage {{ view.order }} · {{ view.name }}</h3>
              <span v-if="viewIsCurrent" class="chip chip--blue" :style="{ fontSize: '10px' }">CURRENT</span>
              <span v-if="viewIsDone" class="chip chip--green" :style="{ fontSize: '10px' }">COMPLETE</span>
              <span v-if="viewIsPending" class="chip chip--ghost" :style="{ fontSize: '10px' }">PENDING</span>
            </div>
            <div class="sub">
              <template v-if="viewIsCurrent">Acceptance checks gate advancement to the next stage. All must pass.</template>
              <template v-else-if="viewIsDone">Stage closed. Acceptance checks were verified at transition time.</template>
              <template v-else>Stage pending. Will become active once the prior stage advances.</template>
            </div>
          </div>
          <div :style="{ display: 'flex', gap: '6px' }">
            <button class="btn btn--ghost btn--sm" :disabled="viewIdx === 0" @click="selectedStage = stages[Math.max(0, viewIdx - 1)]!.id">
              <Icon name="chevron-left" /> Prev
            </button>
            <button class="btn btn--ghost btn--sm" :disabled="viewIdx === stages.length - 1" @click="selectedStage = stages[Math.min(stages.length - 1, viewIdx + 1)]!.id">
              Next <Icon name="chevron-right" />
            </button>
          </div>
        </div>

        <div v-for="(c, i) in viewChecks" :key="i" :class="['sop-check', `is-${c.state}`]">
          <div class="sop-check__icon">
            <Icon v-if="c.state === 'pass'" name="check" :size="12" />
            <Icon v-else-if="c.state === 'fail'" name="x" :size="12" />
            <Icon v-else name="circle-dot" :size="10" />
          </div>
          <div>
            <div class="sop-check__name">{{ c.label }}</div>
            <div class="sop-check__meta">
              {{ c.meta }}
              <span v-if="c.actor && c.actor !== '—' && c.state === 'pass'"> · by <strong :style="{ color: 'var(--fg1)' }">{{ c.actor }}</strong></span>
            </div>
          </div>
          <div>
            <button
              v-if="c.state === 'fail'"
              class="btn btn--secondary btn--sm"
              :data-test-id="`sop-resolve-${c.label.slice(0, 20)}`"
              @click="resolveCheck(c.label)"
            >Resolve</button>
            <span v-else-if="c.state === 'pass'" class="chip chip--green"><Icon name="check" :size="10" /> pass</span>
            <span v-else class="chip chip--ghost"><span class="chip__dot" /> pending</span>
          </div>
        </div>

        <div v-if="viewIsCurrent" :class="['sop-advance-row', canAdvance ? 'is-ready' : 'is-blocked']">
          <div>
            <div :style="{ fontWeight: 700, color: 'var(--fg1)', fontSize: '13px' }">
              {{ canAdvance ? 'Ready to advance' : 'Cannot advance' }}
            </div>
            <div :style="{ fontSize: '12px', color: 'var(--fg2)', marginTop: '2px' }">
              {{ canAdvance ? `All ${checkStates.length} checks pass. Advance to ${next?.name || '—'}.` : `${blockers} check(s) blocking advancement to ${next?.name || '—'}.` }}
            </div>
          </div>
          <button class="btn btn--primary" :disabled="!canAdvance" data-test-id="sop-advance" @click="advance">
            <Icon name="chevron-right" :size="12" /> Advance to {{ next?.name || '—' }}
          </button>
        </div>
      </div>

      <!-- Side rail -->
      <div class="sop-side">
        <div class="card sop-owner-card">
          <div class="card__header"><h3>Stage owner</h3></div>
          <div class="card__body">
            <div class="sop-owner">
              <span class="sop-avatar sop-avatar--lg" :style="{ background: viewMeta.color }">{{ viewMeta.avatar }}</span>
              <div>
                <div :style="{ fontWeight: 700, fontSize: '14px', color: 'var(--fg1)' }">{{ viewMeta.assignee }}</div>
                <div :style="{ fontSize: '12px', color: 'var(--fg2)', marginTop: '2px' }">{{ viewMeta.role }}</div>
              </div>
            </div>
            <div class="sop-owner-actions">
              <button class="btn btn--secondary btn--sm" @click="reassign(view.name)"><Icon name="edit" /> Reassign</button>
              <button class="btn btn--ghost btn--sm" @click="ping(viewMeta.assignee)"><Icon name="message" /> Ping</button>
            </div>
            <div class="sop-owner-meta">
              <div><span class="sop-lbl">Notify on entry</span><span :style="{ color: 'var(--color-green)', fontWeight: 700 }">ON</span></div>
              <div><span class="sop-lbl">SLA target</span><span>2 days</span></div>
              <div><span class="sop-lbl">Status</span><span>{{ viewIsCurrent ? 'Awaiting attestation' : viewIsDone ? 'Signed off' : 'Queued' }}</span></div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card__header">
            <h3>Approvals</h3>
            <span class="chip chip--ghost" :style="{ fontSize: '10px' }">{{ approvers.length }} of {{ stages.length - 1 }}</span>
          </div>
          <div class="card__body" :style="{ padding: 0 }">
            <div v-if="approvers.length === 0" :style="{ padding: '16px', fontSize: '12px', color: 'var(--fg2)', textAlign: 'center' }">No approvals yet.</div>
            <div v-for="(a, i) in approvers" :key="i" class="sop-approval">
              <span class="sop-avatar sop-avatar--sm" :style="{ background: a.color }">{{ a.avatar }}</span>
              <div :style="{ flex: 1, minWidth: 0 }">
                <div :style="{ fontSize: '12.5px', fontWeight: 600, color: 'var(--fg1)' }">{{ a.by }}</div>
                <div :style="{ fontSize: '10.5px', color: 'var(--fg2)' }">{{ a.stage.name }} · {{ fmtLocal(a.at) }}</div>
              </div>
              <Icon name="check" :size="14" class="sop-approval__check" />
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card__header"><h3>Quick actions</h3></div>
          <div class="card__body" :style="{ display: 'grid', gap: '6px' }">
            <RouterLink :to="`/e/${session.id}`" class="btn btn--secondary btn--sm"><Icon name="edit" /> Open editor</RouterLink>
            <RouterLink :to="`/e/${session.id}/audit`" class="btn btn--secondary btn--sm"><Icon name="history" /> Full audit ledger</RouterLink>
            <button class="btn btn--ghost btn--sm" @click="toast.push('Override modal (mock)')"><Icon name="alert" /> Override with reason</button>
            <button class="btn btn--ghost btn--sm" @click="toast.push('Stage notes (mock)')"><Icon name="doc" /> Stage notes</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Transition history + Invariants -->
    <div :style="{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '18px' }">
      <div class="card">
        <div class="card__header">
          <h3>Stage Transition History</h3>
          <span class="chip chip--ghost" :style="{ fontSize: '10px' }">{{ transitions.length }} transitions</span>
        </div>
        <div class="card__body" :style="{ padding: 0 }">
          <div v-for="(t, i) in transitions" :key="i" class="sop-transition">
            <span class="sop-transition__t">{{ fmtIso(t.at) }}</span>
            <div class="sop-transition__main">
              <div :style="{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }">
                <StageBadge :id="t.from" />
                <Icon name="chevron-right" :size="12" />
                <StageBadge :id="t.to" />
              </div>
              <div :style="{ fontSize: '12px', color: 'var(--fg2)', marginTop: '4px' }">{{ t.note }}</div>
            </div>
            <div class="sop-transition__actor">
              <span class="sop-avatar sop-avatar--sm" :style="{ background: t.actorColor }">{{ t.actorAvatar }}</span>
              <div>
                <div :style="{ fontSize: '12px', fontWeight: 600, color: 'var(--fg1)' }">{{ t.actor }}</div>
                <div :style="{ fontSize: '10px', color: 'var(--fg2)' }">{{ t.actorRole }}</div>
              </div>
            </div>
          </div>
          <div :style="{ padding: '12px 16px', color: 'var(--fg2)', fontSize: '12px', fontStyle: 'italic' }">
            — current state (<strong>{{ current.name }}</strong>) since {{ fmtIso(currentSince) }} · assigned to <strong>{{ stageMeta[current.id]!.assignee }}</strong> —
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card__header"><h3>SOP Invariants</h3></div>
        <div class="card__body" :style="{ fontSize: '12px', color: 'var(--fg2)', lineHeight: 1.65 }">
          <div class="sop-invariant">
            <span class="chip chip--green"><Icon name="check" :size="10" /> L5</span>
            <span><strong :style="{ color: 'var(--fg1)' }">No stage skipping.</strong> Transitions are deterministic and replayable. Verified by workflow replay harness.</span>
          </div>
          <div class="sop-invariant">
            <span class="chip chip--green"><Icon name="check" :size="10" /> §18.14</span>
            <span><strong :style="{ color: 'var(--fg1)' }">Append-only audit trail.</strong> Each transition writes a row; the row is never mutated.</span>
          </div>
          <div class="sop-invariant">
            <span class="chip chip--green"><Icon name="check" :size="10" /> §15.6</span>
            <span><strong :style="{ color: 'var(--fg1)' }">8-stage parity.</strong> Stages, gates, and acceptance checks ported byte-for-byte from v3.12.</span>
          </div>
          <div class="sop-invariant">
            <span class="chip chip--blue"><Icon name="circle-dot" :size="10" /> ADR</span>
            <span><strong :style="{ color: 'var(--fg1)' }">Per-stage override.</strong> Override with reason is queued in <RouterLink to="/improvements">Improvement Request i5</RouterLink>.</span>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>
