<script setup lang="ts">
/**
 * Audit / Word Track Changes — /audit and /e/:id/audit
 *
 * Two modes:
 *   • Per-session (props.id present, routed via EditorAuditView wrapper):
 *     reads correction_ledger via GET /v1/audit/sessions/{id}/corrections.
 *     Shows user-edit history (text_edit, slide_reassignment, etc).
 *   • Global (no props.id): reads audit_events via GET /v1/audit. Shows
 *     system-wide activity (sop.deadline_warning, settings.*, improvement.*,
 *     etc). audit_events rows are adapted to Correction shape so the same
 *     AuditLedger component renders both feeds.
 *
 * Same DOM as React audit.jsx::AuditRoute (340-420).
 */
import { computed, onMounted, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import AuditLedger from '@/components/audit/AuditLedger.vue';
import { audit as auditApi, sessions as sessionsApi, type SessionSummary } from '@/services/api';
import { toast } from '@/composables/useToast';

const props = defineProps<{ id?: string }>();

interface Correction {
  id: string;
  t: string;
  seg: string;
  type: string;
  actor: string;
  prior?: string | null;
  next?: string | null;
  note?: string | null;
}

// audit_events shape returned by GET /v1/audit
interface AuditEvent {
  id: string;
  session_id: string | null;
  actor_email: string;
  kind: string;
  summary: string;
  details: unknown;
  occurred_at: string;
}

const globalMode = computed(() => !props.id);

const session = ref<SessionSummary | null>(null);
const corrections = ref<Correction[]>([]);
const loading = ref(true);

async function load(): Promise<void> {
  loading.value = true;
  try {
    if (props.id) {
      // Per-session: read correction_ledger via /v1/audit/sessions/{id}/corrections
      const [s, c] = await Promise.all([
        sessionsApi.get(props.id).catch(() => null),
        auditApi.corrections(props.id).catch(() => []),
      ]);
      session.value = s;
      corrections.value = c as Correction[];
    } else {
      // Global: read audit_events via /v1/audit (limit raised so SOP deadline
      // rows + settings/improvement activity all fit a typical 24h window)
      const list = await auditApi.list({ limit: 500 }).catch(() => []);
      // Adapt audit_events → Correction shape so AuditLedger renders unchanged.
      // The `seg` slot doubles as the session_id prefix in global mode (8 chars
      // is enough for visual grouping; full id surfaces on hover via title).
      corrections.value = (list as AuditEvent[]).map((e): Correction => ({
        id:    e.id,
        t:     e.occurred_at,
        seg:   e.session_id ? e.session_id.slice(0, 8) : '—',
        type:  e.kind,
        actor: e.actor_email || 'system',
        prior: null,
        next:  null,
        note:  e.summary,
      }));
    }
  } finally {
    loading.value = false;
  }
}
onMounted(load);

const filter = ref<string>('all');

const stats = computed(() => {
  const out: Record<string, number> = {};
  corrections.value.forEach(c => { out[c.type] = (out[c.type] ?? 0) + 1; });
  return out;
});

// Per-session filter chips are the fixed correction-type set.
// Global mode chips are derived from whatever kinds are actually in the data
// (which can include sop.*, settings.*, improvement.*, align.*, etc).
const types = computed<Array<{ id: string; label: string }>>(() => {
  if (props.id) {
    return [
      { id: 'all',                  label: 'All types' },
      { id: 'text_edit',            label: 'text_edit' },
      { id: 'chat_insert',          label: 'chat_insert' },
      { id: 'chat_edit',            label: 'chat_edit' },
      { id: 'poll_insert',          label: 'poll_insert' },
      { id: 'slide_reassignment',   label: 'slide_reassignment' },
      { id: 'speaker_reassignment', label: 'speaker_reassignment' },
      { id: 'mark_reviewed',        label: 'mark_reviewed' },
      { id: 'annotation_add',       label: 'annotation_add' },
    ];
  }
  const kinds = new Set<string>();
  corrections.value.forEach((c) => kinds.add(c.type));
  return [
    { id: 'all', label: 'All kinds' },
    ...Array.from(kinds).sort().map((k) => ({ id: k, label: k })),
  ];
});

const allTypes = ['text_edit','chat_insert','chat_edit','chat_remove','poll_insert','poll_remove','slide_reassignment','speaker_reassignment','mark_reviewed','unmark_reviewed','annotation_add','annotation_remove'];

const distinctActors = computed(() => new Set(corrections.value.map(c => c.actor)).size);
const distinctKinds = computed(() => new Set(corrections.value.map(c => c.type)).size);

function exportJsonl(): void {
  const ndjson = corrections.value.map(c => JSON.stringify(c)).join('\n') + '\n';
  const blob = new Blob([ndjson], { type: 'application/x-ndjson' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = globalMode.value ? 'audit-events.jsonl' : 'audit.jsonl';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  toast.push(globalMode.value ? 'Audit events JSONL exported' : 'Audit JSONL exported', { tone: 'success' });
}
</script>

<template>
  <main class="page" data-screen-label="Audit / Word Track Changes">
    <div class="page-eyebrow">
      <RouterLink to="/sessions">Sessions</RouterLink><span class="sep">/</span>
      <template v-if="session">
        <RouterLink :to="`/e/${session.id}`">{{ session.code || session.id }}</RouterLink><span class="sep">/</span>
      </template>
      <span v-if="globalMode">System audit · audit_events</span>
      <span v-else>Audit · Word Track Changes (v7)</span>
    </div>
    <h1 class="page-title">{{ globalMode ? 'System Audit Log' : 'Word Track Changes' }}</h1>
    <p class="page-desc">
      <template v-if="globalMode">
        System-wide activity feed — SOP transitions + deadline warnings, settings changes, improvements, alignment gates, and other audit_events kinds.
        Append-only · filter by kind · drill into a session via the seg column.
      </template>
      <template v-else>
        Every correction is a row. Lineage is append-only — no destructive edits at rest.
        Filter by type, replay from any point, jump to the segment in the editor.
      </template>
    </p>
    <div class="kpi-row">
      <div class="kpi">
        <div class="kpi__label">{{ globalMode ? 'Total Events' : 'Total Corrections' }}</div>
        <div class="kpi__value">{{ corrections.length }}</div>
      </div>
      <template v-if="globalMode">
        <div class="kpi">
          <div class="kpi__label">Distinct Kinds</div>
          <div class="kpi__value">{{ distinctKinds }}</div>
        </div>
        <div class="kpi">
          <div class="kpi__label">SOP Deadline Warnings</div>
          <div class="kpi__value" :style="{ color: 'var(--color-red)' }">{{ stats['sop.deadline_warning'] || 0 }}</div>
          <div class="kpi__delta">overdue stage notices</div>
        </div>
        <div class="kpi">
          <div class="kpi__label">Distinct Actors</div>
          <div class="kpi__value">{{ distinctActors }}</div>
        </div>
      </template>
      <template v-else>
        <div class="kpi">
          <div class="kpi__label">Text Edits (dirty)</div>
          <div class="kpi__value" :style="{ color: 'var(--color-red)' }">{{ stats.text_edit || 0 }}</div>
          <div class="kpi__delta kpi__delta--down">flips has_user_override</div>
        </div>
        <div class="kpi">
          <div class="kpi__label">Non-dirty Corrections</div>
          <div class="kpi__value" :style="{ color: 'var(--color-green)' }">{{ corrections.length - (stats.text_edit || 0) }}</div>
          <div class="kpi__delta">flag colors preserved</div>
        </div>
        <div class="kpi">
          <div class="kpi__label">Distinct Actors</div>
          <div class="kpi__value">{{ distinctActors }}</div>
        </div>
      </template>
    </div>

    <div class="toolbar">
      <div class="filter-chip-row">
        <button
          v-for="t in types"
          :key="t.id"
          :class="['chip', { 'chip--solid': filter === t.id }]"
          :style="{ cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: '11px' }"
          @click="filter = t.id"
        >
          {{ t.label }}
          <span :style="{ opacity: 0.7 }">· {{ t.id === 'all' ? corrections.length : (stats[t.id] || 0) }}</span>
        </button>
      </div>
      <button class="btn btn--secondary" :style="{ marginLeft: 'auto' }" data-test-id="audit-wtc-export-jsonl" @click="exportJsonl">
        <Icon name="download" /> Export JSONL
      </button>
    </div>

    <div v-if="loading" :style="{ padding: '40px', textAlign: 'center', color: 'var(--fg2)' }">Loading audit log…</div>
    <div v-else-if="corrections.length === 0" :style="{ padding: '40px', textAlign: 'center', color: 'var(--fg2)' }">
      {{ globalMode ? 'No audit events yet — system activity accumulates here as users + workers run.' : 'No corrections yet — audit events accumulate as you edit segments.' }}
    </div>
    <AuditLedger v-else :filter="filter" :corrections="corrections" />

    <div v-if="!globalMode" class="card" :style="{ marginTop: '22px' }">
      <div class="card__header">
        <h3>L1 — has_user_override Invariant</h3>
        <span class="chip chip--green"><Icon name="check" :size="10" /> 11/11 types pass</span>
      </div>
      <div class="card__body">
        <p :style="{ margin: 0, fontSize: '13px', color: 'var(--fg2)', lineHeight: 1.6 }">
          Snapshot test verifies that <strong>only</strong> <code>text_edit</code> flips <code>has_user_override</code> to <code>true</code>.
          The other ten correction types — chat/poll insert/edit/remove, slide/speaker reassignment, mark_reviewed, annotation_add/remove —
          preserve all AI flag colors (drift / uncertain / low_confidence) on the affected segment.
          This was production-broken twice in v3.x (PR #33, Phase 8b) and is now structurally impossible.
        </p>
        <div :style="{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px', marginTop: '14px' }">
          <div
            v-for="t in allTypes"
            :key="t"
            :style="{ padding: '8px 10px', background: 'var(--surface-bg)', borderRadius: '6px', border: '1px solid var(--border-subtle)', fontSize: '11.5px', fontFamily: 'var(--font-mono)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }"
          >
            <span>{{ t }}</span>
            <span :style="{ color: t === 'text_edit' ? 'var(--color-red)' : 'var(--color-green)', fontWeight: 700, fontSize: '10px' }">
              {{ t === 'text_edit' ? '→ flips' : 'preserves' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>
