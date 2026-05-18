<script setup lang="ts">
/**
 * SectionDiscrepancy — verbatim port of settings-pages.jsx::SectionDiscrepancy (226-250).
 */
import { ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import FormRow from './FormRow.vue';
import { AI_MODELS } from '@/fixtures/settings';

const backend = ref<string>('gemini-dev');
const model = ref<string>('gemini-2.0-flash');
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
      <select class="set-input" :value="backend" @change="(e) => (backend = (e.target as HTMLSelectElement).value)">
        <option value="gemini-dev">Gemini Developer API</option>
        <option value="vertex">Vertex AI Gemini (separate billing)</option>
      </select>
    </FormRow>
    <FormRow
      label="Classification AI model"
      sub="Model used to classify discrepancies. Change freely without affecting transcription."
    >
      <select class="set-input" :value="model" @change="(e) => (model = (e.target as HTMLSelectElement).value)">
        <option v-for="m in AI_MODELS" :key="m.v" :value="m.v">{{ m.label }}</option>
      </select>
    </FormRow>
    <div class="set-callout">Default: Gemini 2.0 Flash. If 503 errors persist, switch to Vertex AI backend.</div>
  </div>
</template>
