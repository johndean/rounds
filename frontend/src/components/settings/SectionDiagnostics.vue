<script setup lang="ts">
/**
 * SectionDiagnostics — verbatim port of settings-pages.jsx::SectionDiagnostics (598-621).
 * Home view + drill into GCSDebug + EmailDebug.
 */
import { ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import GCSDebug from './GCSDebug.vue';
import EmailDebug from './EmailDebug.vue';

const view = ref<'home' | 'test' | 'gcs'>('home');
</script>

<template>
  <EmailDebug v-if="view === 'test'" @back="view = 'home'" />
  <GCSDebug v-else-if="view === 'gcs'" @back="view = 'home'" />
  <template v-else>
    <SettingsHeader title="Diagnostics" lead="System health, observability counters, and operational probes." />
    <div class="set-card-block">
      <div class="set-eyebrow">TELEMETRY · §20 OBSERVABILITY</div>
      <h4 :style="{ margin: '6px 0 6px', fontSize: '16px', fontWeight: 700 }">Phase 0 counters</h4>
      <p :style="{ fontSize: '13px', color: 'var(--fg2)', lineHeight: 1.6, margin: '0 0 12px' }">
        Live values: <code>longtasks/min: 1</code> · <code>heap: 108 MB · flat over 30m</code> · <code>WS RTT: 18ms</code> · <code>autosave: 2s ago</code>. All seven §20 modules operational.
      </p>
      <button class="btn btn--tertiary" @click="view = 'test'">Open test email page →</button>
    </div>
    <div class="set-card-block">
      <div class="set-eyebrow">GCS · PIPELINE QA</div>
      <h4 :style="{ margin: '6px 0 6px', fontSize: '16px', fontWeight: 700 }">G1–G14 pipeline checks</h4>
      <p :style="{ fontSize: '13px', color: 'var(--fg2)', lineHeight: 1.6, margin: 0 }">
        14 GCS-side checks running on a 5-minute cadence. 7-day uptime <strong>99.98%</strong>. Failing G13 (PII redaction sentinel) auto-rotating salt.
      </p>
      <button class="btn btn--tertiary" :style="{ marginTop: '8px' }" @click="view = 'gcs'">Open GCS QA →</button>
    </div>
  </template>
</template>
