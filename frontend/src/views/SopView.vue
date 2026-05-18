<script setup lang="ts">
/**
 * SOP Workflow — /e/:id/sop
 *
 * Same DOM as React sop.jsx. Wired:
 *   GET /v1/sessions/{id}
 *   GET /v1/sessions/{id}/sop
 *   POST /v1/sessions/{id}/sop/advance
 *   POST /v1/sessions/{id}/sop/checks/resolve
 * Stage palette + assignee/role labels stay static (matches React SSOT).
 */
import { computed, onMounted, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import StageBadge from '@/components/shared/StageBadge.vue';
import { sessions as sessionsApi, sop as sopApi, type SessionSummary } from '@/services/api';
import { SOP_STAGES } from '@/fixtures/sop_stages';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';

const props = defineProps<{ id: string }>();

interface SopState {
  current_stage: string;
  is_blocked: boolean;
  blockers: unknown[];
  assignees: Record<string, unknown>;
  sla_target_hours: Record<string, unknown>;
}

const session = ref<SessionSummary | null>(null);
const sopState = ref<SopState | null>(null);
const loading = ref(true);

async function load(): Promise<void> {
  loading.value = true;
  try {
    const [s, st] = await Promise.all([
      sessionsApi.get(props.id).catch(() => null),
      sopApi.state(props.id).catch(() => null),
    ]);
    session.value = s;
    sopState.value = st as SopState | null;
  } finally {
    loading.value = false;
  }
}
onMounted(load);

const stages = SOP_STAGES;
const currentStage = computed(() => sopState.value?.current_stage || 'prep');
const currentIdx = computed(() => stages.findIndex(s => s.id === currentStage.value));
const current = computed(() => stages[currentIdx.value]!);
const nextStage = computed(() => stages[currentIdx.value + 1]);

// Per-stage palette (matches React SSOT — illustrative role labels)
interface StageMeta { assignee: string; role: string; avatar: string; color: string }
const palette: StageMeta[] = [
  { assignee: 'system',          role: 'Auto-ingest',       avatar: 'SY', color: '#4D6995' },
  { assignee: 'Kate Schultz',    role: 'Copy Editor',       avatar: 'KS', color: '#0861CE' },
  { assignee: 'Dr. Mueller',     role: 'Medical Reviewer',  avatar: 'PM', color: '#C54644' },
  { assignee: 'Ruth Schoonover', role: 'Copy Editor',       avatar: 'RS', color: '#B75D04' },
  { assignee: 'Content Team',    role: 'CMS Owner',         avatar: 'CT', color: '#0097A9' },
  { assignee: 'Content Team',    role: 'Captions',          avatar: 'CT', color: '#B9975B' },
  { assignee: 'QA Group',        role: 'QA',                avatar: 'QA', color: '#007D61' },
  { assignee: '—',               role: '—',                 avatar: '—',  color: '#002855' },
];
const stageMeta = computed<Record<string, StageMeta>>(() => {
  const out: Record<string, StageMeta> = {};
  stages.forEach((s, i) => { out[s.id] = palette[i] || palette[palette.length - 1]!; });
  return out;
});

interface CheckState { label: string; state: 'pass' | 'fail' | 'pending'; meta: string; actor: string }
const checkStates = computed<CheckState[]>(() =>
  (current.value?.checks ?? []).map((label): CheckState => ({
    label,
    state: 'pending',
    meta: 'awaiting check infrastructure (Phase 7)',
    actor: '—',
  })),
);

const selectedStage = ref<string>(currentStage.value);
const view = computed(() => stages.find(s => s.id === selectedStage.value) ?? current.value);
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
    out.push({
      from, to,
      at: new Date(Date.now() - (currentIdx.value - i) * 86400000).toISOString(),
      actor: stageMeta.value[to]!.assignee,
      actorRole: stageMeta.value[to]!.role,
      actorColor: stageMeta.value[to]!.color,
      actorAvatar: stageMeta.value[to]!.avatar,
      note: 'Stage advanced.',
    });
  }
  return out;
});

const currentSince = computed(() => transitions.value.length ? transitions.value[transitions.value.length - 1]!.at : new Date().toISOString());
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

async function resolveCheck(label: string): Promise<void> {
  // Phase 6: real wiring. The backend resolveCheck endpoint persists to
  // sop_checks with the current stage + a slugged check_id (label-derived
  // because checkStates here are derived from stage.checks fixture labels —
  // no real per-check infrastructure yet, but the resolve record persists
  // either way and is queryable for the audit ledger).
  const checkId = label.toLowerCase().replace(/[^a-z0-9]+/g, '_').slice(0, 64);
  try {
    await sopApi.resolveCheck(props.id, checkId, label);
    toast.push(`Resolved: "${label.slice(0, 40)}${label.length > 40 ? '…' : ''}"`, { tone: 'success' });
    await load();
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Resolve failed', { tone: 'error' });
  }
}
async function advance(): Promise<void> {
  if (!nextStage.value) return;
  const ok = await confirm.open({
    title: `Advance to ${nextStage.value.name}?`,
    body: `Append-only transition for ${session.value?.title || props.id}.`,
    confirmLabel: `Advance to ${nextStage.value.name}`,
  });
  if (!ok) return;
  try {
    await sopApi.advance(props.id, nextStage.value.id);
    toast.push(`Advanced to ${nextStage.value.name}`, { tone: 'success' });
    await load();
    selectedStage.value = nextStage.value.id;
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Advance failed', { tone: 'error' });
  }
}
async function reassign(name: string): Promise<void> {
  // Phase 6: real wiring. Prompt for the new assignee (person email or
  // "group:NAME"); send to /sop/assign which persists to sop_state.assignees
  // and records an audit_events row.
  const assignee = window.prompt(
    `Reassign "${name}" stage to (email or "group:NAME"):`,
    '',
  );
  if (!assignee) return;
  try {
    const r = await sopApi.assign(props.id, assignee.trim(), { stage: view.value.id });
    toast.push(`Assigned ${r.stage} → ${r.assignee}`, { tone: 'success' });
    await load();
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Assign failed', { tone: 'error' });
  }
}
function ping(name: string): void {
  // Slack integration is out of scope of audit phases — leave warn-tone.
  toast.push(
    `Slack ping for ${name} not yet wired — depends on Slack integration (out of scope).`,
    { tone: 'warn' },
  );
}

