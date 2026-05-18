<script setup lang="ts">
/**
 * SectionPromptTemplates — verbatim port of settings-pages.jsx (278-407).
 * Catalog view + New-template editor. Inline both branches.
 */
import { ref } from 'vue';
import FormRow from './FormRow.vue';
import TogglePill from './TogglePill.vue';
import { PROMPT_TEMPLATES } from '@/fixtures/settings';
import { toast } from '@/composables/useToast';

const view = ref<'catalog' | 'new'>('catalog');

const cats = ['Education', 'Technical', 'Conversational', 'Business', 'Custom'];

function backToCatalog(): void { view.value = 'catalog'; }
function goNew(): void { view.value = 'new'; }
function backToSettings(): void { toast.push('Back to Settings', { tone: 'info' }); }
function editCustom(): void { toast.push('Editing Custom template (mock)', { tone: 'info' }); }
function duplicateTpl(name: string): void { toast.push(`Duplicated ${name}`, { tone: 'success' }); }
function viewTpl(): void { toast.push('Viewing template', { tone: 'info' }); }
function editTpl(): void { toast.push('Editing template', { tone: 'info' }); }

// New-template form state
const ntype = ref<'processing' | 'ai-prompt'>('processing');
const nname = ref('');
const nicon = ref('📝');
const ndesc = ref('');
const ncat = ref('Custom');
const nfiller = ref('Moderate');
const ntone = ref('Neutral');
const nterm = ref('Medium');
const nrewrite = ref('Minimal');
const nstructure = ref(true);
const nkeypoints = ref(true);
const nprompt = ref('');

function saveNew(): void {
  view.value = 'catalog';
  toast.push('Template saved', { tone: 'success' });
}
</script>

