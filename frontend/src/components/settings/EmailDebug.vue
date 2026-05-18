<script setup lang="ts">
/**
 * EmailDebug — Phase 7 audit remediation, fully wired to real backend.
 *
 * Replaces the previous "(present)" theater. All five sections call live
 * /v1/admin/email-debug endpoints:
 *
 *   1. SMTP Config         — GET /config (env-var presence; no secrets)
 *   2. Connectivity Test   — POST /connectivity (STARTTLS/LOGIN/NOOP/QUIT)
 *   3. Send Test Email     — POST /send (real SMTP send with wire capture)
 *   4. Recent Attempts     — GET /attempts (audit ledger)
 *   5. Event Log           — in-memory client log of every API call
 *
 * Admin-only. Non-admin users get a 403 banner.
 */
import { onMounted, ref } from 'vue';
import FormRow from './FormRow.vue';
import { emailDebug, type SmtpConfigCheck, type SmtpConnectivityResult, type EmailAttemptRow } from '@/services/api';
import { ApiError } from '@/services/http';
import { toast } from '@/composables/useToast';

defineEmits<{ (e: 'back'): void }>();

// ── State ────────────────────────────────────────────────────────────────
const cfg            = ref<SmtpConfigCheck | null>(null);
const connectivity   = ref<SmtpConnectivityResult | null>(null);
const attempts       = ref<EmailAttemptRow[]>([]);
const eventLog       = ref<string[]>([]);
const loadingCfg     = ref(false);
const probing        = ref(false);
const sending        = ref(false);
const loadingAttempts = ref(false);
const forbidden      = ref(false);

// Send-test form
const toAddress = ref('johndean@vin.com');
const subject   = ref('Rounds Test Email');
const body      = ref('This is a test.');

// ── Helpers ──────────────────────────────────────────────────────────────
function log(line: string): void {
  const t = new Date();
  const hh = String(t.getHours()).padStart(2, '0');
  const mm = String(t.getMinutes()).padStart(2, '0');
  const ss = String(t.getSeconds()).padStart(2, '0');
  const ms = String(t.getMilliseconds()).padStart(3, '0');
  eventLog.value = [...eventLog.value, `${hh}:${mm}:${ss}.${ms}  ${line}`].slice(-500);
}

function fmt(e: unknown): string {
  if (e instanceof ApiError) return `${e.status} — ${e.message}`;
  return e instanceof Error ? e.message : String(e);
}

