<script setup lang="ts">
/**
 * DownloadMenu — verbatim port of editor.jsx::DownloadMenu (938-970).
 * Dropdown of export formats (docx / srt / txt / zip). Closes on outside click.
 *
 * Phase A1 (2026-06-05): wired to GET /v1/sessions/{id}/exports/{format}.
 * Replaces the previous toast-only stub. The exportsApi helper streams
 * the artifact bytes as a Blob and triggers a browser save dialog via
 * a transient <a download> element.
 */
import { ref, onMounted, onUnmounted } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { toast } from '@/composables/useToast';
import { exportsApi } from '@/services/api';

const props = defineProps<{ code: string; sessionId: string }>();

const open = ref(false);
const wrapRef = ref<HTMLElement | null>(null);
const downloading = ref<string | null>(null);

interface Format { ext: 'docx' | 'srt' | 'txt' | 'zip'; label: string; sub: string }
const formats: Format[] = [
  { ext: 'docx', label: 'Word',       sub: 'Macro-compatible transcript' },
  { ext: 'srt',  label: 'Captions',   sub: 'SubRip for Wistia / video player' },
  { ext: 'txt',  label: 'Plain Text', sub: 'Quick paste / email' },
  { ext: 'zip',  label: 'Word Macro', sub: 'One-time install for SRT/CMS prep' },
];

function onDoc(e: MouseEvent): void {
  if (!wrapRef.value) return;
  if (!wrapRef.value.contains(e.target as Node)) open.value = false;
}

onMounted(() => document.addEventListener('mousedown', onDoc));
onUnmounted(() => document.removeEventListener('mousedown', onDoc));

async function pick(f: Format): Promise<void> {
  if (downloading.value) return;
  open.value = false;
  downloading.value = f.ext;
  toast.push(`Preparing ${f.label} (.${f.ext})…`, { tone: 'info' });
  try {
    await exportsApi.download(props.sessionId, f.ext);
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Download failed';
    toast.push(`Could not download ${f.label}: ${msg}`, { tone: 'error' });
  } finally {
    downloading.value = null;
  }
}
</script>

<template>
  <span ref="wrapRef" class="dl-menu-wrap">
    <button
      :class="['btn', 'btn--primary', 'btn--sm', open ? 'dl-menu-trigger--open' : '']"
      data-test-id="editor-download"
      @click="open = !open"
    ><Icon name="download" /> Download</button>
    <div v-if="open" class="dl-menu" role="menu">
      <button
        v-for="f in formats"
        :key="f.ext"
        class="dl-menu__item"
        role="menuitem"
        :data-test-id="`dl-${f.ext}`"
        :disabled="downloading !== null"
        @click="pick(f)"
      >
        <div class="dl-menu__label">{{ f.label }} <code>(.{{ f.ext }})</code></div>
        <div class="dl-menu__sub">{{ f.sub }}</div>
      </button>
    </div>
  </span>
</template>
