<script setup lang="ts">
/**
 * EmailBuilder — verbatim port of settings-pages.jsx::EmailBuilder (462-596).
 * Per-Type × per-Stage HTML email template editor with variable palette and
 * live preview header. Defaults are VIN-branded per-stage HTML.
 */
import { ref, watch, computed } from 'vue';
import { SESSION_TYPES } from '@/fixtures/settings';
import { toast } from '@/composables/useToast';

const emit = defineEmits<{ (e: 'back'): void }>();

interface StageOpt { id: string; label: string }
const stages: StageOpt[] = [
  { id: 'prep',       label: '1 Prep' },
  { id: 'copy_draft', label: '2 Copy edit — draft' },
  { id: 'medical',    label: '3 Medical review' },
  { id: 'copy_final', label: '4 Copy edit — final' },
  { id: 'cms',        label: '5 CMS published' },
  { id: 'captions',   label: '6 Captions on video' },
  { id: 'qa',         label: '7 QA' },
  { id: 'complete',   label: '8 Complete' },
];

interface Template { subject: string; body: string }
const DEFAULTS: Record<string, Template> = {
  prep:       { subject: '[VIN] Ready for prep — {{ session_code }}',           body: `<!DOCTYPE html>\n<html><body style="margin:0;padding:0;background:#F7F7F7;font-family:'ProximaNova',Helvetica,Arial,sans-serif;color:#002855;">\n  <table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <tr><td style="background:#002855;padding:20px 28px;color:#FFFFFF;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Ready for prep · {{ session_code }}</div>\n    </td></tr>\n    <tr><td style="padding:18px 28px;background:#F9FAFB;font-family:'Courier New',monospace;font-size:12px;color:#4D6995;line-height:1.7;border-bottom:1px solid #DDE5ED;">\n      Uploaded {{ session_uploaded_at }} · {{ segment_count }} segments · {{ slide_count }} slides · {{ speaker_count }} speakers\n    </td></tr>\n    <tr><td style="padding:24px 28px;font-size:14px;line-height:1.6;color:#002855;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>A new session has been uploaded and is ready for your prep review. Before copy edit can begin, please verify the extras and confirm everything needed is present.</p>\n      <p style="margin:18px 0 6px;font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#4D6995;">WHAT TO DO</p>\n      <ol style="margin:0 0 18px;padding-left:20px;font-size:14px;line-height:1.7;">\n        <li>Open the session and verify slides, chat, and polls are all present.</li>\n        <li>Confirm the session code and title are correct.</li>\n        <li>Flag any missing extras or malformed input.</li>\n        <li>When ready, mark <strong>Prep complete</strong> to hand off to copy edit.</li>\n      </ol>\n      <p><a href="{{ results_url }}" style="display:inline-block;background:#002855;color:#FFFFFF;padding:11px 22px;border-radius:8px;font-weight:600;text-decoration:none;">Open session →</a></p>\n    </td></tr>\n    <tr><td style="padding:14px 28px;background:#F7F7F7;font-size:11px;color:#4D6995;border-top:1px solid #DDE5ED;">\n      Sent by VIN Transcript Software · Reply to this email with questions\n    </td></tr>\n  </table>\n</body></html>` },
  copy_draft: { subject: '[VIN] Ready to copy edit — {{ session_code }}',        body: `<!-- VIN Transcript Software · Stage 2 ·  Copy edit draft -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;padding:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Ready to copy edit · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;line-height:1.65;color:#002855;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>{{ prior_actor_full_name }} has finished prep on {{ session_code }}. It's ready for your draft copy edit in the AI editor.</p>\n      <p>Open the editor → work through flagged review items → mark <strong>Copy edit — draft complete</strong>.</p>\n      <p><a href="{{ editor_url }}" style="display:inline-block;background:#002855;color:#FFFFFF;padding:11px 22px;border-radius:8px;font-weight:600;text-decoration:none;">Open editor →</a></p>\n    </div>\n  </div>\n</body></html>` },
  medical:    { subject: '[VIN] Medical review requested — {{ session_code }}',  body: `<!-- VIN Transcript Software · Stage 3 · Medical review -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;padding:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Medical review requested · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;line-height:1.65;color:#002855;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>The draft transcript for {{ session_code }} — <em>{{ session_title }}</em> — is ready for your medical review. Please review with tracked changes enabled and return it to {{ prior_actor_full_name }} when complete.</p>\n      <p><strong>What to do</strong></p>\n      <ol style="padding-left:20px;line-height:1.7;">\n        <li>Open the Word document.</li>\n        <li>Turn on <strong>Track Changes</strong> before editing.</li>\n        <li>Focus on medical accuracy, terminology, and factual corrections.</li>\n        <li>Save and send the reviewed document back to {{ prior_actor_full_name }}.</li>\n      </ol>\n    </div>\n  </div>\n</body></html>` },
  copy_final: { subject: '[VIN] Final copy edit pass — {{ session_code }}',     body: `<!-- VIN Transcript Software · Stage 4 -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Final copy edit · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;color:#002855;line-height:1.65;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>Medical review is complete. Incorporate the medical reviewer's notes, finalize speaker labels, and do the final readthrough.</p>\n    </div>\n  </div>\n</body></html>` },
  cms:        { subject: '[VIN] Ready for CMS publish — {{ session_code }}',    body: `<!-- VIN Transcript Software · Stage 5 -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Publish to CMS · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;color:#002855;line-height:1.65;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>Final copy is complete. Generate the CMS-ready document, upload to VIN library, and attest CE hours.</p>\n    </div>\n  </div>\n</body></html>` },
  captions:   { subject: '[VIN] Captions ready for upload — {{ session_code }}', body: `<!-- VIN Transcript Software · Stage 6 -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Captions ready · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;color:#002855;line-height:1.65;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>The transcript is published to CMS. The SRT file is ready for Wistia upload and burn-in.</p>\n      <ol style="padding-left:20px;line-height:1.7;">\n        <li>Download the SRT file.</li>\n        <li>Upload to Wistia for the session video.</li>\n        <li>Enable burn-in captions and verify playback.</li>\n        <li>Mark <strong>Captions on video complete</strong>.</li>\n      </ol>\n    </div>\n  </div>\n</body></html>` },
  qa:         { subject: '[VIN] QA pass requested — {{ session_code }}',        body: `<!-- VIN Transcript Software · Stage 7 -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">QA pass · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;color:#002855;line-height:1.65;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>The session is ready for QA. Run end-to-end playback spot checks, verify mobile rendering, confirm search indexing, and validate GCS G1–G14 checks pass.</p>\n    </div>\n  </div>\n</body></html>` },
  complete:   { subject: '[VIN] Session published · {{ session_code }}',        body: `<!-- VIN Transcript Software · Stage 8 -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Published — {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;color:#002855;line-height:1.65;">\n      <p>Hi {{ prior_actor_full_name }},</p>\n      <p>{{ session_code }} is now live in the VIN library. Presenter notified, audit ledger archived. Thanks for the work.</p>\n    </div>\n  </div>\n</body></html>` },
};

