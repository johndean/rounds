<script setup lang="ts">
/**
 * Upload — /upload
 * Faithful 1:1 port of docs/port-source/upload.jsx (352 LOC).
 */
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import Icon from '@/components/shared/Icon.vue';
import { toast } from '@/composables/useToast';

const router = useRouter();

const filesAttached = ref(true);
const pipeline = ref('direct');
const aiMode = ref('transcript');
const model = ref('gemini-25-pro');
const style = ref('lecture');
const styleOpen = ref(true);
const iilOpen = ref(true);
const iilEnabled = ref(true);
const tier1 = ref(true);
const tier2 = ref(true);
const tier3 = ref(true);
const stt = ref('google_latest_long');
const savedTpl = ref('');

const attached = [
  { kind: 'AI Transcription', file: '042326_Hendershott_audio.mp3',  size: '69.2 MB',  chip: 'blue',  icon: 'speaker' },
  { kind: 'Video Playback',   file: '042326_Hendershott_vid.mp4',    size: '235.9 MB', chip: 'blue',  icon: 'play' },
  { kind: 'Slide Extraction', file: '042326_Hendershott.pdf',        size: '5.4 MB',   chip: 'amber', icon: 'slide' },
  { kind: 'Chat Transcript',  file: '042326_Hendershott_chat.txt',   size: '16.1 KB',  chip: 'blue',  icon: 'message' },
  { kind: 'Session Manifest', file: '042326_Hendershott_extras2.txt', size: '12.5 KB',  chip: 'blue',  icon: 'doc' },
];

const aiModeOptions = [
  { value: 'transcript',       label: 'Transcript',       help: 'Clean, enhanced transcript with corrected speech errors' },
  { value: 'summary',          label: 'Summary',          help: 'Condensed summary of the session' },
  { value: 'key-moments',      label: 'Key Moments',      help: 'Extracts the highest-signal moments from the session' },
  { value: 'structured-notes', label: 'Structured Notes', help: 'Outline-style notes with sections and bullets' },
  { value: 'custom-prompt',    label: 'Custom Prompt',    help: 'User-defined processing instructions' },
];

interface StyleItem { id: string; name: string; icon: string; desc: string }
const styleCategories: Array<{ id: string; label: string; items: StyleItem[] }> = [
  { id: 'education',      label: 'Education',      items: [
    { id: 'lecture',  name: 'Lecture',             icon: '🎓', desc: 'Optimized for structured teaching content' },
    { id: 'training', name: 'Training / Workshop', icon: '🛠️', desc: 'Handles Q&A, exercises and interaction patterns' },
  ]},
  { id: 'technical',      label: 'Technical',      items: [
    { id: 'technical', name: 'Technical Deep Dive', icon: '⚙️', desc: 'Terminology preservation — minimal rewrite' },
  ]},
  { id: 'conversational', label: 'Conversational', items: [
    { id: 'podcast', name: 'Podcast / Conversation', icon: '🎙️', desc: 'Light cleanup — conversational flow preserved' },
  ]},
  { id: 'business',       label: 'Business',       items: [
    { id: 'sales', name: 'Sales / Presentation', icon: '📊', desc: 'Emphasis and persuasion patterns preserved' },
  ]},
  { id: 'ai-prompt',      label: 'AI Prompt',      items: [
    { id: 'transcript-prompt', name: 'Transcript', icon: '📝', desc: 'Clean, enhanced transcript with corrected speech errors' },
  ]},
  { id: 'custom',         label: 'Custom',         items: [
    { id: 'custom-define',  name: 'Custom',                    icon: '⚡', desc: 'Define your own processing rules' },
    { id: 'transcript-pv1', name: 'Transcript (Paragraph v1)', icon: '📝', desc: 'Clean, enhanced transcript with corrected speech errors' },
  ]},
];
const allStyles = styleCategories.flatMap(c => c.items);
const currentStyle = computed(() => allStyles.find(s => s.id === style.value) ?? allStyles[0]!);

const styleChips = [
  { id: 'filler',      label: 'filler: strict',     emphasis: true },
  { id: 'terms',       label: 'terms: medium',      emphasis: false },
  { id: 'structure',   label: 'structure: on',      emphasis: true },
  { id: 'key-points',  label: 'key points: on',     emphasis: true },
  { id: 'tone',        label: 'tone: neutral',      emphasis: false },
];

