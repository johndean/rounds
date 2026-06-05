<script setup lang="ts">
/**
 * EmailBuilder — per-Type × per-Stage HTML email template editor.
 *
 * Phase 5 of the 2026-05-23 Settings BUILD remediation plan. Previously
 * a fake-save editor (saveForType + sendTest were warn-toasts); now
 * wired to /v1/email-templates CRUD (migration 048) and reuses
 * /v1/admin/email-debug/send for the test-send button.
 *
 * Template resolution:
 *   - "default" Type or no per-type row → uses the default row for the stage
 *   - per-Type row exists → that row wins
 *
 * Saving from "default" with the Default Type selected updates the default
 * row. Saving with a real Type creates (or updates) a per-Type override.
 */
import { onMounted, ref, watch, computed } from 'vue';
import {
  settingsApi,
  emailTemplatesApi,
  emailDebug,
  auth,
  type EmailTemplate,
  type SettingsType,
} from '@/services/api';
import { ApiError } from '@/services/http';
import { toast } from '@/composables/useToast';

const emit = defineEmits<{ (e: 'back'): void }>();

interface StageOpt { id: string; label: string; kind?: 'transition' | 'overdue' }
const stages: StageOpt[] = [
  // Stage-transition templates (migration 048) — fire on stage entry
  { id: 'prep',       label: '1 Prep',                    kind: 'transition' },
  { id: 'copy_draft', label: '2 Copy edit — draft',       kind: 'transition' },
  { id: 'medical',    label: '3 Medical review',          kind: 'transition' },
  { id: 'copy_final', label: '4 Copy edit — final',       kind: 'transition' },
  { id: 'cms',        label: '5 CMS published',           kind: 'transition' },
  { id: 'captions',   label: '6 Captions on video',       kind: 'transition' },
  { id: 'qa',         label: '7 QA',                      kind: 'transition' },
  { id: 'complete',   label: '8 Complete',                kind: 'transition' },
  // Deadline-overdue templates (migration 051, Phase 7.2) — fire when
  // SOP_DEADLINE_EMAIL_ENABLED is true AND a stage sits past its SLA.
  // 'complete' has no overdue variant (terminal, SLA=0).
  { id: 'prep_overdue',       label: '⚠ Prep — overdue',          kind: 'overdue' },
  { id: 'copy_draft_overdue', label: '⚠ Copy edit draft — overdue', kind: 'overdue' },
  { id: 'medical_overdue',    label: '⚠ Medical review — overdue',  kind: 'overdue' },
  { id: 'copy_final_overdue', label: '⚠ Copy edit final — overdue', kind: 'overdue' },
  { id: 'cms_overdue',        label: '⚠ CMS publish — overdue',     kind: 'overdue' },
  { id: 'captions_overdue',   label: '⚠ Captions — overdue',        kind: 'overdue' },
  { id: 'qa_overdue',         label: '⚠ QA — overdue',              kind: 'overdue' },
];

// Real session types from /v1/settings/types so the Type dropdown shows
// the live list, not a fixture. Sentinel id === '' represents the default
// (session_type_id IS NULL) row.
const types = ref<SettingsType[]>([]);
const selectedTypeId = ref<string>('');     // '' = default

const stage = ref<string>('prep');

// Currently-loaded template (the row returned by resolve). When the
// operator edits subject/body, those refs may diverge from current; the
// "Save for this Type" / "Revert to default" buttons reconcile.
const current = ref<EmailTemplate | null>(null);
const resolvedFrom = ref<'per_type' | 'default' | null>(null);
const subject = ref<string>('');
const body = ref<string>('');

const loading = ref(false);
const saving = ref(false);
const sending = ref(false);

async function loadResolved(): Promise<void> {
  loading.value = true;
  try {
    const t = await emailTemplatesApi.resolve({
      session_type_id: selectedTypeId.value || null,
      stage_id:        stage.value,
      locale:          'en-US',
    });
    current.value = t;
    resolvedFrom.value = (t.resolved_from as 'per_type' | 'default' | undefined) ?? null;
    subject.value = t.subject;
    body.value = t.body;
  } catch (e) {
    // 404 = no default exists either (migration 048 should prevent this).
    // Surface a clear toast + clear the editor.
    current.value = null;
    resolvedFrom.value = null;
    subject.value = '';
    body.value = '';
    const msg = e instanceof ApiError
      ? `${e.status} — ${e.message}`
      : 'Failed to load template';
    toast.push(msg, { tone: 'error' });
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    types.value = await settingsApi.types();
  } catch {
    // Even if /types fails, the Default-Type editor still works.
    types.value = [];
  }
  await loadResolved();
});

