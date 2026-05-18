<script setup lang="ts">
/**
 * SectionAIModels — verbatim port of settings-pages.jsx::SectionAIModels (192-206).
 */
import { ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import FormRow from './FormRow.vue';
import { AI_MODELS } from '@/fixtures/settings';
import { toast } from '@/composables/useToast';

const model = ref<string>('gemini-2.5-pro');

function onChange(e: Event): void {
  const v = (e.target as HTMLSelectElement).value;
  model.value = v;
  toast.push(`Model: ${AI_MODELS.find((m) => m.v === v)?.label}`, { tone: 'success' });
}
</script>

<template>
  <SettingsHeader
    title="AI models"
    lead="Default model used for new AI MODE sessions. Can be overridden per session on Upload."
  />
  <div class="set-form">
    <FormRow label="Default AI model" sub="Model used for transcription and discrepancy passes.">
      <select class="set-input" :value="model" @change="onChange">
        <option v-for="m in AI_MODELS" :key="m.v" :value="m.v">{{ m.label }}</option>
      </select>
    </FormRow>
  </div>
</template>
