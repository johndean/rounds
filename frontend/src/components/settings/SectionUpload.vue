<script setup lang="ts">
/**
 * SectionUpload — persists `upload_backend` to org_settings via /v1/settings.
 *
 * UploadView and signed-URL flow both read this on mount to pick the
 * transport (railway multipart vs GCS direct PUT).
 */
import { onMounted, ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import FormRow from './FormRow.vue';
import { settingsApi } from '@/services/api';
import { toast } from '@/composables/useToast';

const method = ref<string>('gcs');
const loading = ref(true);
const saving = ref(false);

onMounted(async () => {
  try {
    const s = await settingsApi.list();
    const v = (s as Record<string, unknown>).upload_backend;
    if (typeof v === 'string') method.value = v;
  } catch {
    /* fall back to default — backend offline */
  } finally {
    loading.value = false;
  }
});

async function onChange(e: Event): Promise<void> {
  const v = (e.target as HTMLSelectElement).value;
  const prev = method.value;
  method.value = v;
  saving.value = true;
  try {
    await settingsApi.set('upload_backend', v);
    toast.push(`Upload method: ${v === 'gcs' ? 'GCS (direct)' : 'Railway (default)'}`, { tone: 'success' });
  } catch (err) {
    method.value = prev;
    toast.push('Failed to save upload method', { tone: 'error' });
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <SettingsHeader title="Upload & storage" lead="How large files are transferred to our processing pipeline." />
  <div class="set-form">
    <FormRow
      label="Upload method"
      sub="GCS (default) sends bytes directly from your browser to cloud storage, bypassing the server — faster and more reliable for the typical 200 MB+ CE session video. Railway routes bytes through our server; keep this only for environments where browser→GCS is blocked."
    >
      <select class="set-input" :value="method" :disabled="loading || saving" @change="onChange">
        <option value="gcs">GCS (direct upload — default)</option>
        <option value="railway">Railway (server-routed)</option>
      </select>
    </FormRow>
  </div>
</template>