watch([stage, selectedTypeId], () => { void loadResolved(); });

async function saveForType(): Promise<void> {
  if (saving.value) return;
  saving.value = true;
  try {
    if (selectedTypeId.value === '') {
      // Editing the default row directly. Must already exist (seeded by
      // migration 048); update it.
      if (current.value && resolvedFrom.value === 'default') {
        const updated = await emailTemplatesApi.update(current.value.id, {
          subject: subject.value,
          body:    body.value,
        });
        current.value = updated;
        resolvedFrom.value = 'default';
        toast.push('Default template saved for this stage', { tone: 'success' });
      } else {
        // No default exists for this stage (unusual). Create one.
        const created = await emailTemplatesApi.add({
          session_type_id: null,
          stage_id:        stage.value,
          locale:          'en-US',
          subject:         subject.value,
          body:            body.value,
        });
        current.value = created;
        resolvedFrom.value = 'default';
        toast.push('Default template created for this stage', { tone: 'success' });
      }
    } else {
      // A real Type is selected.
      if (current.value && resolvedFrom.value === 'per_type'
          && current.value.session_type_id === selectedTypeId.value) {
        // Update the existing per-Type row.
        const updated = await emailTemplatesApi.update(current.value.id, {
          subject: subject.value,
          body:    body.value,
        });
        current.value = updated;
        resolvedFrom.value = 'per_type';
        toast.push('Per-Type template saved', { tone: 'success' });
      } else {
        // Currently showing the default for this Type → create a per-Type
        // override row.
        const created = await emailTemplatesApi.add({
          session_type_id: selectedTypeId.value,
          stage_id:        stage.value,
          locale:          'en-US',
          subject:         subject.value,
          body:            body.value,
        });
        current.value = created;
        resolvedFrom.value = 'per_type';
        toast.push('Per-Type override created', { tone: 'success' });
      }
    }
  } catch (e) {
    const msg = e instanceof ApiError
      ? extractApiMessage(e, 'Failed to save template')
      : 'Failed to save template';
    toast.push(msg, { tone: 'error' });
  } finally {
    saving.value = false;
  }
}

async function revertToDefault(): Promise<void> {
  // If we're already on the default, just re-fetch.
  // If we're on a per-Type override, delete it and re-resolve (which
  // returns the default since the override is gone).
  if (saving.value) return;
  if (resolvedFrom.value === 'per_type' && current.value) {
    saving.value = true;
    try {
      await emailTemplatesApi.remove(current.value.id);
      toast.push('Per-Type override removed; using default', { tone: 'info' });
      await loadResolved();
    } catch (e) {
      const msg = e instanceof ApiError
        ? extractApiMessage(e, 'Failed to revert')
        : 'Failed to revert';
      toast.push(msg, { tone: 'error' });
    } finally {
      saving.value = false;
    }
  } else {
    await loadResolved();
    toast.push('Reverted to saved default', { tone: 'info' });
  }
}

async function sendTest(): Promise<void> {
  if (sending.value) return;
  // Use the logged-in user's email by default.
  let recipient: string;
  try {
    const me = await auth.me();
    recipient = me.email;
  } catch {
    recipient = '';
  }
  const input = window.prompt(
    'Send test email to:',
    recipient,
  );
  if (!input) return;
  const to = input.trim();
  if (!to || !/^\S+@\S+\.\S+$/.test(to)) {
    toast.push('Invalid recipient email', { tone: 'warn' });
    return;
  }
  sending.value = true;
  try {
    // Substitute sample vars client-side so the test send exercises the
    // exact same render pipeline the production hook will use later.
    const subj = substituteVars(subject.value, SAMPLE_VARS);
    const html = substituteVars(body.value, SAMPLE_VARS);
    const r = await emailDebug.send({ to, subject: subj, html_body: html });
    if (r.sent) {
      toast.push(`Test sent to ${to} (${r.latency_ms} ms)`, { tone: 'success' });
    } else {
      toast.push(`SMTP failed: ${r.error || 'unknown error'}`, { tone: 'error' });
    }
  } catch (e) {
    const msg = e instanceof ApiError
      ? extractApiMessage(e, 'Test send failed')
      : 'Test send failed';
    toast.push(msg, { tone: 'error' });
  } finally {
    sending.value = false;
  }
}

function extractApiMessage(e: ApiError, fallback: string): string {
  const body = e.body as { detail?: { message?: string; code?: string } | string } | undefined;
  const detail = body?.detail;
  if (detail && typeof detail === 'object' && detail.message) return detail.message;
  if (typeof detail === 'string') return `${e.status} — ${detail}`;
  return `${e.status} — ${fallback}`;
}

