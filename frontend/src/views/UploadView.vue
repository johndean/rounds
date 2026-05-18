<script setup lang="ts">
/**
 * Upload — /upload
 *
 * Visual layout ported 1:1 from docs/port-source/upload.jsx. Functionally
 * wired through to the real backend:
 *
 *   1. User picks files via <input type="file" multiple> (or drops on the zone)
 *   2. Process click:
 *      a. POST /v1/sessions          → returns session UUID
 *      b. For each file:
 *           POST /v1/gcs/upload-url  → signed PUT URL + canonical gcs_uri
 *           PUT  <signed_url>        → bytes go straight to GCS
 *      c. POST /v1/gcs/upload-complete (R7 scope-validated, writes Source rows)
 *      d. Router push to /p/<session_id> for ingest progress (Phase 6)
 */
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import Icon from '@/components/shared/Icon.vue';
import { toast } from '@/composables/useToast';
import { sessions as sessionsApi, gcs as gcsApi } from '@/services/api';
import { ApiError } from '@/services/http';

const router = useRouter();

// ── Form state ────────────────────────────────────────────────────────
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

// ── Real file-picker state ───────────────────────────────────────────
interface Attached {
  file: File;
  kind: string;
  role: 'video' | 'audio' | 'slide' | 'manifest' | 'chat' | 'other';
  size: string;
  chip: 'blue' | 'amber' | 'teal' | 'ghost';
  icon: string;
}

const attached = ref<Attached[]>([]);
const filesAttached = computed(() => attached.value.length > 0);
const pickerRef = ref<HTMLInputElement | null>(null);
const dragOver = ref(false);
const uploading = ref(false);
const progress = ref<{ done: number; total: number }>({ done: 0, total: 0 });

function inferRole(name: string): Attached['role'] {
  const lower = name.toLowerCase();
  const ext = lower.split('.').pop() || '';
  if (['mp4', 'mov', 'mkv', 'webm', 'avi', 'm4v'].includes(ext)) return 'video';
  if (['mp3', 'm4a', 'wav', 'ogg', 'flac', 'aac'].includes(ext)) return 'audio';
  if (['pdf', 'pptx', 'ppt'].includes(ext)) return 'slide';
  if (ext === 'txt') {
    if (/extras2|_manifest|^manifest_/i.test(name)) return 'manifest';
    return 'chat';
  }
  return 'other';
}

