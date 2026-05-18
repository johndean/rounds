<script setup lang="ts">
/**
 * DownloadMenu — verbatim port of editor.jsx::DownloadMenu (938-970).
 * Dropdown of export formats (docx / srt / txt / zip). Closes on outside click.
 */
import { ref, onMounted, onUnmounted } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { toast } from '@/composables/useToast';

defineProps<{ code: string }>();

const open = ref(false);
const wrapRef = ref<HTMLElement | null>(null);

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

function pick(f: Format, code: string): void {
  open.value = false;
  toast.push(`Downloading ${f.label} (.${f.ext}) for ${code}`, { tone: 'info' });
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
        @click="pick(f, code)"
      >
        <div class="dl-menu__label">{{ f.label }} <code>(.{{ f.ext }})</code></div>
        <div class="dl-menu__sub">{{ f.sub }}</div>
      </button>
    </div>
  </span>
</template>
