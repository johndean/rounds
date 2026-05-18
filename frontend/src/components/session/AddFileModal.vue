<script setup lang="ts">
/**
 * AddFileModal — port of MIC AddFileModal.vue (892 LOC), trimmed to Rounds'
 * native design system (`card`, `btn`, `chip` classes).
 *
 * UX:
 *   1. Idle      — dropzone with drag-drop or click-to-browse
 *   2. Uploading — spinner + optional progress bar
 *   3. Conflict  — 409 surface for slides (deck summary) / chat / manifest
 *   4. Done      — checkmark + auto-close
 *   5. Error     — message + Retry
 *
 * Transports:
 *   • railway — multipart POST to /v1/sessions/{id}/add/{type}
 *   • gcs     — POST /add/signed-url → browser PUT → POST /add/{type} with {gcs_uri}
 *
 * The transport is sourced from org_settings `upload_backend` (loaded on mount).
 */
import { computed, onMounted, ref, watch } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { settingsApi } from '@/services/api';
import { ApiError, http } from '@/services/http';

const props = defineProps<{
  open: boolean;
  sessionId: string;
  type: 'slides' | 'chat' | 'manifest' | 'bios';
  hasExisting: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'success', payload: { type: string; data: unknown }): void;
}>();

// ── Per-type metadata ─────────────────────────────────────────────────
interface TypeMeta {
  label: string;
  icon: string;
  accept: string;
  help: string;
  hint: string;
}
const TYPE_META: Record<string, TypeMeta> = {
  slides: {
    label: 'Slides',
    icon: 'slide',
    accept: 'application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation,.pdf,.pptx',
    help: 'Upload a PDF or PPTX slide deck.',
    hint: 'PDF or PPTX accepted',
  },
  chat: {
    label: 'Chat log',
    icon: 'message',
    accept: 'text/plain,text/csv,.txt,.csv',
    help: 'Upload a Zoom/webinar chat export (.txt).',
    hint: '.txt accepted',
  },
  manifest: {
    label: 'Session manifest',
    icon: 'doc',
    accept: 'text/plain,.txt',
    help: 'Upload an extras2 session manifest (.txt).',
    hint: '.txt accepted',
  },
  bios: {
    label: 'Speaker bios',
    icon: 'user',
    accept: 'text/plain,.txt',
    help: 'Speaker bios are inline-edited on the Speakers panel. This dialog is informational only.',
    hint: 'Edit bios inline on the Speakers panel',
  },
};

const meta = computed<TypeMeta>(() => TYPE_META[props.type] || TYPE_META.slides);

// ── State machine ─────────────────────────────────────────────────────
type Phase = 'idle' | 'uploading' | 'committing' | 'conflict' | 'done' | 'error';
const phase = ref<Phase>('idle');
const picked = ref<File | null>(null);
const dropOver = ref(false);
const errorMsg = ref<string>('');
const progress = ref<number>(0); // 0..100
const conflictDetails = ref<Record<string, unknown> | null>(null);
const stagingGcsUri = ref<string | null>(null);
const stagingFilename = ref<string | null>(null);
const selectedSlides = ref<Set<number>>(new Set());
const uploadBackend = ref<'railway' | 'gcs'>('railway');

onMounted(async () => {
  try {
    const s = (await settingsApi.list()) as Record<string, unknown>;
    if (s.upload_backend === 'gcs') uploadBackend.value = 'gcs';
  } catch {
    /* default railway */
  }
});

watch(() => props.open, (v) => {
  if (v) reset();
});

function reset(): void {
  phase.value = 'idle';
  picked.value = null;
  dropOver.value = false;
  errorMsg.value = '';
  progress.value = 0;
  conflictDetails.value = null;
  stagingGcsUri.value = null;
  stagingFilename.value = null;
  selectedSlides.value = new Set();
}

function close(): void {
  emit('close');
}

// ── File picking ──────────────────────────────────────────────────────
function onPick(e: Event): void {
  const f = (e.target as HTMLInputElement).files?.[0];
  if (f) picked.value = f;
}

