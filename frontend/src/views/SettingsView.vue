<script setup lang="ts">
/**
 * Settings (E pattern). IMPLEMENTATION.md §10 / §11.
 * 12 sections + drill-ins. Phase 8 part 3: General + Discrepancy classification
 * are live; remaining sections show their scope but defer detail until needed.
 */
import { onMounted, ref, computed } from 'vue';
import { settingsApi } from '@/services/api';
import { useUiStore } from '@/stores/ui';
import { toast } from '@/composables/useToast';

const props = defineProps<{ section?: string }>();
const uiStore = useUiStore();

const SECTIONS = [
  { id: 'general',          label: 'General' },
  { id: 'team',             label: 'Team & roles' },
  { id: 'types',            label: 'Types & stage defaults' },
  { id: 'ai-models',        label: 'AI models' },
  { id: 'upload-storage',   label: 'Upload & storage' },
  { id: 'classification',   label: 'Discrepancy classification' },
  { id: 'export',           label: 'Export' },
  { id: 'prompts',          label: 'Prompt templates' },
  { id: 'manifest',         label: 'Session manifest' },
  { id: 'email',            label: 'Email' },
  { id: 'diagnostics',      label: 'Diagnostics' },
  { id: 'deleted-sessions', label: 'Deleted sessions' },
];

const activeSection = computed(() => props.section ?? 'general');

const orgSettings = ref<Record<string, unknown>>({});
const loading = ref(true);

async function load(): Promise<void> {
  loading.value = true;
  try {
    orgSettings.value = await settingsApi.list();
  } catch {
    orgSettings.value = {};
  } finally {
    loading.value = false;
  }
}

async function saveSetting(key: string, value: unknown): Promise<void> {
  try {
    await settingsApi.set(key, value);
    orgSettings.value[key] = value;
    toast.push(`Saved ${key}`, { tone: 'success' });
  } catch {
    toast.push(`Failed to save ${key}`, { tone: 'error' });
  }
}

const orgName       = computed({ get: () => (orgSettings.value.org_name as string) ?? '', set: v => saveSetting('org_name', v) });
const defaultLocale = computed({ get: () => (orgSettings.value.default_locale as string) ?? 'en-US', set: v => saveSetting('default_locale', v) });

onMounted(load);
</script>

<template>
  <div class="settings">
    <aside class="settings__sidebar">
      <RouterLink
        v-for="s in SECTIONS"
        :key="s.id"
        :to="`/settings/${s.id}`"
        :class="{ 'is-active': activeSection === s.id }"
      >{{ s.label }}</RouterLink>
    </aside>

    <main class="settings__content">
      <header style="margin-bottom: var(--space-5);">
        <h1 class="settings-header__title">{{ SECTIONS.find(s => s.id === activeSection)?.label ?? 'Settings' }}</h1>
        <p class="settings-header__lead">
          {{ activeSection === 'general' ? 'Organization-wide defaults and locale.'
            : activeSection === 'classification' ? 'Choose which backend classifies discrepancies — Gemini Developer API (default) or Vertex AI.'
            : 'Section scaffolded; full editor lands in upcoming Phase 8 commits.' }}
        </p>
      </header>

      <div v-if="activeSection === 'general'" class="settings-form">
        <p v-if="loading" style="color: var(--fg2);">Loading…</p>
        <template v-else>
          <label><span>Organization name</span>
            <input type="text" :value="orgName" @change="(e) => orgName = (e.target as HTMLInputElement).value" />
          </label>
          <label><span>Default locale</span>
            <select :value="defaultLocale" @change="(e) => defaultLocale = (e.target as HTMLSelectElement).value">
              <option value="en-US">English (US)</option>
              <option value="en-GB">English (UK)</option>
            </select>
          </label>
        </template>
      </div>

      <div v-else-if="activeSection === 'classification'" class="settings-form">
        <label><span>Backend</span>
          <select v-model="uiStore.classifyBackend">
            <option value="gemini_dev">Gemini Developer API</option>
            <option value="vertex_ai">Vertex AI</option>
          </select>
        </label>
        <label><span>Model</span>
          <select v-model="uiStore.classifyModel">
            <option value="gemini-2.5-flash-lite">gemini-2.5-flash-lite</option>
            <option value="gemini-2.5-flash">gemini-2.5-flash</option>
            <option value="gemini-2.5-pro">gemini-2.5-pro</option>
          </select>
        </label>
        <p style="margin-top: var(--space-4); padding: var(--space-3); background: var(--color-warm-light); border-radius: var(--radius-sm); font-size: var(--fs-xs); color: var(--fg1);">
          Setting persists to local storage; backend route at /v1/diag/classify-route confirms which backend is active.
        </p>
      </div>

      <div v-else class="card">
        <p style="margin: 0; color: var(--fg2); font-size: var(--fs-sm);">
          Section <span class="mono">{{ activeSection }}</span> — backend endpoints are live at <span class="mono">/v1/settings/*</span>; UI for this section lands in a subsequent Phase 8 commit.
        </p>
      </div>
    </main>
  </div>
</template>