interface Tier { id: string; label: string; sub: string; chip: string; words: string[]; on: typeof tier1 }
const tiers = computed<Tier[]>(() => [
  { id: 't1', label: 'Tier 1 — Acoustic Fillers',  sub: 'Removes hesitation sounds with no semantic meaning', chip: 'red',    words: ['um', 'uh', 'er', 'ah'], on: tier1 },
  { id: 't2', label: 'Tier 2 — Discourse Fillers', sub: 'Removes conversational filler words only when meaning is preserved', chip: 'amber', words: ['you know', 'basically', 'like', 'right', 'essentially'], on: tier2 },
  { id: 't3', label: 'Tier 3 — Redundant Phrases', sub: 'Shortens repetitive phrases without changing meaning', chip: 'teal', words: ["what I'm saying is", 'the thing is', "what we're going to do is"], on: tier3 },
]);

const savedTemplates = [
  { group: 'AI Prompt', items: [{ id: 'ai-transcript', label: 'Transcript' }] },
  { group: 'Custom',    items: [{ id: 'custom-pv1',    label: 'Transcript (Paragraph v1)' }] },
];

const isCustom = computed(() => aiMode.value === 'custom-prompt');
const currentAiMode = computed(() => aiModeOptions.find(o => o.value === aiMode.value));

const customPromptDefault = `You are generating a MIC transcript that must be 100% compliant with the
full Transcript SOP and downstream processing pipeline.

This transcript will flow through:
- Medical Review
- Copy Edit Review
- CMS Publishing
- Captions on Video
- QA

Verbatim-minus-fillers · preserve drug names · annotate uncertainty.`;

function processBatch(): void {
  if (!filesAttached.value) {
    toast.push('Add at least one file', { tone: 'warn' });
    return;
  }
  toast.push('Starting processing…');
  router.push('/p/se_007');
}

function removeAttachment(file: string): void {
  toast.push(`Removed ${file}`, { tone: 'warn' });
}
</script>

