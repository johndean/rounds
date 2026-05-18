<script setup lang="ts">
/**
 * EmailDebug — verbatim port of settings-pages.jsx::EmailDebug (675-764).
 * SMTP config rows + connectivity test + send-test form + recent attempts + event log.
 */
import FormRow from './FormRow.vue';
import { SESSION_TYPES, SOP_STAGE_KEYS } from '@/fixtures/settings';
import { SESSIONS } from '@/fixtures/sessions';
import { toast } from '@/composables/useToast';

defineEmits<{ (e: 'back'): void }>();

const smtpRows: Array<[string, string]> = [
  ['SMTP_HOST',     'smtp.resend.com'],
  ['SMTP_PORT',     '587'],
  ['SMTP_FROM',     'mic@design.veterinary.support'],
  ['SMTP_USERNAME', 'present'],
  ['SMTP_PASSWORD', 'present'],
];

function refresh(): void { toast.push('Refreshed', { tone: 'success' }); }
function testSmtp(): void { toast.push('SMTP connection OK', { tone: 'success' }); }
function sendTest(): void { toast.push('Test email sent', { tone: 'success' }); }
function copyBundle(): void { toast.push('Diagnostic bundle copied', { tone: 'success' }); }
function clearLog(): void { toast.push('Cleared', { tone: 'success' }); }
</script>

