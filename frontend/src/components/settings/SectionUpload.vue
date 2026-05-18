<script setup lang="ts">
/**
 * SectionUpload — verbatim port of settings-pages.jsx::SectionUpload (208-224).
 */
import { ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import FormRow from './FormRow.vue';
import { toast } from '@/composables/useToast';

const method = ref<string>('railway');

function onChange(e: Event): void {
  method.value = (e.target as HTMLSelectElement).value;
  toast.push('Upload method updated', { tone: 'success' });
}
</script>

<template>
  <SettingsHeader title="Upload & storage" lead="How large files are transferred to our processing pipeline." />
  <div class="set-form">
    <FormRow
      label="Upload method"
      sub="Railway routes file bytes through our server (current default). GCS sends bytes directly from your browser to cloud storage, bypassing the server — more reliable on slow connections and for large files."
    >
      <select class="set-input" :value="method" @change="onChange">
        <option value="railway">Railway (default)</option>
        <option value="gcs">GCS (direct upload)</option>
      </select>
    </FormRow>
  </div>
</template>