function onDrop(e: DragEvent): void {
  e.preventDefault();
  dropOver.value = false;
  const f = e.dataTransfer?.files?.[0];
  if (f) picked.value = f;
}

function onDragOver(e: DragEvent): void { e.preventDefault(); dropOver.value = true; }
function onDragLeave(): void { dropOver.value = false; }

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

// ── Upload flow ───────────────────────────────────────────────────────
async function upload(extraMode?: string): Promise<void> {
  if (!picked.value || props.type === 'bios') return;
  errorMsg.value = '';
  phase.value = 'uploading';
  progress.value = 0;

  try {
    let gcs_uri: string;
    if (uploadBackend.value === 'gcs') {
      // Step 1: signed URL
      const { signed_url, gcs_uri: uri } = await http<{ signed_url: string; gcs_uri: string }>(
        `/v1/sessions/${encodeURIComponent(props.sessionId)}/add/signed-url`,
        {
          body: { filename: picked.value.name, mime_type: picked.value.type || 'application/octet-stream', type: props.type },
          method: 'POST',
        },
      );
      // Step 2: PUT directly to GCS with progress
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('PUT', signed_url);
        xhr.setRequestHeader('Content-Type', picked.value!.type || 'application/octet-stream');
        xhr.upload.onprogress = (ev) => {
          if (ev.lengthComputable) progress.value = Math.round((ev.loaded / ev.total) * 100);
        };
        xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`GCS PUT ${xhr.status}`)));
        xhr.onerror = () => reject(new Error('GCS PUT network error'));
        xhr.send(picked.value!);
      });
      gcs_uri = uri;
      stagingGcsUri.value = uri;
      stagingFilename.value = picked.value.name;
      phase.value = 'committing';

      // Step 3: commit
      await commit(gcs_uri, extraMode);
    } else {
      // Railway: multipart POST
      const fd = new FormData();
      const fieldName = props.type === 'slides' ? 'slide_file' : props.type === 'chat' ? 'chat_file' : 'manifest_file';
      fd.append(fieldName, picked.value);
      phase.value = 'committing';
      const qs = extraMode ? `?mode=${extraMode}` : '';
      const resp = await fetch(`/v1/sessions/${encodeURIComponent(props.sessionId)}/add/${props.type}${qs}`, {
        method: 'POST',
        body: fd,
        headers: { Authorization: `Bearer ${localStorage.getItem('rounds_jwt_v1') || ''}` },
      });
      const json = await resp.json().catch(() => null);
      if (!resp.ok) {
        const env = (json && typeof json === 'object' && 'error' in json) ? (json as { error?: { code?: string; message?: string; details?: Record<string, unknown> } }).error : null;
        if (resp.status === 409 && env?.details) {
          conflictDetails.value = env.details;
          stagingGcsUri.value = (env.details.gcs_uri as string) || null;
          stagingFilename.value = (env.details.new_filename as string) || (env.details.new_deck_filename as string) || picked.value.name;
          phase.value = 'conflict';
          return;
        }
        throw new Error(env?.message || `Upload failed: ${resp.status}`);
      }
      phase.value = 'done';
      emit('success', { type: props.type, data: (json && typeof json === 'object' && 'data' in json) ? (json as { data: unknown }).data : json });
      setTimeout(close, 900);
    }
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      const body = err.body as { details?: Record<string, unknown>; error?: { details?: Record<string, unknown> } } | undefined;
      const d = body?.details || body?.error?.details;
      if (d) {
        conflictDetails.value = d;
        stagingGcsUri.value = (d.gcs_uri as string) || null;
        stagingFilename.value = (d.new_filename as string) || (d.new_deck_filename as string) || (picked.value?.name ?? null);
        phase.value = 'conflict';
        return;
      }
    }
    errorMsg.value = err instanceof Error ? err.message : 'Upload failed';
    phase.value = 'error';
  }
}