// ─── Variable palette ────────────────────────────────────────────────
interface VarCategory { name: string; vars: string[] }
const varCategories: VarCategory[] = [
  { name: 'SESSION',  vars: ['session_code', 'session_title', 'session_type_name', 'session_uploaded_at', 'session_duration_minutes'] },
  { name: 'COUNTS',   vars: ['segment_count', 'slide_count', 'speaker_count', 'chat_message_count', 'poll_count'] },
  { name: 'STAGE',    vars: ['stage_name', 'stage_label_human', 'stage_number', 'total_stages', 'prior_stage_label', 'next_stage_label', 'stage_color'] },
  { name: 'ASSIGNEE', vars: ['assignee_first_name', 'assignee_full_name', 'assignee_initials', 'assignee_email'] },
  { name: 'ACTOR',    vars: ['prior_actor_full_name', 'prior_actor_initials', 'prior_actor_completed_at'] },
  { name: 'LINKS',    vars: ['results_url', 'editor_url', 'session_page_url', 'audit_trail_url', 'cms_url', 'video_url'] },
];

const SAMPLE_VARS: Record<string, string> = {
  session_code:              '041526_JepsenGrant',
  session_title:             'Diagnostic Approach to Feline Anemia',
  session_type_name:         'AAFV',
  session_uploaded_at:       'May 17, 2026',
  session_duration_minutes:  '54',
  segment_count:             '120',
  slide_count:               '18',
  speaker_count:             '4',
  chat_message_count:        '23',
  poll_count:                '5',
  stage_name:                'prep',
  stage_label_human:         'Prep',
  stage_number:              '1',
  total_stages:              '8',
  prior_stage_label:         '—',
  next_stage_label:          'Copy edit (draft)',
  stage_color:               '#002855',
  assignee_first_name:       'Lacy',
  assignee_full_name:        'Lacy McKinney',
  assignee_initials:         'LM',
  assignee_email:            'lacy@vin.com',
  prior_actor_full_name:     'Carla Burris',
  prior_actor_initials:      'CB',
  prior_actor_completed_at:  'May 17, 2026 14:32',
  results_url:               'https://rounds.vin/#/p/sample-uuid',
  editor_url:                'https://rounds.vin/#/session/sample-uuid/editor',
  session_page_url:          'https://rounds.vin/#/session/sample-uuid',
  audit_trail_url:           'https://rounds.vin/#/audit?session_id=sample-uuid',
  cms_url:                   'https://cms.vin.com/sessions/sample',
  video_url:                 'https://video.vin.com/sample.mp4',
};

function substituteVars(template: string, vars: Record<string, string>): string {
  return template.replace(/\{\{\s*([a-z_]+)\s*\}\}/gi, (_, name: string) => {
    return vars[name] ?? `{{ ${name} }}`;
  });
}

const subjectRef = ref<HTMLInputElement | null>(null);
const bodyRef = ref<HTMLTextAreaElement | null>(null);
const focusedField = ref<'subject' | 'body'>('subject');

function insertVar(v: string): void {
  const token = ` {{ ${v} }}`;
  if (focusedField.value === 'subject') {
    subject.value = subject.value + token;
  } else {
    body.value = body.value + token;
  }
}

// ─── Preview ─────────────────────────────────────────────────────────
const previewSubject = computed(() => substituteVars(subject.value, SAMPLE_VARS));
const previewBody    = computed(() => substituteVars(body.value, SAMPLE_VARS));

const currentSourceLabel = computed(() => {
  if (resolvedFrom.value === 'per_type') return 'Per-Type override';
  if (resolvedFrom.value === 'default')  return 'Default';
  return '—';
});
</script>