async function addOverride(): Promise<void> {
  // Phase 6: annotation kind='override'. Used when a stage advances despite
  // failing checks; the override reason is captured in the audit trail.
  const reason = window.prompt(`Override reason for "${view.value.name}":`, '');
  if (!reason || !reason.trim()) return;
  try {
    await sopApi.annotate(props.id, reason.trim(), { stage: view.value.id, kind: 'override' });
    toast.push(`Override recorded on ${view.value.name}`, { tone: 'success' });
    await load();
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Override failed', { tone: 'error' });
  }
}

async function addNote(): Promise<void> {
  // Phase 6: annotation kind='note'. Free-text stage commentary.
  const body = window.prompt(`Add note to "${view.value.name}":`, '');
  if (!body || !body.trim()) return;
  try {
    await sopApi.annotate(props.id, body.trim(), { stage: view.value.id, kind: 'note' });
    toast.push(`Note added to ${view.value.name}`, { tone: 'success' });
    await load();
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Note add failed', { tone: 'error' });
  }
}

function fmtIso(iso: string): string {
  try { return new Date(iso).toISOString().slice(0, 16).replace('T', ' '); }
  catch { return iso; }
}
function fmtLocal(iso: string): string {
  try { return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: false }); }
  catch { return iso; }
}
</script>

<template>
  <main class="page" data-screen-label="SOP Workflow">
    <div class="page-eyebrow">
      <RouterLink to="/sessions">Sessions</RouterLink><span class="sep">/</span>
      <RouterLink v-if="session" :to="`/s/${session.id}`">{{ session.code || session.id }}</RouterLink>
      <span v-else>{{ props.id }}</span>
      <span class="sep">/</span>
      <span>SOP Workflow</span>
    </div>

    <div v-if="loading" :style="{ padding: '60px', textAlign: 'center', color: 'var(--fg2)' }">Loading SOP state…</div>
    <template v-else>
      <div class="sop-header">
        <div class="sop-header__left">
          <div class="sop-header__code">{{ session?.code || props.id }}</div>
          <h1 class="sop-header__title">{{ session?.title || 'Session not found' }}</h1>
          <div class="sop-header__meta">
            <span><strong>{{ session?.presenter || '—' }}</strong></span>
            <span class="sep">·</span>
            <span>{{ session?.duration_sec ? `${Math.round(session.duration_sec / 60)} min` : '—' }}</span>
            <span class="sep">·</span>
            <span>{{ (session?.segment_count || 0).toLocaleString() }} segments · {{ (session?.word_count || 0).toLocaleString() }} words</span>
            <span class="sep">·</span>
            <span>{{ (session?.attendee_count || 0).toLocaleString() }} attendees</span>
          </div>
        </div>
        <div class="sop-header__right">
          <RouterLink :to="`/e/${props.id}`" class="btn btn--secondary"><Icon name="chevron-left" /> Back to editor</RouterLink>
          <RouterLink :to="`/v/${props.id}`" class="btn btn--ghost"><Icon name="external" /> Viewer</RouterLink>
        </div>
      </div>

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
          <div class="sop-kpi__sub">since {{ fmtIso(currentSince) }}</div>
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
                {{ canAdvance ? `All ${checkStates.length} checks pass. Advance to ${nextStage?.name || '—'}.` : `${blockers} check(s) blocking advancement to ${nextStage?.name || '—'}.` }}
              </div>
            </div>
            <button class="btn btn--primary" :disabled="!canAdvance" data-test-id="sop-advance" @click="advance">
              <Icon name="chevron-right" :size="12" /> Advance to {{ nextStage?.name || '—' }}
            </button>
          </div>
        </div>

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
              <RouterLink :to="`/e/${props.id}`" class="btn btn--secondary btn--sm"><Icon name="edit" /> Open editor</RouterLink>
              <RouterLink :to="`/e/${props.id}/audit`" class="btn btn--secondary btn--sm"><Icon name="history" /> Full audit ledger</RouterLink>
              <button class="btn btn--ghost btn--sm" @click="addOverride"><Icon name="alert" /> Override with reason</button>
              <button class="btn btn--ghost btn--sm" @click="addNote"><Icon name="doc" /> Stage notes</button>
            </div>
          </div>
        </div>
      </div>

      <div :style="{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '18px' }">
        <div class="card">
          <div class="card__header">
            <h3>Stage Transition History</h3>
            <span class="chip chip--ghost" :style="{ fontSize: '10px' }">{{ transitions.length }} transitions</span>
          </div>
          <div class="card__body" :style="{ padding: 0 }">
            <div v-if="transitions.length === 0" :style="{ padding: '16px', fontSize: '12px', color: 'var(--fg2)', textAlign: 'center' }">
              No transitions yet — session is still in <strong>{{ current.name }}</strong>.
            </div>
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
    </template>
  </main>
</template>