async function commit(gcs_uri: string, extraMode?: string, extraBody?: Record<string, unknown>): Promise<void> {
  try {
    const qs = extraMode ? `?mode=${extraMode}` : '';
    const data = await http(`/v1/sessions/${encodeURIComponent(props.sessionId)}/add/${props.type}${qs}`, {
      body: { gcs_uri, ...(extraBody || {}) },
      method: 'POST',
    });
    phase.value = 'done';
    emit('success', { type: props.type, data });
    setTimeout(close, 900);
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      const body = err.body as { details?: Record<string, unknown>; error?: { details?: Record<string, unknown> } } | undefined;
      const d = body?.details || body?.error?.details;
      if (d) {
        conflictDetails.value = d;
        phase.value = 'conflict';
        return;
      }
    }
    errorMsg.value = err instanceof Error ? err.message : 'Commit failed';
    phase.value = 'error';
  }
}

// ── Conflict-resolution actions ───────────────────────────────────────
async function chooseSlideMode(mode: 'replace' | 'append' | 'replace_selected'): Promise<void> {
  if (!stagingGcsUri.value) return;
  phase.value = 'committing';
  const extra = mode === 'replace_selected' ? { slide_numbers: [...selectedSlides.value] } : undefined;
  await commit(stagingGcsUri.value, mode, extra);
}

async function chooseChatMode(replace: boolean): Promise<void> {
  if (!stagingGcsUri.value) return;
  if (!replace) { close(); return; }
  phase.value = 'committing';
  try {
    const data = await http(`/v1/sessions/${encodeURIComponent(props.sessionId)}/add/chat?confirm=true`, {
      body: { gcs_uri: stagingGcsUri.value },
      method: 'POST',
    });
    phase.value = 'done';
    emit('success', { type: 'chat', data });
    setTimeout(close, 900);
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : 'Commit failed';
    phase.value = 'error';
  }
}

async function chooseManifestMode(mode: 'use_new' | 'keep_current'): Promise<void> {
  if (!stagingGcsUri.value) return;
  phase.value = 'committing';
  await commit(stagingGcsUri.value, mode);
}

function toggleSlide(n: number): void {
  const s = new Set(selectedSlides.value);
  if (s.has(n)) s.delete(n);
  else s.add(n);
  selectedSlides.value = s;
}

// ── Conflict pane helpers ─────────────────────────────────────────────
const currentPages = computed<Array<{ page_number: number; thumbnail_url: string }>>(
  () => (conflictDetails.value?.current_pages as Array<{ page_number: number; thumbnail_url: string }>) || [],
);
const newPages = computed<Array<{ page_number: number; thumbnail_url: string }>>(
  () => (conflictDetails.value?.new_pages as Array<{ page_number: number; thumbnail_url: string }>) || [],
);
const existingCount = computed<number>(() => Number(conflictDetails.value?.existing_count ?? 0));
const newCount = computed<number>(() => Number(conflictDetails.value?.new_count ?? 0));
const currentPreview = computed<Array<{ speaker: string; message: string }>>(
  () => (conflictDetails.value?.current_preview as Array<{ speaker: string; message: string }>) || [],
);
const newPreview = computed<Array<{ speaker: string; message: string }>>(
  () => (conflictDetails.value?.new_preview as Array<{ speaker: string; message: string }>) || [],
);
const currentSummary = computed<Record<string, unknown>>(
  () => (conflictDetails.value?.current_summary as Record<string, unknown>) || {},
);
const newSummary = computed<Record<string, unknown>>(
  () => (conflictDetails.value?.new_summary as Record<string, unknown>) || {},
);

function summarizeChat(list: Array<{ speaker?: string; message?: string }>): string {
  if (!list || list.length === 0) return '—';
  return list.slice(0, 10).map((m) => {
    const spk = (m.speaker || '—').slice(0, 24);
    const msg = (m.message || '').slice(0, 60);
    return `${spk}: ${msg}`;
  }).join('\n');
}

function summarizeManifest(obj: Record<string, unknown>): string {
  if (!obj || Object.keys(obj).length === 0) return '—';
  const fields = ['code', 'title_long', 'title_short', 'ce_broker_id', 'class_id', 'speaker_count', 'resource_count'];
  return fields.filter((k) => obj[k] != null && obj[k] !== '').map((k) => `${k}: ${obj[k]}`).join('\n');
}
</script>