<template>
  <div class="set-subnav">
    <button class="set-link" @click="emit('back')">← Settings</button>
    <h2 :style="{ margin: 0, fontSize: '22px', fontWeight: 700 }">Email Template Builder</h2>
    <span :style="{ fontSize: '11px', color: 'var(--fg2)', marginLeft: '8px' }">
      Per Type × Stage · stage-notification emails sent from VIN Transcript Software
    </span>
    <span :style="{ marginLeft: 'auto', display: 'inline-flex', gap: '10px', alignItems: 'center' }">
      <span class="set-eyebrow">EDITING</span>
      <select
        v-model="selectedTypeId"
        class="set-input set-input--sm"
        :style="{ width: '240px' }"
        data-test-id="email-builder-type"
      >
        <option value="">default (applies to every Type)</option>
        <option v-for="t in types" :key="t.id" :value="t.id">{{ t.code }} · {{ t.label }}</option>
      </select>
    </span>
  </div>
  <p :style="{ background: 'rgba(8,97,206,0.06)', border: '1px solid rgba(8,97,206,0.25)', padding: '8px 14px', borderRadius: '6px', fontSize: '12px', margin: '0 0 18px', color: 'var(--fg1)' }">
    • Templates cascade: the per-Type row wins, otherwise the default row renders. Variables use <code v-pre>{{ variable_name }}</code> syntax — click a chip on the right to insert it.
  </p>
  <div class="set-emailbuilder">
    <div class="set-pane" :style="{ padding: '18px' }">
      <h4 :style="{ margin: '0 0 10px', fontSize: '14px', fontWeight: 700 }">Email Templates (per Type × Stage)</h4>
      <p :style="{ fontSize: '12px', color: 'var(--fg2)', margin: '0 0 14px' }">
        Each stage sends an email to the person assigned for that stage. Customise per Type when different rounds need different wording.
        <em v-if="loading" :style="{ marginLeft: '6px', color: 'var(--fg2)' }">loading…</em>
      </p>
      <div class="set-stage-tabs">
        <button
          v-for="s in stages"
          :key="s.id"
          :class="['set-stage-tab', stage === s.id ? 'is-active' : '']"
          @click="stage = s.id"
        >{{ s.label }}</button>
      </div>
      <div class="set-emailbuilder__field">
        <div class="set-eyebrow" :style="{ marginBottom: '6px' }">SUBJECT</div>
        <input
          ref="subjectRef"
          v-model="subject"
          class="set-input set-input--full"
          data-test-id="email-builder-subject"
          @focus="focusedField = 'subject'"
        />
      </div>
      <div class="set-emailbuilder__field">
        <div class="set-eyebrow" :style="{ marginBottom: '6px' }">HTML BODY</div>
        <textarea
          ref="bodyRef"
          v-model="body"
          class="set-input set-input--full set-input--mono"
          :rows="18"
          data-test-id="email-builder-body"
          @focus="focusedField = 'body'"
        />
      </div>
      <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '14px' }">
        <div :style="{ display: 'flex', gap: '8px' }">
          <button
            class="btn sugg-modal__submit"
            :disabled="saving || loading"
            data-test-id="email-builder-save"
            @click="saveForType"
          >{{ saving ? 'Saving…' : (selectedTypeId === '' ? 'Save default' : 'Save for this Type') }}</button>
          <button
            class="btn btn--ghost btn--sm"
            :disabled="saving || loading || resolvedFrom !== 'per_type'"
            @click="revertToDefault"
          >Remove override · revert</button>
          <button
            class="btn btn--ghost btn--sm"
            :disabled="sending || loading"
            data-test-id="email-builder-send-test"
            @click="sendTest"
          >{{ sending ? 'Sending…' : 'Send test to my email' }}</button>
        </div>
        <span :style="{ fontSize: '11px', color: 'var(--fg2)' }">
          Source: <strong :style="{ color: 'var(--fg1)' }">{{ currentSourceLabel }}</strong>
        </span>
      </div>
    </div>
    <div class="set-pane" :style="{ padding: '18px' }">
      <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }">
        <h4 :style="{ margin: 0, fontSize: '14px', fontWeight: 700 }">PREVIEW</h4>
        <select class="set-input set-input--sm" disabled><option>sample data</option></select>
      </div>
      <div :style="{ background: 'var(--surface-bg)', padding: '10px 14px', border: '1px solid var(--border-subtle)', borderRadius: '6px', marginBottom: '10px', fontSize: '12px' }">
        <strong>Subject:</strong> {{ previewSubject }}
      </div>
      <iframe
        :srcdoc="previewBody"
        :style="{ width: '100%', minHeight: '420px', border: '1px solid var(--border-subtle)', borderRadius: '6px', background: '#fff' }"
        sandbox="allow-same-origin"
      />
      <div :style="{ marginTop: '18px' }">
        <div class="set-eyebrow" :style="{ marginBottom: '8px' }">
          VARIABLES <span :style="{ color: 'var(--fg2)', marginLeft: '6px', textTransform: 'none', letterSpacing: 0, fontWeight: 500 }">click to insert at end of focused field</span>
        </div>
        <div v-for="cat in varCategories" :key="cat.name" :style="{ marginBottom: '10px' }">
          <div class="set-eyebrow" :style="{ fontSize: '9px', marginBottom: '4px' }">{{ cat.name }}</div>
          <div :style="{ display: 'flex', flexWrap: 'wrap', gap: '4px' }">
            <code
              v-for="v in cat.vars"
              :key="v"
              class="set-var-chip"
              @click="insertVar(v)"
            >{{ v }}</code>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
