<script setup lang="ts">
/**
 * AuditTabInline — verbatim port of audit.jsx::AuditTabInline (165-221).
 * Inside the editor's Audit tab: Decisions (default) vs Ledger toggle, with
 * full-WTC link + CSV export.
 */
import { ref, computed } from 'vue';
import { RouterLink } from 'vue-router';
import Icon from '@/components/shared/Icon.vue';
import DecisionCard from '@/components/editor/DecisionCard.vue';
import AuditLedger from '@/components/audit/AuditLedger.vue';
import { type Segment } from '@/fixtures/transcript';
import { toast } from '@/composables/useToast';

interface CorrectionRow {
  id: string;
  t: string;
  type: string;
  actor: string;
  seg: string;
  prior?: string | null;
  next?: string | null;
  note?: string | null;
}

const props = defineProps<{
  session: { id: string };
  activeSegmentId: string | null | undefined;
  liveCorrections?: readonly CorrectionRow[];
  liveSegments?: readonly Segment[];
}>();

const emit = defineEmits<{ (e: 'segmentClick', id: string): void }>();

const view = ref<'decisions' | 'ledger'>('decisions');

const corrections = computed<readonly CorrectionRow[]>(() => props.liveCorrections ?? []);

const segmentsById = computed<Map<string, Segment>>(() => {
  const m = new Map<string, Segment>();
  (props.liveSegments ?? []).forEach((s) => m.set(s.id, s));
  return m;
});

const decisionTypes = new Set(['text_edit', 'chat_insert', 'slide_reassignment', 'speaker_reassignment', 'annotation_add']);
const decisions = computed(() => corrections.value.filter((c) => decisionTypes.has(c.type)).slice().reverse());

function exportCsv(): void {
  const csv = corrections.value
    .map((e) => `${e.t},${e.actor},${e.type},"${e.note ?? ''}"`)
    .join('\n') + '\n';
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'audit.csv';
  a.click();
  URL.revokeObjectURL(url);
  toast.push('Audit log exported', { tone: 'success' });
}
</script>

<template>
  <section class="audit-tab" data-screen-label="Audit · Decisions">
    <div class="audit-tab__toolbar">
      <div class="audit-tab__count">
        <strong>{{ view === 'decisions' ? decisions.length : corrections.length }}</strong>
        {{ view === 'decisions' ? ' active decisions' : ' ledger rows' }}
      </div>
      <div class="audit-tab__flags">
        <span class="audit-tab__flag"><span class="dot" :style="{ background: 'var(--color-red)' }" /> Drift (0)</span>
        <span class="audit-tab__flag"><span class="dot" :style="{ background: 'var(--color-amber)' }" /> Uncertain (0)</span>
        <span class="audit-tab__flag"><span class="dot" :style="{ background: 'var(--color-blue)' }" /> Low conf (0)</span>
      </div>
      <div class="audit-tab__viewtoggle" role="radiogroup" aria-label="Audit view">
        <button
          :class="view === 'decisions' ? 'is-active' : ''"
          role="radio" :aria-checked="view === 'decisions'"
          @click="view = 'decisions'"
        >Decisions</button>
        <button
          :class="view === 'ledger' ? 'is-active' : ''"
          role="radio" :aria-checked="view === 'ledger'"
          @click="view = 'ledger'"
        >Ledger</button>
      </div>
      <div class="audit-tab__actions">
        <RouterLink :to="`/e/${session.id}/audit`" class="btn btn--ghost btn--sm">
          <Icon name="external" /> Full WTC
        </RouterLink>
        <button class="btn btn--ghost btn--sm" data-test-id="audit-export" @click="exportCsv">
          <Icon name="download" /> Export
        </button>
      </div>
    </div>

    <div v-if="view === 'decisions'" class="audit-tab__body">
      <DecisionCard
        v-for="c in decisions"
        :key="c.id"
        :c="c"
        :segments-by-id="segmentsById"
        :active-segment-id="activeSegmentId"
        @segment-click="(id) => emit('segmentClick', id)"
      />
      <div
        v-if="decisions.length === 0"
        :style="{ padding: '40px', textAlign: 'center', color: 'var(--fg2)' }"
      >No active decisions.</div>
    </div>
    <div v-else class="audit-tab__body audit-tab__body--ledger">
      <AuditLedger />
    </div>
  </section>
</template>