// ── Section 1: config ────────────────────────────────────────────────────
async function loadConfig(): Promise<void> {
  loadingCfg.value = true;
  log('STEP   GET /v1/admin/email-debug/config');
  try {
    cfg.value = await emailDebug.config();
    forbidden.value = false;
    log(`OK     config loaded — host=${cfg.value.host.present} from=${cfg.value.from_address.present} username=${cfg.value.username.present} password=${cfg.value.password.present}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) {
      forbidden.value = true;
      log('FORBID 403 — admin required');
    } else {
      log(`FAIL   ${fmt(e)}`);
    }
  } finally {
    loadingCfg.value = false;
  }
}

async function refresh(): Promise<void> {
  await loadConfig();
  await loadAttempts();
}

// ── Section 2: connectivity ──────────────────────────────────────────────
async function testSmtp(): Promise<void> {
  if (probing.value) return;
  probing.value = true;
  log('STEP   POST /v1/admin/email-debug/connectivity');
  try {
    connectivity.value = await emailDebug.connectivity();
    const c = connectivity.value;
    const allOk = c.connect.ok && c.starttls.ok && c.noop.ok && c.quit.ok && c.login.ok !== false;
    log(allOk
      ? `OK     connect=${c.connect.latency_ms}ms starttls=${c.starttls.latency_ms}ms noop=${c.noop.latency_ms}ms quit=${c.quit.latency_ms}ms`
      : `WARN   connectivity probe completed with failures — see panel for details`);
    toast.push(allOk ? 'SMTP connectivity OK' : 'SMTP probe completed with failures', { tone: allOk ? 'success' : 'warn' });
  } catch (e) {
    log(`FAIL   connectivity ${fmt(e)}`);
    toast.push(fmt(e), { tone: 'error' });
  } finally {
    probing.value = false;
  }
}

// ── Section 3: send ──────────────────────────────────────────────────────
async function sendTest(): Promise<void> {
  if (sending.value) return;
  if (!toAddress.value) {
    toast.push('Recipient required', { tone: 'warn' });
    return;
  }
  sending.value = true;
  log(`STEP   POST /v1/admin/email-debug/send to=${toAddress.value}`);
  try {
    const r = await emailDebug.send({
      to:        toAddress.value,
      subject:   subject.value,
      text_body: body.value,
    });
    if (r.sent) {
      log(`OK     sent in ${r.latency_ms}ms`);
      toast.push(`Test email sent in ${r.latency_ms}ms`, { tone: 'success' });
    } else {
      log(`FAIL   ${r.error || 'send returned sent=false'}`);
      toast.push(r.error || 'Send failed', { tone: 'error' });
    }
    await loadAttempts();
  } catch (e) {
    log(`FAIL   ${fmt(e)}`);
    toast.push(fmt(e), { tone: 'error' });
  } finally {
    sending.value = false;
  }
}

// ── Section 4: attempts ──────────────────────────────────────────────────
async function loadAttempts(): Promise<void> {
  loadingAttempts.value = true;
  log('STEP   GET /v1/admin/email-debug/attempts?limit=50');
  try {
    attempts.value = await emailDebug.attempts({ limit: 50 });
    log(`OK     loaded ${attempts.value.length} attempt(s)`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) {
      forbidden.value = true;
      log('FORBID 403 — admin required');
    } else {
      log(`FAIL   ${fmt(e)}`);
    }
  } finally {
    loadingAttempts.value = false;
  }
}

async function retest(row: EmailAttemptRow): Promise<void> {
  toAddress.value = row.to_address;
  subject.value = row.subject || 'Rounds Test Email';
  body.value = 'Retest of attempt ' + row.id;
  await sendTest();
}

// ── Section 5: event log ─────────────────────────────────────────────────
function clearLog(): void { eventLog.value = []; }

function copyBundle(): void {
  const bundle = JSON.stringify(
    { config: cfg.value, connectivity: connectivity.value, last_attempts: attempts.value.slice(0, 5) },
    null, 2,
  );
  navigator.clipboard?.writeText(bundle).then(
    () => toast.push('Diagnostic bundle copied to clipboard', { tone: 'success' }),
    () => toast.push('Clipboard unavailable', { tone: 'warn' }),
  );
}

// ── Init ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  log('INFO   email-debug page mounted');
  await loadConfig();
  if (!forbidden.value) await loadAttempts();
});

function fmtTs(iso: string | null): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); }
  catch { return iso; }
}
</script>

<template>
  <div class="set-subnav">
    <button class="set-link" @click="$emit('back')">← Settings</button>
    <h2 :style="{ margin: 0, fontSize: '22px', fontWeight: 700 }">Test Email · Diagnostics</h2>
    <span :style="{ fontSize: '11px', color: 'var(--fg2)', marginLeft: '8px' }">SMTP config · connectivity check · test send · attempts ledger</span>
  </div>

  <div
    v-if="forbidden"
    role="status"
    :style="{
      padding: '14px 16px', marginBottom: '14px',
      background: 'rgba(217,119,6,0.08)', border: '1px solid rgba(217,119,6,0.35)',
      borderRadius: 'var(--radius-sm)', color: '#b45309',
      fontSize: '13px', lineHeight: 1.55,
    }"
  >
    <strong>Admin-only.</strong>
    SMTP diagnostics require admin privileges. Contact your admin if you need
    email diagnostics run on your behalf.
  </div>

  <p :style="{ background: 'rgba(8,97,206,0.06)', border: '1px solid rgba(8,97,206,0.25)', padding: '10px 14px', borderRadius: '6px', fontSize: '12px', color: 'var(--fg1)', margin: '0 0 18px' }">
    All four sections run against the same SMTP config as production
    stage-notify emails — failures reproduce exactly what a real send
    would do. Username and password values are never returned, only their
    presence.
  </p>

  <div class="set-pane" :style="{ padding: '18px', marginBottom: '14px' }">
    <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }">
      <h4 :style="{ margin: 0, fontSize: '14px', fontWeight: 700 }">1. SMTP Config</h4>
      <button class="set-link" :disabled="loadingCfg" @click="refresh">{{ loadingCfg ? 'Loading…' : 'Refresh' }}</button>
    </div>
    <div v-if="!cfg && !forbidden" :style="{ color: 'var(--fg2)', fontSize: '12px' }">Loading…</div>
    <template v-else-if="cfg">
      <div v-for="(meta, key) in cfg" :key="key" class="set-smtp-row">
        <code>SMTP_{{ key.toUpperCase() }}</code>
        <span :style="{ color: meta.present ? 'var(--color-green)' : 'var(--color-amber)' }">
          {{ meta.present ? '✓' : '✗' }}
          <span :style="{ color: meta.value ? 'var(--fg1)' : 'var(--fg2)', fontStyle: meta.value ? 'normal' : 'italic', marginLeft: '8px' }">{{ meta.value || (meta.present ? '(present)' : 'not set') }}</span>
        </span>
      </div>
    </template>
  </div>

  <div class="set-pane" :style="{ padding: '18px', marginBottom: '14px' }">
    <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }">
      <h4 :style="{ margin: 0, fontSize: '14px', fontWeight: 700 }">2. Connectivity Test</h4>
      <button class="btn sugg-modal__submit" :disabled="probing || forbidden" @click="testSmtp">
        {{ probing ? 'Probing…' : 'Test SMTP Connection' }}
      </button>
    </div>
    <div v-if="!connectivity" :style="{ fontSize: '12px', color: 'var(--fg2)', marginTop: '10px' }">Not yet run.</div>
    <table v-else :style="{ width: '100%', marginTop: '12px', fontSize: '12px', borderCollapse: 'collapse' }">
      <thead>
        <tr :style="{ textAlign: 'left', color: 'var(--fg2)', letterSpacing: '0.06em', textTransform: 'uppercase', fontSize: '10px' }">
          <th :style="{ padding: '6px 8px', borderBottom: '1px solid var(--border-subtle)' }">Step</th>
          <th :style="{ padding: '6px 8px', borderBottom: '1px solid var(--border-subtle)' }">Result</th>
          <th :style="{ padding: '6px 8px', borderBottom: '1px solid var(--border-subtle)' }">Latency</th>
          <th :style="{ padding: '6px 8px', borderBottom: '1px solid var(--border-subtle)' }">Detail</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(step, name) in connectivity" :key="name">
          <td :style="{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }">{{ name }}</td>
          <td :style="{ padding: '6px 8px', color: step.ok === true ? 'var(--color-green)' : step.ok === false ? 'var(--color-red)' : 'var(--fg2)' }">
            {{ step.ok === true ? '✓ ok' : step.ok === false ? '✗ failed' : 'skipped' }}
          </td>
          <td :style="{ padding: '6px 8px', fontFamily: 'var(--font-mono)', color: 'var(--fg2)' }">{{ step.latency_ms !== null ? step.latency_ms + ' ms' : '—' }}</td>
          <td :style="{ padding: '6px 8px', color: 'var(--fg2)', fontSize: '11px' }">{{ step.error || '' }}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="set-pane" :style="{ padding: '18px', marginBottom: '14px' }">
    <h4 :style="{ margin: '0 0 12px', fontSize: '14px', fontWeight: 700 }">3. Send Test Email</h4>
    <FormRow label="To"><input v-model="toAddress" class="set-input" /></FormRow>
    <FormRow label="Subject"><input v-model="subject" class="set-input" /></FormRow>
    <FormRow label="Body (plain text)">
      <textarea v-model="body" class="set-input" :rows="4" />
    </FormRow>
    <div :style="{ textAlign: 'right' }">
      <button class="btn sugg-modal__submit" :disabled="sending || forbidden" @click="sendTest">
        {{ sending ? 'Sending…' : 'Send' }}
      </button>
    </div>
  </div>

  <div :style="{ background: 'rgba(8,97,206,0.05)', border: '1px solid rgba(8,97,206,0.2)', padding: '12px', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }">
    <button class="btn btn--tertiary" @click="copyBundle">📋 Copy diagnostic bundle</button>
    <span :style="{ fontSize: '12px', color: 'var(--fg2)' }">JSON: config + last connectivity result + 5 most-recent attempts. Never includes SMTP_USERNAME or SMTP_PASSWORD values.</span>
  </div>

  <div class="set-pane" :style="{ padding: '18px', marginBottom: '14px' }">
    <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }">
      <h4 :style="{ margin: 0, fontSize: '14px', fontWeight: 700 }">4. Recent Attempts</h4>
      <button class="set-link" :disabled="loadingAttempts" @click="loadAttempts">{{ loadingAttempts ? 'Loading…' : 'Refresh' }}</button>
    </div>
    <table v-if="attempts.length > 0" class="set-attempts">
      <thead><tr><th>WHEN</th><th>TRIGGER</th><th>TO</th><th>SUBJECT</th><th>RESULT</th><th>MS</th><th></th></tr></thead>
      <tbody>
        <tr v-for="row in attempts" :key="row.id">
          <td>{{ fmtTs(row.attempted_at) }}</td>
          <td><code>{{ row.trigger }}</code></td>
          <td>{{ row.to_address }}</td>
          <td :style="{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }">{{ row.subject || '—' }}</td>
          <td :style="{ color: row.result === 'sent' ? 'var(--color-green)' : 'var(--color-red)' }">
            {{ row.result === 'sent' ? '✓ sent' : '✗ failed' }}
          </td>
          <td>{{ row.latency_ms ?? '—' }}</td>
          <td><button class="btn btn--secondary btn--sm" @click="retest(row)">Retest</button></td>
        </tr>
      </tbody>
    </table>
    <div v-else :style="{ padding: '14px', color: 'var(--fg2)', fontSize: '12px', textAlign: 'center' }">
      No send attempts logged yet.
    </div>
  </div>

  <div class="set-pane" :style="{ padding: '18px' }">
    <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }">
      <h4 :style="{ margin: 0, fontSize: '14px', fontWeight: 700 }">5. Event Log</h4>
      <button class="set-link" @click="clearLog">Clear</button>
    </div>
    <pre :style="{
      background: '#0B1626', color: '#DDE5ED',
      fontFamily: 'var(--font-mono)', fontSize: '11px', lineHeight: 1.6,
      padding: '14px', borderRadius: '4px', margin: 0,
      maxHeight: '260px', overflow: 'auto',
    }">{{ eventLog.length ? eventLog.join('\n') : 'Event log is empty.' }}</pre>
  </div>
</template>