<template>
  <main class="upload-page" data-screen-label="Upload">
    <div :style="{ maxWidth: '760px', margin: '0 auto', padding: '44px 24px 64px' }">
      <div :style="{ textAlign: 'center', marginBottom: '28px' }">
        <div :style="{ display: 'inline-flex', alignItems: 'center', gap: '7px', fontSize: '11px', fontWeight: 700, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--fg-link)', marginBottom: '10px' }">
          <span :style="{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--fg-link)' }" /> Media Intelligence Compiler
        </div>
        <h1 :style="{ fontSize: '38px', fontWeight: 800, lineHeight: 1.1, margin: '0 0 12px', color: 'var(--fg1)' }">
          Turn lectures into<br />structured content
        </h1>
        <p :style="{ fontSize: '14px', color: 'var(--fg2)', margin: '0 auto', maxWidth: '480px' }">
          Upload video. We produce a clean verbatim transcript aligned to every slide.
        </p>
      </div>

      <!-- Drop zone -->
      <div
        :class="['upload-dropzone', { 'is-active': filesAttached }]"
        @click="filesAttached = !filesAttached"
      >
        <template v-if="filesAttached">
          <div :style="{ width: '56px', height: '56px', borderRadius: '14px', background: 'rgba(8,97,206,0.18)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '14px' }">
            <Icon name="doc" :size="26" />
          </div>
          <div :style="{ fontSize: '17px', fontWeight: 700, color: 'var(--fg1)' }">5 files selected</div>
          <div :style="{ fontSize: '13px', color: 'var(--fg-link)', marginTop: '4px' }">✓ Ready to process · click to add more</div>
        </template>
        <template v-else>
          <div :style="{ width: '56px', height: '56px', borderRadius: '14px', background: 'var(--surface-muted)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '14px' }">
            <Icon name="download" :size="26" class="upload-dropzone__arrow" />
          </div>
          <div :style="{ fontSize: '17px', fontWeight: 700, color: 'var(--fg1)' }">Drop your files here</div>
          <div :style="{ fontSize: '12px', color: 'var(--fg2)', marginTop: '4px' }">Video, audio, PDF, PPTX, text · multiple files supported</div>
        </template>
      </div>

      <template v-if="filesAttached">
        <div class="upload-attach-note">
          AI will process: <strong>{{ attached[0]!.file }}</strong> + <strong>{{ attached[2]!.file }}</strong> together · <strong>{{ attached[1]!.file }}</strong> for playback
        </div>
        <div v-for="a in attached" :key="a.kind">
          <div class="upload-attach-label">
            {{ a.kind }}
            <span v-if="a.kind === 'Session Manifest'" :style="{ marginLeft: '6px', fontWeight: 600, color: 'var(--fg2)', textTransform: 'none', letterSpacing: 0 }">(extras2) — populates speaker labels, per-slide resources, and publishing links</span>
          </div>
          <div class="upload-attach">
            <Icon :name="a.icon" :size="16" />
            <span class="upload-attach__name">{{ a.file }}</span>
            <span class="upload-attach__size">{{ a.size }}</span>
            <span :class="`chip chip--${a.chip}`" :style="{ fontSize: '10px', padding: '3px 9px' }">{{ a.kind }}</span>
            <button
              class="btn btn--ghost btn--icon btn--sm"
              :data-test-id="`upload-remove-${a.kind.replace(/\s/g, '')}`"
              title="Remove"
              @click="removeAttachment(a.file)"
            ><Icon name="x" :size="11" /></button>
          </div>
        </div>
      </template>

      <!-- Form sections -->
      <div class="upload-form">
        <!-- Processing Pipeline -->
        <div class="upload-field">
          <label class="upload-field__label" :style="{ color: 'var(--color-amber)' }">
            <Icon name="lightning" :size="12" /> Processing Pipeline
          </label>
          <select v-model="pipeline" class="upload-field__select">
            <option value="direct">Direct to AI — file sent directly to Gemini</option>
            <option value="enhanced">AI-Enhanced — transcribe first, then AI refines</option>
          </select>
          <div class="upload-field__help">
            {{ pipeline === 'direct' ? 'Gemini processes the media file directly and returns a formatted transcript' : 'Google STT generates word-level timing; Gemini reconciles to clean prose' }}
          </div>
        </div>

        <!-- AI Processing Mode -->
        <div class="upload-field">
          <label class="upload-field__label" :style="{ color: 'var(--color-blue)' }">
            <Icon name="users" :size="12" /> Select AI Processing Mode
          </label>
          <select v-model="aiMode" class="upload-field__select">
            <option v-for="o in aiModeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
          <div class="upload-field__help">{{ currentAiMode?.help }}</div>
        </div>

        <!-- AI Model -->
        <div class="upload-field">
          <label class="upload-field__label" :style="{ color: '#C5478D' }">
            <Icon name="globe" :size="12" /> AI Model
          </label>
          <select v-model="model" class="upload-field__select">
            <option value="gemini-25-pro">Gemini 2.5 Pro (recommended)</option>
            <option value="gemini-25-flash">Gemini 2.5 Flash (faster, lower quality)</option>
            <option value="gpt-5">GPT-5</option>
            <option value="claude-opus">Claude Opus 4.5</option>
          </select>
        </div>

        <!-- Custom Prompt mode -->
        <template v-if="isCustom">
          <div class="upload-field">
            <label class="upload-field__label" :style="{ color: 'var(--color-green)' }">
              <Icon name="save" :size="12" /> Load Saved Prompt Template
              <span :style="{ marginLeft: '8px', fontSize: '9px', color: 'var(--fg2)', fontWeight: 600, padding: '2px 6px', background: 'var(--surface-muted)', borderRadius: '4px', textTransform: 'none', letterSpacing: 0 }">optional</span>
            </label>
            <select
              v-model="savedTpl"
              class="upload-field__select"
              :style="savedTpl ? { borderColor: 'var(--color-green)', boxShadow: '0 0 0 2px rgba(0,125,97,0.10)' } : undefined"
            >
              <option value="">— pick a saved template to load below —</option>
              <optgroup v-for="g in savedTemplates" :key="g.group" :label="g.group">
                <option v-for="it in g.items" :key="it.id" :value="it.id">{{ it.label }}</option>
              </optgroup>
            </select>
            <div class="upload-field__help">Loads the saved prompt into the textarea below. Edit freely after loading.</div>
          </div>
          <div class="upload-field">
            <label class="upload-field__label" :style="{ color: 'var(--color-blue)' }">
              <Icon name="edit" :size="12" /> Custom Prompt
            </label>
            <textarea
              class="upload-field__select"
              :rows="10"
              :value="customPromptDefault"
              :style="{ fontFamily: 'var(--font-mono)', fontSize: '12.5px', lineHeight: 1.55, padding: '12px 14px', resize: 'vertical' }"
            />
          </div>
        </template>

        <!-- STT -->
        <div :class="['upload-field', { 'upload-field--disabled': pipeline !== 'enhanced' }]">
          <label class="upload-field__label">
            <Icon name="speaker" :size="12" /> Speech-to-Text (STT)
            <span :style="{ marginLeft: 'auto', fontSize: '10px', color: 'var(--fg2)', textTransform: 'none', letterSpacing: 0, fontWeight: 500 }">
              Applied when Processing Pipeline = AI-Enhanced
            </span>
          </label>
          <select v-model="stt" class="upload-field__select" :disabled="pipeline !== 'enhanced'">
            <option value="google_latest_long">Google STT v3 · latest_long</option>
            <option value="google_phone">Google STT · phone_call</option>
          </select>
        </div>

        <!-- Processing Style card -->
        <div class="upload-style-card">
          <div class="upload-style-card__head">
            <label class="upload-field__label" :style="{ color: 'var(--fg2)', marginBottom: 0 }">
              <Icon name="settings" :size="12" /> Processing Style
              <span class="chip chip--ghost" :style="{ marginLeft: '8px', fontSize: '9px' }">v3.10</span>
            </label>
            <button class="btn btn--ghost btn--icon btn--sm" :aria-expanded="styleOpen" @click="styleOpen = !styleOpen">
              <Icon :name="styleOpen ? 'chevron-down' : 'chevron-right'" :size="14" />
            </button>
          </div>
          <button class="upload-style-current" @click="styleOpen = !styleOpen">
            <span :style="{ fontSize: '22px' }">{{ currentStyle.icon }}</span>
            <span>
              <div :style="{ fontSize: '14px', fontWeight: 700, color: 'var(--fg1)' }">{{ currentStyle.name }}</div>
              <div :style="{ fontSize: '12px', color: 'var(--fg2)', marginTop: '1px' }">{{ currentStyle.desc }}</div>
            </span>
            <Icon :name="styleOpen ? 'chevron-down' : 'chevron-right'" :size="14" :style="{ marginLeft: 'auto', color: 'var(--fg2)' }" />
          </button>

          <div v-if="styleOpen" class="upload-style-list">
            <div v-for="cat in styleCategories" :key="cat.id">
              <div class="upload-style-cat">{{ cat.label }}</div>
              <button
                v-for="it in cat.items"
                :key="it.id"
                :class="['upload-style-item', { 'is-selected': it.id === style }]"
                @click="style = it.id"
              >
                <span :style="{ fontSize: '18px' }">{{ it.icon }}</span>
                <span>
                  <div :style="{ fontSize: '13.5px', fontWeight: 700, color: 'var(--fg1)' }">{{ it.name }}</div>
                  <div :style="{ fontSize: '11.5px', color: 'var(--fg2)' }">{{ it.desc }}</div>
                </span>
                <Icon v-if="it.id === style" name="check" :size="14" class="upload-style-item__chk" />
              </button>
            </div>

            <div class="upload-style-chips">
              <span
                v-for="c in styleChips"
                :key="c.id"
                :class="['upload-style-chip', { 'is-emphasis': c.emphasis }]"
              >{{ c.label }}</span>
            </div>
          </div>
        </div>

        <!-- IIL card -->
        <div :class="['upload-iil-card', { 'is-open': iilOpen }]">
          <div class="upload-iil-card__head">
            <button class="upload-iil-card__title" @click="iilOpen = !iilOpen">
              <span :style="{ fontSize: '22px' }">🧠</span>
              <span>
                <div :style="{ fontSize: '14px', fontWeight: 700, color: 'var(--color-blue)' }">Instructor Intelligence Layer</div>
                <div :style="{ fontSize: '11px', color: 'var(--fg2)', marginTop: '2px' }">
                  {{ iilOpen ? 'Click to collapse' : 'Click to expand' }} · configure tier rules {{ iilOpen ? 'below' : '' }}
                </div>
              </span>
              <Icon :name="iilOpen ? 'chevron-down' : 'chevron-right'" :size="14" :style="{ marginLeft: 'auto', color: 'var(--fg2)' }" />
            </button>
            <button
              class="upload-iil__toggle"
              :aria-pressed="iilEnabled"
              title="Toggle IIL"
              @click.stop="iilEnabled = !iilEnabled"
            >
              <span :class="['upload-iil__knob', { 'is-on': iilEnabled }]" />
            </button>
          </div>
          <div v-if="iilOpen" class="upload-iil-tiers">
            <div v-for="t in tiers" :key="t.id" class="upload-iil-tier">
              <div class="upload-iil-tier__head">
                <div>
                  <div :class="['upload-iil-tier__label', `upload-iil-tier__label--${t.chip}`]">{{ t.label }}</div>
                  <div class="upload-iil-tier__sub">{{ t.sub }}</div>
                </div>
                <button
                  class="upload-iil__toggle"
                  :aria-pressed="t.on.value"
                  @click="t.on.value = !t.on.value"
                >
                  <span :class="['upload-iil__knob', { 'is-on': t.on.value }]" />
                </button>
              </div>
              <div class="upload-iil-words">
                <span
                  v-for="w in t.words"
                  :key="w"
                  :class="['upload-iil-word', `upload-iil-word--${t.chip}`]"
                >{{ w }}</span>
              </div>
            </div>
          </div>
        </div>

        <button class="btn btn--primary upload-process" data-test-id="upload-process" @click="processBatch">
          Process &nbsp;→
        </button>
        <p :style="{ textAlign: 'center', fontSize: '11px', color: 'var(--fg2)', marginTop: '10px' }">
          Processing may take longer depending on file size
        </p>
      </div>
    </div>
  </main>
</template>