const stage = ref<string>('prep');
const type = ref<string>('default · default');
const subject = ref<string>(DEFAULTS.prep!.subject);
const body = ref<string>(DEFAULTS.prep!.body);

watch(stage, (s) => {
  subject.value = DEFAULTS[s]!.subject;
  body.value = DEFAULTS[s]!.body;
});

interface VarCategory { name: string; vars: string[] }
const varCategories: VarCategory[] = [
  { name: 'SESSION',  vars: ['session_code', 'session_title', 'session_type_name', 'session_uploaded_at', 'session_duration_minutes'] },
  { name: 'COUNTS',   vars: ['segment_count', 'slide_count', 'speaker_count', 'chat_message_count', 'poll_count'] },
  { name: 'STAGE',    vars: ['stage_name', 'stage_label_human', 'stage_number', 'total_stages', 'prior_stage_label', 'next_stage_label', 'stage_color'] },
  { name: 'ASSIGNEE', vars: ['assignee_first_name', 'assignee_full_name', 'assignee_initials', 'assignee_email'] },
  { name: 'ACTOR',    vars: ['prior_actor_full_name', 'prior_actor_initials', 'prior_actor_completed_at'] },
  { name: 'LINKS',    vars: ['results_url', 'editor_url', 'session_page_url', 'audit_trail_url', 'cms_url', 'video_url'] },
];