<template>
  <div class="set-subnav">
    <button class="set-link" @click="$emit('back')">← Settings</button>
    <h2 :style="{ margin: 0, fontSize: '22px', fontWeight: 700 }">Test Email · Diagnostics</h2>
    <span :style="{ fontSize: '11px', color: 'var(--fg2)', marginLeft: '8px' }">SMTP config · connectivity check · test send · copy-ready diagnostic bundle</span>
  </div>
  <p :style="{ background: 'rgba(8,97,206,0.06)', border: '1px solid rgba(8,97,206,0.25)', padding: '10px 14px', borderRadius: '6px', fontSize: '12px', color: 'var(--fg1)', margin: '0 0 18px' }">
    • Use this page to debug email send issues before contacting support. All three sections run against the same SMTP config as production stage notifications — failures reproduce exactly what a real send would do.
  </p>

  <div class="set-pane" :style="{ padding: '18px', marginBottom: '14px' }">
    <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }">
      <h4 :style="{ margin: 0, fontSize: '14px', fontWeight: 700 }">1. SMTP Config</h4>
      <button class="set-link" @click="refresh">Refresh</button>
    </div>
    <div v-for="[k, v] in smtpRows" :key="k" class="set-smtp-row">
      <code>{{ k }}</code>
      <span :style="{ color: 'var(--color-green)' }">
        ✓
        <span :style="{ color: v === 'present' ? 'var(--fg2)' : 'var(--fg1)', fontStyle: v === 'present' ? 'italic' : 'normal', marginLeft: '8px' }">{{ v }}</span>
      </span>
    </div>
  </div>

  <div class="set-pane" :style="{ padding: '18px', marginBottom: '14px' }">
    <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }">
      <h4 :style="{ margin: 0, fontSize: '14px', fontWeight: 700 }">2. Connectivity Test</h4>
      <button class="btn sugg-modal__submit" @click="testSmtp">Test SMTP Connection</button>
    </div>
    <div :style="{ fontSize: '12px', color: 'var(--fg2)', marginTop: '10px' }">Not yet run.</div>
  </div>

  <div class="set-pane" :style="{ padding: '18px', marginBottom: '14px' }">
    <h4 :style="{ margin: '0 0 12px', fontSize: '14px', fontWeight: 700 }">3. Send Test Email</h4>
    <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }">
      <FormRow label="TYPE">
        <select class="set-input">
          <option>default (global)</option>
          <option v-for="t in SESSION_TYPES.slice(1)" :key="t">{{ t }}</option>
        </select>
      </FormRow>
      <FormRow label="STAGE">
        <select class="set-input">
          <option v-for="s in SOP_STAGE_KEYS" :key="s.id">{{ s.label.toUpperCase() }}</option>
        </select>
      </FormRow>
    </div>
    <FormRow label="SESSION (REAL DATA)">
      <select class="set-input">
        <option>— sample data (today's date) —</option>
        <option v-for="s in SESSIONS" :key="s.id">{{ s.code || s.id }}</option>
      </select>
    </FormRow>
    <FormRow label="To"><input class="set-input" value="johndean@vin.com" /></FormRow>
    <FormRow label="Subject"><input class="set-input" value="VIN Test Email" /></FormRow>
    <FormRow label="Body (plain text OR HTML — pasted template is rendered HTML)">
      <textarea class="set-input" :rows="4">This is a test.</textarea>
    </FormRow>
    <div :style="{ textAlign: 'right' }">
      <button class="btn sugg-modal__submit" @click="sendTest">Send</button>
    </div>
  </div>

  <div :style="{ background: 'rgba(8,97,206,0.05)', border: '1px solid rgba(8,97,206,0.2)', padding: '12px', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }">
    <button class="btn btn--tertiary" @click="copyBundle">📋 Copy diagnostic bundle</button>
    <span :style="{ fontSize: '12px', color: 'var(--fg2)' }">Paste into a support ticket or share with your VIN admin. Never includes SMTP_USERNAME or SMTP_PASSWORD values.</span>
  </div>

  <div class="set-pane" :style="{ padding: '18px', marginBottom: '14px' }">
    <h4 :style="{ margin: '0 0 12px', fontSize: '14px', fontWeight: 700 }">4. Recent Attempts</h4>
    <table class="set-attempts">
      <thead><tr><th>WHEN</th><th>TRIGGER</th><th>TO</th><th>SUBJECT</th><th>RESULT</th><th>MS</th><th></th></tr></thead>
      <tbody>
        <tr>
          <td>04/20/2026, 05:12:07 PM</td><td><code>debug_test</code></td><td>johndean.bali@gmail.com</td>
          <td>[VIN] Ready to copy edit — 040126_Freema…</td>
          <td :style="{ color: 'var(--color-green)' }">✓ sent</td><td>1028</td>
          <td><button class="btn btn--secondary btn--sm">Retest</button></td>
        </tr>
        <tr>
          <td>04/20/2026, 04:17:17 PM</td><td><code>debug_test</code></td><td>johndean.bali@gmail.com</td>
          <td>VIN Test Email from production</td>
          <td :style="{ color: 'var(--color-green)' }">✓ sent</td><td>1057</td>
          <td><button class="btn btn--secondary btn--sm">Retest</button></td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="set-pane" :style="{ padding: '18px' }">
    <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }">
      <h4 :style="{ margin: 0, fontSize: '14px', fontWeight: 700 }">5. Event Log</h4>
      <button class="set-link" @click="clearLog">Clear</button>
    </div>
    <pre :style="{ background: '#0B1626', color: '#DDE5ED', fontFamily: 'var(--font-mono)', fontSize: '11px', lineHeight: 1.6, padding: '14px', borderRadius: '4px', margin: 0, overflowX: 'auto' }">08:10:53.028  INFO   email-debug page mounted
08:10:53.028  INFO   operator: johndean@vin.com
08:10:53.028  STEP   GET /v1/admin/email-debug/config
08:10:53.028  STEP   GET /v1/admin/email-debug/attempts?limit=50
08:10:53.028  STEP   GET /v1/sop/types
08:10:53.028  STEP   GET /v1/sessions?limit=50
08:10:53.451  OK     config loaded — present: host, port, from_address, username, password
08:10:53.459  OK     loaded 17 type(s)
08:10:53.475  OK     loaded 2 attempt(s)
08:10:53.497  OK     loaded 38 session(s) for picker</pre>
  </div>
</template>
