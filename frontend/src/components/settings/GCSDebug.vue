<script setup lang="ts">
/**
 * GCSDebug — live probe table for the GCS-side ingestion plane.
 *
 * Phase 2 of the 2026-05-23 Settings BUILD remediation plan. The original
 * port (settings-pages.jsx::GCSDebug 623-673) rendered a hardcoded "all
 * green" fixture which never actually probed anything; this version calls
 * GET /v1/diag/gcs-checks on mount and re-runs on demand.
 *
 * Endpoint returns 14 rows: G1-G6 are real probes, G7-G14 are deferred
 * stubs (ok=null) rendered with a neutral "deferred" chip so operators
 * can't mistake them for healthy.
 */
import { onMounted, ref, computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { diag, type GcsCheckRow } from '@/services/api';
import { toast } from '@/composables/useToast';
import { ApiError } from '@/services/http';

defineEmits<{ (e: 'back'): void }>();

const checks = ref<GcsCheckRow[]>([]);
const loading = ref(true);
const lastRunAt = ref<Date | null>(null);

const okCount = computed(() => checks.value.filter((c) => c.ok === true).length);
const failCount = computed(() => checks.value.filter((c) => c.ok === false).length);
const deferredCount = computed(() => checks.value.filter((c) => c.ok === null).length);
const totalChecks = computed(() => checks.value.length);

async function load(): Promise<void> {
  loading.value = true;
  try {
    checks.value = await diag.gcsChecks();
    lastRunAt.value = new Date();
  } catch (e) {
    const msg = e instanceof ApiError
      ? `${e.status} — ${e.message}`
      : 'Failed to run GCS checks';
    toast.push(msg, { tone: 'error' });
  } finally {
    loading.value = false;
  }
}

onMounted(load);

const gridCols = '60px 1fr 110px 90px 1fr';

function lastRunDisplay(): string {
  if (!lastRunAt.value) return 'never';
  const ago = Math.round((Date.now() - lastRunAt.value.getTime()) / 1000);
  if (ago < 60) return `${ago}s ago`;
  if (ago < 3600) return `${Math.round(ago / 60)}m ago`;
  return `${Math.round(ago / 3600)}h ago`;
}
</script>

<template>
  <div class="set-subnav">
    <button class="set-link" @click="$emit('back')">← Settings</button>
    <h2 :style="{ margin: 0, fontSize: '22px', fontWeight: 700 }">GCS Pipeline QA</h2>
    <span :style="{ fontSize: '11px', color: 'var(--fg2)', marginLeft: '8px' }">
      Live probes · GET /v1/diag/gcs-checks · audit-logged
    </span>
    <span :style="{ marginLeft: 'auto', display: 'inline-flex', gap: '8px', alignItems: 'center' }">
      <span :style="{ fontSize: '11px', color: 'var(--fg2)' }">Last run: {{ lastRunDisplay() }}</span>
      <button
        class="btn btn--tertiary btn--sm"
        :disabled="loading"
        data-test-id="gcs-checks-rerun"
        @click="load"
      >
        {{ loading ? 'Running…' : 'Re-run checks' }}
      </button>
    </span>
  </div>
  <p :style="{ background: 'rgba(8,97,206,0.06)', border: '1px solid rgba(8,97,206,0.25)', padding: '10px 14px', borderRadius: '6px', fontSize: '12px', color: 'var(--fg1)', margin: '0 0 18px' }">
    • Six real probes (G1–G6): bucket reachability, signed-URL generation, PUT
    round-trip to <code>_diag/</code>, lifecycle policy, CORS, default-object-ACL.
    G7–G14 are explicitly deferred — the chip says <strong>deferred</strong>, not
    <strong>pass</strong>, so the table never shows fake health.
  </p>
  <div class="kpi-row" :style="{ marginBottom: '18px' }">
    <div class="kpi">
      <div class="kpi__label">Real probes passing</div>
      <div class="kpi__value" :style="{ color: failCount === 0 ? 'var(--color-green)' : 'var(--color-amber)' }">
        {{ okCount }}/{{ totalChecks - deferredCount }}
      </div>
    </div>
    <div class="kpi">
      <div class="kpi__label">Real probes failing</div>
      <div class="kpi__value" :style="{ color: failCount === 0 ? 'var(--fg2)' : 'var(--color-amber)' }">
        {{ failCount }}
      </div>
    </div>
    <div class="kpi">
      <div class="kpi__label">Deferred (not yet implemented)</div>
      <div class="kpi__value" :style="{ color: 'var(--fg2)' }">{{ deferredCount }}</div>
    </div>
    <div class="kpi">
      <div class="kpi__label">Total checks</div>
      <div class="kpi__value">{{ totalChecks }}</div>
    </div>
  </div>
  <div class="audit-ledger">
    <div class="audit-row audit-row--head" :style="{ gridTemplateColumns: gridCols }">
      <div>ID</div><div>Check</div><div>Status</div><div>Latency</div><div>Note</div>
    </div>
    <div v-if="loading && checks.length === 0" class="audit-row" :style="{ gridTemplateColumns: gridCols, color: 'var(--fg2)', fontStyle: 'italic' }">
      <div>—</div><div>Running probes…</div><div>—</div><div>—</div><div>—</div>
    </div>
    <div v-for="c in checks" :key="c.id" class="audit-row" :style="{ gridTemplateColumns: gridCols }">
      <div class="seg">{{ c.id }}</div>
      <div class="type">{{ c.name }}</div>
      <div>
        <span v-if="c.ok === true" class="chip chip--green"><Icon name="check" :size="10" /> pass</span>
        <span v-else-if="c.ok === false" class="chip chip--amber"><Icon name="alert" :size="10" /> fail</span>
        <span v-else class="chip" :style="{ background: 'rgba(77,105,149,0.08)', color: 'var(--fg2)', borderColor: 'rgba(77,105,149,0.25)' }">deferred</span>
      </div>
      <div class="t">{{ c.ok === null ? '—' : `${c.ms} ms` }}</div>
      <div class="note">{{ c.note || '—' }}</div>
    </div>
  </div>
</template>