function insertVar(v: string): void {
  subject.value = subject.value + ` {{ ${v} }}`;
}
function saveForType(): void { toast.push('Saved for this Type', { tone: 'success' }); }
function revert(): void {
  subject.value = DEFAULTS[stage.value]!.subject;
  body.value = DEFAULTS[stage.value]!.body;
  toast.push('Reverted to default', { tone: 'info' });
}
function sendTest(): void { toast.push('Test email sent', { tone: 'success' }); }

const previewSessionCode = '041526_JepsenGrant';
const previewSubject = computed(() => subject.value.split('{{ session_code }}').join(previewSessionCode));
const previewTitle = computed(() => previewSubject.value.replace('[VIN] ', ''));
</script>

<template>
  <div class="set-subnav">
    <button class="set-link" @click="emit('back')">← Settings</button>
    <h2 :style="{ margin: 0, fontSize: '22px', fontWeight: 700 }">Email Template Builder</h2>
    <span :style="{ fontSize: '11px', color: 'var(--fg2)', marginLeft: '8px' }">Per Type × Stage · stage-notification emails sent from VIN Transcript Software</span>
    <span :style="{ marginLeft: 'auto', display: 'inline-flex', gap: '10px', alignItems: 'center' }">
      <span class="set-eyebrow">EDITING</span>
      <select
        v-model="type"
        class="set-input set-input--sm"
        :style="{ width: '240px' }"
      >
        <option>default · default</option>
        <option v-for="t in SESSION_TYPES.slice(1)" :key="t">{{ t }}</option>
      </select>
    </span>
  </div>
  <p :style="{ background: 'rgba(8,97,206,0.06)', border: '1px solid rgba(8,97,206,0.25)', padding: '8px 14px', borderRadius: '6px', fontSize: '12px', margin: '0 0 18px', color: 'var(--fg1)' }">
    • Templates cascade: the Type-specific row wins → the built-in default for that stage renders otherwise. Variables use <code v-pre>{{ variable_name }}</code> syntax. Click a variable in the palette to insert it at the cursor.
  </p>
  <div class="set-emailbuilder">
    <div class="set-pane" :style="{ padding: '18px' }">
      <h4 :style="{ margin: '0 0 10px', fontSize: '14px', fontWeight: 700 }">Email Templates (per Type × Stage)</h4>
      <p :style="{ fontSize: '12px', color: 'var(--fg2)', margin: '0 0 14px' }">
        Each stage sends an email to the person assigned for that stage. Customise the template per Type when you need different wording for different rounds.
      </p>
      <div class="set-stage-tabs">
        <button
          v-for="s in stages"
          :key="s.id"
          :class="['set-stage-tab', stage === s.id ? 'is-active' : '']"
          @click="stage = s.id"
        >{{ s.label }} <span class="set-stage-tab__default">DEFAULT</span></button>
      </div>
      <div class="set-emailbuilder__field">
        <div class="set-eyebrow" :style="{ marginBottom: '6px' }">SUBJECT</div>
        <input v-model="subject" class="set-input set-input--full" />
      </div>
      <div class="set-emailbuilder__field">
        <div class="set-eyebrow" :style="{ marginBottom: '6px' }">HTML BODY</div>
        <textarea v-model="body" class="set-input set-input--full set-input--mono" :rows="18" />
      </div>
      <div class="set-emailbuilder__field">
        <div class="set-eyebrow" :style="{ marginBottom: '6px' }">
          PLAIN TEXT (OPTIONAL)
          <span :style="{ color: 'var(--fg2)', marginLeft: '6px', textTransform: 'none', letterSpacing: 0, fontWeight: 500 }">Auto-generated from HTML if left blank.</span>
        </div>
        <textarea class="set-input set-input--full set-input--mono" :rows="6" />
      </div>
      <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '14px' }">
        <div :style="{ display: 'flex', gap: '8px' }">
          <button class="btn sugg-modal__submit" @click="saveForType">Save for this Type</button>
          <button class="btn btn--ghost btn--sm" @click="revert">Revert to default</button>
          <button class="btn btn--ghost btn--sm" @click="sendTest">Send test to my email</button>
        </div>
        <span :style="{ fontSize: '11px', color: 'var(--fg2)' }">Source: <strong :style="{ color: 'var(--fg1)' }">Default</strong></span>
      </div>
    </div>
    <div class="set-pane" :style="{ padding: '18px' }">
      <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }">
        <h4 :style="{ margin: 0, fontSize: '14px', fontWeight: 700 }">PREVIEW</h4>
        <select class="set-input set-input--sm"><option>sample data (today's date)</option></select>
      </div>
      <div :style="{ background: 'var(--surface-bg)', padding: '10px 14px', border: '1px solid var(--border-subtle)', borderRadius: '6px', marginBottom: '10px', fontSize: '12px' }">
        <strong>Subject:</strong> {{ previewSubject }}
      </div>
      <div :style="{ background: '#fff', border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: 0, fontSize: '13px', lineHeight: 1.6, overflow: 'hidden' }">
        <div :style="{ background: 'var(--color-navy)', color: '#fff', padding: '20px 28px' }">
          <div :style="{ fontSize: '11px', letterSpacing: '.18em', textTransform: 'uppercase', color: '#B1C9E8' }">VIN Transcript Software</div>
          <div :style="{ fontSize: '18px', fontWeight: 800, marginTop: '4px' }">{{ previewTitle }}</div>
        </div>
        <div :style="{ background: 'var(--surface-bg)', padding: '16px 28px', fontFamily: 'var(--font-mono)', fontSize: '11.5px', color: 'var(--fg2)', lineHeight: 1.7, borderBottom: '1px solid var(--border-subtle)' }">
          Uploaded May 17, 2026 · 120 segments · 18 slides · 4 speakers
        </div>
        <div :style="{ padding: '20px 28px', color: 'var(--fg1)' }">
          <p :style="{ margin: '0 0 10px' }">Hi Lacy,</p>
          <p :style="{ margin: '0 0 14px' }">A new session has been uploaded and is ready for your prep review. Before copy edit can begin, please verify the extras and confirm everything needed is present.</p>
          <div :style="{ fontSize: '11px', fontWeight: 800, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--fg2)', margin: '14px 0 6px' }">WHAT TO DO</div>
          <ol :style="{ margin: '0 0 14px', paddingLeft: '22px', fontSize: '13px' }">
            <li>Open the session and verify slides, chat, and polls are all present.</li>
            <li>Confirm the session code and title are correct.</li>
            <li>Flag any missing extras or malformed input.</li>
            <li>When ready, mark <strong>Prep complete</strong> to hand off to copy edit.</li>
          </ol>
          <button class="btn" :style="{ background: 'var(--color-navy)', color: '#fff' }">Open session →</button>
        </div>
        <div :style="{ padding: '12px 28px', background: 'var(--surface-muted)', fontSize: '11px', color: 'var(--fg2)', borderTop: '1px solid var(--border-subtle)' }">
          Sent by VIN Transcript Software · Reply to this email with questions
        </div>
      </div>
      <div :style="{ marginTop: '18px' }">
        <div class="set-eyebrow" :style="{ marginBottom: '8px' }">
          VARIABLES <span :style="{ color: 'var(--fg2)', marginLeft: '6px', textTransform: 'none', letterSpacing: 0, fontWeight: 500 }">click to insert</span>
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
