<script setup lang="ts">
/**
 * GCS QA — /gcs
 * Faithful 1:1 port of docs/port-source/processing.jsx::GcsRoute.
 */
import { computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';

interface Check { id: string; name: string; ok: boolean; ms: number; note?: string }

const checks: Check[] = [
  { id: 'G1',  name: 'Asset bucket exists',         ok: true,  ms: 12 },
  { id: 'G2',  name: 'Object ACLs (uniform)',       ok: true,  ms: 22 },
  { id: 'G3',  name: 'Lifecycle policy applied',     ok: true,  ms: 8  },
  { id: 'G4',  name: 'Retention lock present',       ok: true,  ms: 14 },
  { id: 'G5',  name: 'KMS key rotation < 90d',       ok: true,  ms: 36 },
  { id: 'G6',  name: 'Audit log streaming',          ok: true,  ms: 24 },
  { id: 'G7',  name: 'Pub/Sub subscription live',    ok: true,  ms: 18 },
  { id: 'G8',  name: 'STT credentials valid',        ok: true,  ms: 41 },
  { id: 'G9',  name: 'Gemini quota healthy',         ok: true,  ms: 28 },
  { id: 'G10', name: 'DLQ depth < threshold',        ok: true,  ms: 11 },
  { id: 'G11', name: 'Backup snapshot < 24h',        ok: true,  ms: 9  },
  { id: 'G12', name: 'Egress region matches policy', ok: true,  ms: 16 },
  { id: 'G13', name: 'PII redaction sentinel',       ok: false, ms: 52, note: '1 sample required new salt — auto-rotating now' },
  { id: 'G14', name: 'End-to-end smoke (5 files)',   ok: true,  ms: 1480 },
];

const okCount = computed(() => checks.filter(c => c.ok).length);
</script>

<template>
  <main class="page" data-screen-label="GCS QA">
    <div class="page-eyebrow">
      <span>Operations</span><span class="sep">/</span><span>GCS Pipeline QA</span>
    </div>
    <h1 class="page-title">GCS Pipeline QA</h1>
    <p class="page-desc">
      14 checks across the GCS-side ingestion plane. Each check runs on a 5-minute cadence; results stream
      into the audit ledger. Failures trigger PagerDuty after two consecutive misses.
    </p>
    <div class="kpi-row">
      <div class="kpi">
        <div class="kpi__label">Checks Passing</div>
        <div class="kpi__value" :style="{ color: 'var(--color-green)' }">{{ okCount }}/14</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">Last Sweep</div>
        <div class="kpi__value" :style="{ fontSize: '18px' }">00:01:42</div>
        <div class="kpi__delta">cadence 5 min</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">7-Day Uptime</div>
        <div class="kpi__value">99.98%</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">Open Pages</div>
        <div class="kpi__value">0</div>
      </div>
    </div>
    <div class="audit-ledger">
      <div class="audit-row audit-row--head" :style="{ gridTemplateColumns: '60px 1fr 80px 80px 1fr' }">
        <div>ID</div><div>Check</div><div>Status</div><div>Latency</div><div>Note</div>
      </div>
      <div
        v-for="c in checks"
        :key="c.id"
        class="audit-row"
        :style="{ gridTemplateColumns: '60px 1fr 80px 80px 1fr' }"
      >
        <div class="seg">{{ c.id }}</div>
        <div class="type">{{ c.name }}</div>
        <div>
          <span v-if="c.ok" class="chip chip--green"><Icon name="check" :size="10" /> pass</span>
          <span v-else class="chip chip--amber"><Icon name="alert" :size="10" /> retrying</span>
        </div>
        <div class="t">{{ c.ms }} ms</div>
        <div class="note">{{ c.note || '—' }}</div>
      </div>
    </div>
  </main>
</template>