<template>
  <template v-if="view === 'catalog'">
    <div class="set-subnav">
      <button class="set-link" @click="backToSettings">← Settings</button>
      <h2 :style="{ margin: 0, fontSize: '24px', fontWeight: 800 }">Templates</h2>
      <button class="btn sugg-modal__submit" :style="{ marginLeft: 'auto' }" @click="goNew">+ New Template</button>
    </div>
    <h3 class="set-section-title" :style="{ marginTop: '12px' }">Processing Templates (STT Pipeline)</h3>
    <p :style="{ color: 'var(--fg2)', fontSize: '13px', margin: '0 0 18px' }">Control filler removal, tone, terminology for standard speech-to-text processing</p>
    <template v-for="cat in cats" :key="cat">
      <div v-if="PROMPT_TEMPLATES.filter((t) => t.cat === cat).length" :style="{ marginBottom: '18px' }">
        <div class="set-eyebrow" :style="{ marginBottom: '8px' }">{{ cat.toUpperCase() }}</div>
        <div
          v-for="t in PROMPT_TEMPLATES.filter((t) => t.cat === cat)"
          :key="t.id"
          class="set-tpl-card"
        >
          <div :style="{ fontSize: '22px' }">{{ t.icon }}</div>
          <div :style="{ flex: 1, minWidth: 0 }">
            <div class="set-tpl-card__name">{{ t.name }}</div>
            <div class="set-tpl-card__desc">{{ t.desc }}</div>
            <div class="set-tpl-card__chips">
              <code v-for="c in t.chips" :key="c">{{ c }}</code>
            </div>
          </div>
          <span class="set-tpl-card__tag set-tpl-card__tag--iil">IIL</span>
          <span class="set-tpl-card__tag">System</span>
          <button v-if="t.id === 'custom'" class="set-link" @click="editCustom">Edit</button>
          <button v-else class="set-link" @click="duplicateTpl(t.name)">Duplicate</button>
        </div>
      </div>
    </template>

    <h3 class="set-section-title" :style="{ marginTop: '28px' }">AI Prompt Templates (Gemini)</h3>
    <p :style="{ color: 'var(--fg2)', fontSize: '13px', margin: '0 0 18px' }">Define the system prompt sent to Gemini for AI MODE processing</p>
    <div class="set-tpl-card">
      <div :style="{ fontSize: '22px' }">📝</div>
      <div :style="{ flex: 1 }">
        <div class="set-tpl-card__name">Transcript</div>
        <div class="set-tpl-card__desc">Clean, enhanced transcript with corrected speech errors</div>
        <pre class="set-tpl-card__code">You are generating a VIN transcript that must be 100% compliant with the full Transcript SOP and downstream processing.p.</pre>
      </div>
      <span class="set-tpl-card__tag set-tpl-card__tag--iil">Prompt</span>
      <span class="set-tpl-card__tag">System</span>
      <button class="set-link" @click="viewTpl">View</button>
      <button class="set-link" @click="duplicateTpl('Transcript')">Duplicate</button>
    </div>
    <div class="set-tpl-card">
      <div :style="{ fontSize: '22px' }">📝</div>
      <div :style="{ flex: 1 }">
        <div class="set-tpl-card__name">Transcript (Paragraph v1)</div>
        <div class="set-tpl-card__desc">Clean, enhanced transcript with corrected speech errors</div>
      </div>
      <span class="set-tpl-card__tag set-tpl-card__tag--iil">Prompt</span>
      <button class="set-link" @click="editTpl">Edit</button>
    </div>
  </template>

  <template v-else>
    <div class="set-subnav">
      <button class="set-link" @click="backToCatalog">← Settings</button>
      <h2 :style="{ margin: 0, fontSize: '24px', fontWeight: 800 }">Templates</h2>
      <button class="btn sugg-modal__submit" :style="{ marginLeft: 'auto' }">+ New Template</button>
    </div>
    <div class="set-pane" :style="{ padding: '22px' }">
      <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }">
        <h3 :style="{ margin: 0, fontSize: '18px', fontWeight: 700 }">New Template</h3>
        <div :style="{ display: 'flex', gap: '8px' }">
          <button class="btn btn--secondary" @click="backToCatalog">Cancel</button>
          <button class="btn sugg-modal__submit" @click="saveNew">Save</button>
        </div>
      </div>
      <FormRow label="Type">
        <select v-model="ntype" class="set-input">
          <option value="processing">Processing Template (STT/IIL)</option>
          <option value="ai-prompt">AI Prompt Template (Gemini)</option>
        </select>
      </FormRow>
      <FormRow label="Name"><input v-model="nname" class="set-input" placeholder="Template name" /></FormRow>
      <FormRow label="Icon"><input v-model="nicon" class="set-input" :style="{ maxWidth: '80px' }" /></FormRow>
      <FormRow label="Description"><input v-model="ndesc" class="set-input" placeholder="Brief description" /></FormRow>
      <FormRow label="Category">
        <select v-model="ncat" class="set-input">
          <option>Education</option><option>Technical</option><option>Conversational</option><option>Business</option><option>Custom</option>
        </select>
      </FormRow>

      <div class="set-eyebrow" :style="{ marginTop: '24px', marginBottom: '14px', color: 'var(--text-accent)' }">IIL CONFIGURATION</div>
      <FormRow label="Filler policy">
        <select v-model="nfiller" class="set-input"><option>Strict</option><option>Moderate</option><option>Light</option></select>
      </FormRow>
      <FormRow label="Tone">
        <select v-model="ntone" class="set-input"><option>Neutral</option><option>Conversational</option><option>Formal</option><option>Persuasive</option></select>
      </FormRow>
      <FormRow label="Terminology">
        <select v-model="nterm" class="set-input"><option>Strict</option><option>Medium</option><option>Loose</option></select>
      </FormRow>
      <FormRow label="Rewrite level">
        <select v-model="nrewrite" class="set-input"><option>Minimal</option><option>Moderate</option><option>Aggressive</option></select>
      </FormRow>
      <FormRow label="Structure extraction">
        <template #control>
          <TogglePill :on="nstructure" @update:on="(v) => (nstructure = v)" />
        </template>
      </FormRow>
      <FormRow label="Key points">
        <template #control>
          <TogglePill :on="nkeypoints" @update:on="(v) => (nkeypoints = v)" />
        </template>
      </FormRow>

      <div class="set-eyebrow" :style="{ marginTop: '24px', marginBottom: '6px' }">SYSTEM PROMPT</div>
      <div :style="{ fontSize: '12px', color: 'var(--fg2)', marginBottom: '8px' }">The prompt sent to Gemini for AI MODE processing. Leave empty to use the default.</div>
      <textarea
        v-model="nprompt"
        class="set-input"
        :rows="8"
        placeholder="Enter system prompt."
        :style="{ fontFamily: 'var(--font-mono)', fontSize: '12.5px', lineHeight: 1.6, resize: 'vertical' }"
      />
      <div :style="{ textAlign: 'right', fontSize: '11px', color: 'var(--fg2)', marginTop: '4px' }">{{ nprompt.length }} characters</div>
    </div>
  </template>
</template>