<template>
  <div
    v-if="open"
    class="afm-overlay"
    role="dialog"
    aria-modal="true"
    :style="{ position: 'fixed', inset: 0, background: 'rgba(8, 14, 24, 0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }"
    @click.self="close"
    @keydown.esc="close"
  >
    <div
      class="afm-modal card"
      :style="{ background: 'var(--surface)', width: phase === 'conflict' && type === 'slides' ? '900px' : '560px', maxWidth: '95vw', maxHeight: '90vh', overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: 0, borderRadius: '8px', boxShadow: '0 12px 32px rgba(8, 14, 24, 0.3)' }"
    >
      <!-- Header -->
      <div :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '1px solid var(--border-subtle)' }">
        <div :style="{ display: 'flex', alignItems: 'center', gap: '10px' }">
          <Icon :name="meta.icon" :size="16" />
          <strong :style="{ fontSize: '14px', color: 'var(--fg1)' }">{{ hasExisting ? 'Update' : 'Add' }} {{ meta.label }}</strong>
        </div>
        <button class="btn btn--ghost btn--icon btn--sm" title="Close" @click="close"><Icon name="x" :size="12" /></button>
      </div>

      <!-- Body -->
      <div :style="{ flex: 1, overflowY: 'auto', padding: '18px' }">
        <!-- Bios: informational only -->
        <template v-if="type === 'bios'">
          <div :style="{ padding: '20px', textAlign: 'center', color: 'var(--fg2)', fontSize: '13px', lineHeight: 1.6 }">
            {{ meta.help }}<br>
            Open the session editor and edit each speaker's bio in the Speakers panel.
          </div>
        </template>

        <!-- Idle -->
        <template v-else-if="phase === 'idle'">
          <p :style="{ fontSize: '12.5px', color: 'var(--fg2)', margin: '0 0 14px', lineHeight: 1.5 }">{{ meta.help }}</p>
          <label
            :class="['afm-dropzone', { 'afm-drop-over': dropOver, 'afm-drop-filled': picked }]"
            :style="{
              display: 'block',
              border: `2px dashed ${dropOver ? 'var(--color-green, #0d7a5e)' : 'var(--border-subtle)'}`,
              borderRadius: '6px',
              background: dropOver ? 'rgba(13, 122, 94, 0.05)' : 'var(--surface-bg)',
              padding: '28px 16px',
              textAlign: 'center',
              cursor: 'pointer',
            }"
            @drop="onDrop"
            @dragover="onDragOver"
            @dragleave="onDragLeave"
          >
            <input type="file" :accept="meta.accept" :style="{ display: 'none' }" @change="onPick" />
            <div :style="{ fontSize: '24px', marginBottom: '8px' }">📥</div>
            <div :style="{ fontSize: '13px', fontWeight: 600, color: 'var(--fg1)', marginBottom: '4px' }">
              {{ picked ? picked.name : 'Drop file here or click to browse' }}
            </div>
            <div :style="{ fontSize: '11px', color: 'var(--fg2)' }">
              <template v-if="picked">{{ fmtSize(picked.size) }} · {{ picked.type || 'unknown' }}</template>
              <template v-else>{{ meta.hint }}</template>
            </div>
          </label>
        </template>

        <!-- Uploading / Committing -->
        <template v-else-if="phase === 'uploading' || phase === 'committing'">
          <div :style="{ padding: '20px 0', textAlign: 'center' }">
            <div
              :style="{
                width: '32px', height: '32px', borderRadius: '50%', margin: '0 auto 14px',
                border: '3px solid var(--border-subtle)', borderTopColor: 'var(--color-green, #0d7a5e)',
                animation: 'afm-spin 0.8s linear infinite',
              }"
            />
            <div :style="{ fontSize: '13px', color: 'var(--fg1)', fontWeight: 600 }">
              {{ phase === 'uploading' ? `Uploading to cloud storage…` : 'Committing on server…' }}
            </div>
            <div v-if="phase === 'uploading' && progress > 0" :style="{ marginTop: '12px', maxWidth: '320px', marginLeft: 'auto', marginRight: 'auto' }">
              <div :style="{ width: '100%', height: '6px', background: 'var(--surface-bg)', borderRadius: '3px', overflow: 'hidden' }">
                <div :style="{ height: '100%', background: 'var(--color-green, #0d7a5e)', width: `${progress}%`, transition: 'width 0.2s' }" />
              </div>
              <div :style="{ marginTop: '6px', fontSize: '11px', color: 'var(--fg2)' }">{{ progress }}%</div>
            </div>
          </div>
        </template>

        <!-- Done -->
        <template v-else-if="phase === 'done'">
          <div :style="{ padding: '20px 0', textAlign: 'center', color: 'var(--color-green, #0d7a5e)' }">
            <Icon name="check" :size="32" />
            <div :style="{ fontSize: '13px', fontWeight: 600, marginTop: '8px', color: 'var(--fg1)' }">
              {{ meta.label }} saved
            </div>
          </div>
        </template>

        <!-- Error -->
        <template v-else-if="phase === 'error'">
          <div :style="{ padding: '20px', textAlign: 'center' }">
            <Icon name="alert" :size="24" />
            <div :style="{ fontSize: '13px', color: 'var(--color-red)', fontWeight: 600, marginTop: '8px', marginBottom: '6px' }">Upload failed</div>
            <div :style="{ fontSize: '12px', color: 'var(--fg2)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }">{{ errorMsg }}</div>
          </div>
        </template>

        <!-- Conflict: slides -->
        <template v-else-if="phase === 'conflict' && type === 'slides'">
          <div :style="{ fontSize: '12.5px', color: 'var(--fg2)', marginBottom: '10px', lineHeight: 1.5 }">
            This session already has slides. Choose how to merge the new deck:
          </div>
          <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }">
            <div>
              <div :style="{ fontSize: '11px', fontWeight: 700, color: 'var(--fg2)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '6px' }">
                Current ({{ currentPages.length || 0 }} slides)
              </div>
              <div :style="{ maxHeight: '260px', overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: '5px', padding: '6px' }">
                <label
                  v-for="p in currentPages"
                  :key="`cur-${p.page_number}`"
                  :style="{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px', cursor: 'pointer' }"
                >
                  <input type="checkbox" :checked="selectedSlides.has(p.page_number)" @change="toggleSlide(p.page_number)" />
                  <img v-if="p.thumbnail_url" :src="p.thumbnail_url" :style="{ width: '64px', maxHeight: '80px', objectFit: 'contain', background: '#fff', border: '1px solid var(--border-subtle)' }" />
                  <span :style="{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--fg2)' }">{{ String(p.page_number).padStart(2, '0') }}</span>
                </label>
                <div v-if="currentPages.length === 0" :style="{ padding: '12px', color: 'var(--fg2)', fontSize: '11px', textAlign: 'center' }">(no thumbnails)</div>
              </div>
            </div>
            <div>
              <div :style="{ fontSize: '11px', fontWeight: 700, color: 'var(--fg2)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '6px' }">
                New: {{ stagingFilename }} ({{ newPages.length || conflictDetails?.new_deck_pages || 0 }} pages)
              </div>
              <div :style="{ maxHeight: '260px', overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: '5px', padding: '6px' }">
                <div v-for="p in newPages" :key="`new-${p.page_number}`" :style="{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px' }">
                  <img v-if="p.thumbnail_url" :src="p.thumbnail_url" :style="{ width: '64px', maxHeight: '80px', objectFit: 'contain', background: '#fff', border: '1px solid var(--border-subtle)' }" />
                  <span :style="{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--fg2)' }">{{ String(p.page_number).padStart(2, '0') }}</span>
                </div>
                <div v-if="newPages.length === 0" :style="{ padding: '12px', color: 'var(--fg2)', fontSize: '11px', textAlign: 'center' }">(no thumbnails)</div>
              </div>
            </div>
          </div>
          <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }">
            <button class="btn btn--secondary btn--sm" @click="close">↩ Keep current</button>
            <button class="btn btn--secondary btn--sm" :style="{ borderColor: 'var(--color-red)', color: 'var(--color-red)' }" @click="chooseSlideMode('replace')">🗑 Replace ALL</button>
            <button class="btn btn--secondary btn--sm" @click="chooseSlideMode('append')">➕ Append</button>
            <button class="btn btn--primary btn--sm" :disabled="selectedSlides.size === 0" @click="chooseSlideMode('replace_selected')">↔ Replace selected ({{ selectedSlides.size }})</button>
          </div>
        </template>

        <!-- Conflict: chat -->
        <template v-else-if="phase === 'conflict' && type === 'chat'">
          <div :style="{ fontSize: '12.5px', color: 'var(--fg2)', marginBottom: '10px', lineHeight: 1.5 }">
            This session already has {{ existingCount }} chat message(s). New file has {{ newCount }}.
          </div>
          <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }">
            <div>
              <div :style="{ fontSize: '11px', fontWeight: 700, color: 'var(--fg2)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '4px' }">Current ({{ existingCount }} msgs)</div>
              <pre :style="{ background: 'var(--surface-bg)', padding: '8px', fontSize: '11px', maxHeight: '180px', overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: '4px', whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }">{{ summarizeChat(currentPreview) }}</pre>
            </div>
            <div>
              <div :style="{ fontSize: '11px', fontWeight: 700, color: 'var(--fg2)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '4px' }">New ({{ newCount }} msgs)</div>
              <pre :style="{ background: 'var(--surface-bg)', padding: '8px', fontSize: '11px', maxHeight: '180px', overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: '4px', whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }">{{ summarizeChat(newPreview) }}</pre>
            </div>
          </div>
          <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }">
            <button class="btn btn--secondary btn--sm" @click="chooseChatMode(false)">↩ Keep current</button>
            <button class="btn btn--primary btn--sm" :style="{ background: 'var(--color-red)', borderColor: 'var(--color-red)' }" @click="chooseChatMode(true)">✓ Use new chat ({{ newCount }})</button>
          </div>
        </template>

        <!-- Conflict: manifest -->
        <template v-else-if="phase === 'conflict' && type === 'manifest'">
          <div :style="{ fontSize: '12.5px', color: 'var(--fg2)', marginBottom: '10px', lineHeight: 1.5 }">
            This session already has a manifest. Keep current or replace?
          </div>
          <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }">
            <div>
              <div :style="{ fontSize: '11px', fontWeight: 700, color: 'var(--fg2)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '4px' }">Current</div>
              <pre :style="{ background: 'var(--surface-bg)', padding: '8px', fontSize: '11px', maxHeight: '180px', overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: '4px', whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }">{{ summarizeManifest(currentSummary) }}</pre>
            </div>
            <div>
              <div :style="{ fontSize: '11px', fontWeight: 700, color: 'var(--fg2)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '4px' }">New</div>
              <pre :style="{ background: 'var(--surface-bg)', padding: '8px', fontSize: '11px', maxHeight: '180px', overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: '4px', whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }">{{ summarizeManifest(newSummary) }}</pre>
            </div>
          </div>
          <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }">
            <button class="btn btn--secondary btn--sm" @click="chooseManifestMode('keep_current')">↩ Keep current</button>
            <button class="btn btn--primary btn--sm" :style="{ background: 'var(--color-red)', borderColor: 'var(--color-red)' }" @click="chooseManifestMode('use_new')">✓ Use new manifest</button>
          </div>
        </template>
      </div>

      <!-- Footer (idle + error states only) -->
      <div
        v-if="phase === 'idle' || phase === 'error'"
        :style="{ display: 'flex', justifyContent: 'flex-end', gap: '8px', padding: '12px 18px', borderTop: '1px solid var(--border-subtle)' }"
      >
        <button class="btn btn--secondary btn--sm" @click="close">Cancel</button>
        <button
          v-if="type !== 'bios'"
          class="btn btn--primary btn--sm"
          :disabled="!picked"
          @click="upload()"
        >{{ phase === 'error' ? 'Retry' : 'Upload' }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes afm-spin { to { transform: rotate(360deg); } }
</style>
