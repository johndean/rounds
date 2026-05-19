<script setup lang="ts">
/**
 * SectionDiscrepancy — port of settings-pages.jsx::SectionDiscrepancy (226-250).
 *
 * Persists `classify_backend` + `classify_model` to org settings. Classify task
 * (Phase 6l) reads these on every classify call.
 */
import { onMounted, ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import FormRow from './FormRow.vue';
import { AI_MODELS } from '@/fixtures/settings';
import { settingsApi } from '@/services/api';
import { toast } from '@/composables/useToast';

const backend = ref<string>('gemini-dev');
const model = ref<string>('gemini-2.0-flash');
const loading = ref(true);

onMounted(async () => {
  try {
    const s = await settingsApi.list() as Record<string, unknown>;
    if (typeof s.classify_backend === 'string') backend.value = s.classify_backend as string;
    if (typeof s.classify_model === 'string') model.value = s.classify_model as string;
  } finally {
    loading.value = false;
  }
});

async function saveBackend(e: Event): Promise<void> {
  const v = (e.target as HTMLSelectElement).value;
  backend.value = v;
  try { await settingsApi.set('classify_backend', v); toast.push('Classification backend updated', { tone: 'success' }); }
  catch { toast.push('Failed to save', { tone: 'error' }); }
}
async function saveModel(e: Event): Promise<void> {
  const v = (e.target as HTMLSelectElement).value;
  model.value = v;
  try { await settingsApi.set('classify_model', v); toast.push('Classification model updated', { tone: 'success' }); }
  catch { toast.push('Failed to save', { tone: 'error' }); }
}
</script>

<template>
  <SettingsHeader
    title="Discrepancy classification"
    lead="Classifier used to tag discrepancies by type (medication, terminology, etc.). Separate from the main pipeline model — change freely without affecting transcription."
  />
  <div class="set-form">
    <FormRow
      label="Classification backend"
      sub="Gemini API uses your GEMINI_API_KEY. Vertex AI Gemini uses a separate API key (VERTEX_AI_GEMINI_API_KEY) with independent billing and quota."
    >
      <select class="set-input" :value="backend" :disabled="loading" @change="saveBackend">
        <option value="gemini-dev">Gemini Developer API</option>
        <option value="vertex">Vertex AI Gemini (separate billing)</option>
      </select>
    </FormRow>
    <FormRow
      label="Classification AI model"
      sub="Model used to classify discrepancies. Change freely without affecting transcription."
    >
      <select class="set-input" :value="model" :disabled="loading" @change="saveModel">
        <option v-for="m in AI_MODELS" :key="m.v" :value="m.v">{{ m.label }}</option>
      </select>
    </FormRow>
    <div class="set-callout">Default: Gemini 2.0 Flash. If 503 errors persist, switch to Vertex AI backend.</div>
  </div>
</template>
