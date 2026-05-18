<script setup lang="ts">
/**
 * SectionAIModels — port of settings-pages.jsx::SectionAIModels (192-206).
 *
 * Persists `default_ai_model` to the org-wide settings via
 * GET / PUT /v1/settings. UploadView reads this on mount to prefill the
 * Model picker.
 */
import { onMounted, ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import FormRow from './FormRow.vue';
import { AI_MODELS } from '@/fixtures/settings';
import { settingsApi } from '@/services/api';
import { toast } from '@/composables/useToast';

const model = ref<string>('gemini-2.5-pro');
const loading = ref(true);

onMounted(async () => {
  try {
    const s = await settingsApi.list();
    if (typeof (s as Record<string, unknown>).default_ai_model === 'string') {
      model.value = (s as Record<string, unknown>).default_ai_model as string;
    }
  } finally {
    loading.value = false;
  }
});

async function onChange(e: Event): Promise<void> {
  const v = (e.target as HTMLSelectElement).value;
  model.value = v;
  try {
    await settingsApi.set('default_ai_model', v);
    toast.push(`Default model: ${AI_MODELS.find((m) => m.v === v)?.label}`, { tone: 'success' });
  } catch {
    toast.push('Failed to save default model', { tone: 'error' });
  }
}
</script>

<template>
  <SettingsHeader
    title="AI models"
    lead="Default model used for new AI MODE sessions. Can be overridden per session on Upload."
  />
  <div class="set-form">
    <FormRow label="Default AI model" sub="Model used for transcription and discrepancy passes.">
      <select class="set-input" :value="model" :disabled="loading" @change="onChange">
        <option v-for="m in AI_MODELS" :key="m.v" :value="m.v">{{ m.label }}</option>
      </select>
    </FormRow>
  </div>
</template>