function buildAttached(file: File): Attached {
  const role = inferRole(file.name);
  const meta: Record<Attached['role'], { kind: string; chip: Attached['chip']; icon: string }> = {
    video:    { kind: 'Video Playback',   chip: 'blue',  icon: 'play'    },
    audio:    { kind: 'AI Transcription', chip: 'blue',  icon: 'speaker' },
    slide:    { kind: 'Slide Extraction', chip: 'amber', icon: 'slide'   },
    manifest: { kind: 'Session Manifest', chip: 'blue',  icon: 'doc'     },
    chat:     { kind: 'Chat Transcript',  chip: 'blue',  icon: 'message' },
    other:    { kind: 'Other',            chip: 'ghost', icon: 'doc'     },
  };
  return { file, role, size: humanSize(file.size), ...meta[role] };
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function openPicker(): void { pickerRef.value?.click(); }

function onPick(e: Event): void {
  const input = e.target as HTMLInputElement;
  if (!input.files) return;
  ingestFiles(Array.from(input.files));
  input.value = '';
}

function onDrop(e: DragEvent): void {
  e.preventDefault();
  dragOver.value = false;
  if (!e.dataTransfer) return;
  ingestFiles(Array.from(e.dataTransfer.files));
}

function ingestFiles(files: File[]): void {
  // Dedupe by name+size; keep first occurrence
  const seen = new Set(attached.value.map((a) => `${a.file.name}::${a.file.size}`));
  for (const f of files) {
    const key = `${f.name}::${f.size}`;
    if (seen.has(key)) continue;
    seen.add(key);
    attached.value.push(buildAttached(f));
  }
}

function removeAttachment(idx: number): void {
  const name = attached.value[idx]?.file.name;
  attached.value.splice(idx, 1);
  if (name) toast.push(`Removed ${name}`, { tone: 'warn' });
}

// ── Process pipeline ─────────────────────────────────────────────────
function genCode(): string {
  const d = new Date();
  const yy = String(d.getFullYear()).slice(-2);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const stem = (attached.value[0]?.file.name || 'session').split('.')[0]!.slice(0, 24);
  return `${mm}${dd}${yy}_${stem.replace(/[^A-Za-z0-9_-]/g, '_')}`;
}

async function processBatch(): Promise<void> {
  if (!filesAttached.value) {
    toast.push('Add at least one file', { tone: 'warn' });
    return;
  }
  if (uploading.value) return;
  uploading.value = true;
  progress.value = { done: 0, total: attached.value.length };
  const code = genCode();
  try {
    // 1) Create session
    toast.push(`Creating session ${code}…`, { tone: 'info' });
    const session = await sessionsApi.create({
      code,
      title: code.replace(/_/g, ' '),
      presenter: '',
      duration_sec: null,
      attendee_count: null,
      taxonomy: [],
    } as never);
    const sessionId = (session as { id: string }).id;

    // 2) Per-file: signed-URL → PUT
    const completeFiles: Array<{ gcs_uri: string; role: string; filename: string; content_type: string; size_bytes: number }> = [];
    for (let i = 0; i < attached.value.length; i++) {
      const a = attached.value[i]!;
      const { signed_url, gcs_uri } = await gcsApi.signedUrl(sessionId, a.file.name, a.role);
      const put = await fetch(signed_url, {
        method: 'PUT',
        headers: { 'Content-Type': a.file.type || 'application/octet-stream' },
        body: a.file,
      });
      if (!put.ok) throw new Error(`GCS PUT failed (${put.status}) for ${a.file.name}`);
      completeFiles.push({
        gcs_uri,
        role: a.role,
        filename: a.file.name,
        content_type: a.file.type || 'application/octet-stream',
        size_bytes: a.file.size,
      });
      progress.value = { done: i + 1, total: attached.value.length };
    }

    // 3) upload-complete (R7 scope-validated, writes Source rows)
    await gcsApi.uploadComplete(sessionId, completeFiles);

    // 4) Navigate to processing page
    toast.push(`Uploaded ${completeFiles.length} file${completeFiles.length === 1 ? '' : 's'}`, { tone: 'success' });
    router.push(`/p/${sessionId}`);
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status}: ${e.message}` : e instanceof Error ? e.message : 'Upload failed';
    toast.push(msg, { tone: 'error', duration: 8000 });
  } finally {
    uploading.value = false;
  }
}

// ── Style + AI mode options (unchanged from prior port) ─────────────
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
</script>

<template>
  <main class="upload-page" data-screen-label="Upload">
    <input
      ref="pickerRef"
      type="file"
      multiple
      :style="{ display: 'none' }"
      data-test-id="upload-picker"
      @change="onPick"
    />
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
        :class="['upload-dropzone', { 'is-active': filesAttached, 'is-drag': dragOver }]"
        data-test-id="upload-dropzone"
        @click="openPicker"
        @dragover.prevent="dragOver = true"
        @dragleave.prevent="dragOver = false"
        @drop="onDrop"
      >
        <template v-if="filesAttached">
          <div :style="{ width: '56px', height: '56px', borderRadius: '14px', background: 'rgba(8,97,206,0.18)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '14px' }">
            <Icon name="doc" :size="26" />
          </div>
          <div :style="{ fontSize: '17px', fontWeight: 700, color: 'var(--fg1)' }">{{ attached.length }} file{{ attached.length === 1 ? '' : 's' }} selected</div>
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
          {{ attached.length }} file{{ attached.length === 1 ? '' : 's' }} ready · roles auto-detected from filename
        </div>
        <div v-for="(a, i) in attached" :key="`${a.file.name}::${a.file.size}`">
          <div class="upload-attach-label">
            {{ a.kind }}
            <span v-if="a.role === 'manifest'" :style="{ marginLeft: '6px', fontWeight: 600, color: 'var(--fg2)', textTransform: 'none', letterSpacing: 0 }">(extras2) — populates speaker labels, per-slide resources, and publishing links</span>
          </div>
          <div class="upload-attach">
            <Icon :name="a.icon" :size="16" />
            <span class="upload-attach__name">{{ a.file.name }}</span>
            <span class="upload-attach__size">{{ a.size }}</span>
            <span :class="`chip chip--${a.chip}`" :style="{ fontSize: '10px', padding: '3px 9px' }">{{ a.kind }}</span>
            <button
              class="btn btn--ghost btn--icon btn--sm"
              :data-test-id="`upload-remove-${i}`"
              title="Remove"
              :disabled="uploading"
              @click.stop="removeAttachment(i)"
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

        <button
          class="btn btn--primary upload-process"
          data-test-id="upload-process"
          :disabled="uploading || !filesAttached"
          @click="processBatch"
        >
          <template v-if="uploading">
            Uploading {{ progress.done }}/{{ progress.total }}…
          </template>
          <template v-else>
            Process &nbsp;→
          </template>
        </button>
        <p :style="{ textAlign: 'center', fontSize: '11px', color: 'var(--fg2)', marginTop: '10px' }">
          {{ uploading ? 'Streaming bytes to GCS — do not close this tab' : 'Processing may take longer depending on file size' }}
        </p>
      </div>
    </div>
  </main>
</template>
