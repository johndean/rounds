<script setup lang="ts">
/**
 * SectionDiagnostics — verbatim port of settings-pages.jsx::SectionDiagnostics (598-621).
 * Home view + drill into GCSDebug + EmailDebug.
 */
import { ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import GCSDebug from './GCSDebug.vue';
import EmailDebug from './EmailDebug.vue';
import { diag, type ClearSlotsResult } from '@/services/api';
import { toast } from '@/composables/useToast';
import { ApiError } from '@/services/http';

const view = ref<'home' | 'test' | 'gcs'>('home');

// Rate-limit slot reset — unblocks a user who hit 429 RATE_LIMIT_USER after
// create+delete cycles leaked Redis slots. Sweeps the user's active-sessions
// set, removes any slot whose session is soft-deleted or gone.
const resetting = ref<boolean>(false);
const lastReset = ref<ClearSlotsResult | null>(null);

async function onResetSlots(): Promise<void> {
  if (resetting.value) return;
  resetting.value = true;
  try {
    const result = await diag.clearRateLimitSlots();
    lastReset.value = result;
    toast.push(
      result.removed_count > 0
        ? `Cleared ${result.removed_count} stale slot${result.removed_count === 1 ? '' : 's'}. ${result.remaining}/${result.cap} remaining.`
        : `No stale slots. ${result.remaining}/${result.cap} in use.`,
      { tone: result.removed_count > 0 ? 'success' : 'info' },
    );
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : (e instanceof Error ? e.message : 'Reset failed');
    toast.push(msg, { tone: 'error' });
  } finally {
    resetting.value = false;
  }
}
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
    <div class="set-card-block">
      <div class="set-eyebrow">RATE LIMIT · STUCK SLOT RECOVERY</div>
      <h4 :style="{ margin: '6px 0 6px', fontSize: '16px', fontWeight: 700 }">Reset rate-limit slots</h4>
      <p :style="{ fontSize: '13px', color: 'var(--fg2)', lineHeight: 1.6, margin: '0 0 12px' }">
        If you hit <code>429 RATE_LIMIT_USER</code> after creating + deleting sessions,
        Redis can leak the slot. This sweeps your active-sessions set and removes any
        slot whose session is soft-deleted or gone. Live slots are preserved.
      </p>
      <button
        class="btn btn--tertiary"
        :disabled="resetting"
        @click="onResetSlots"
      >
        {{ resetting ? 'Sweeping…' : 'Reset my stale slots' }}
      </button>
      <p
        v-if="lastReset"
        :style="{ marginTop: '10px', fontSize: '12px', color: 'var(--fg2)', fontFamily: 'var(--font-mono)' }"
      >
        Last sweep: removed <strong>{{ lastReset.removed_count }}</strong>,
        <strong>{{ lastReset.remaining }}/{{ lastReset.cap }}</strong> remaining.
      </p>
    </div>
  </template>
</template>
