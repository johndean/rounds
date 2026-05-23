<script setup lang="ts">
/**
 * SectionExport — persists `export_include_keypoints` to org_settings.
 */
import { onMounted, ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import FormRow from './FormRow.vue';
import TogglePill from './TogglePill.vue';
import { settingsApi } from '@/services/api';
import { toast } from '@/composables/useToast';
import { ApiError } from '@/services/http';

const keyPoints = ref(false);
const loading = ref(true);
const downloading = ref(false);

onMounted(async () => {
  try {
    const s = (await settingsApi.list()) as Record<string, unknown>;
    if (typeof s.export_include_keypoints === 'boolean') keyPoints.value = s.export_include_keypoints;
  } catch {
    /* fall back to default */
  } finally {
    loading.value = false;
  }
});

async function onToggleKeyPoints(v: boolean): Promise<void> {
  const prev = keyPoints.value;
  keyPoints.value = v;
  try {
    await settingsApi.set('export_include_keypoints', v);
    toast.push(`Key points in export: ${v ? 'on' : 'off'}`, { tone: 'success' });
  } catch {
    keyPoints.value = prev;
    toast.push('Failed to save export setting', { tone: 'error' });
  }
}

async function downloadMacro(): Promise<void> {
  // Phase 3 of the 2026-05-23 Settings BUILD remediation plan. Calls the
  // real /v1/settings/export/macro endpoint via fetch+blob so the browser
  // download dialog opens. 404 MACRO_NOT_FOUND surfaces a clean message
  // when the bundle isn't deployed under docs/macros/.
  if (downloading.value) return;
  downloading.value = true;
  try {
    await settingsApi.downloadMacro();
    toast.push('Macro bundle downloaded', { tone: 'success' });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      const body = e.body as { detail?: { code?: string; message?: string } | string } | undefined;
      const detail = body?.detail;
      const msg = (detail && typeof detail === 'object' && detail.message)
        ? detail.message
        : 'Macro bundle not deployed yet.';
      toast.push(msg, { tone: 'warn' });
    } else {
      const status = e instanceof ApiError ? `${e.status} — ` : '';
      toast.push(`${status}Failed to download macro bundle`, { tone: 'error' });
    }
  } finally {
    downloading.value = false;
  }
}
</script>

<template>
  <SettingsHeader title="Export" lead="What gets included when you download a session." />
  <div class="set-form">
    <FormRow label="Include key points" sub="Add suggested key points to exported documents.">
      <template #control>
        <TogglePill :on="keyPoints" @update:on="onToggleKeyPoints" />
      </template>
    </FormRow>
    <div class="set-card-block">
      <div class="set-eyebrow">WORD MACRO (ONE-TIME INSTALL)</div>
      <div :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '14px', marginTop: '8px' }">
        <div>
          <div :style="{ fontSize: '14px', fontWeight: 700, color: 'var(--fg1)' }">
            Download <code :style="{ fontFamily: 'var(--font-mono)', fontSize: '12.5px' }">macro_COMPLETE_v5.zip</code>
          </div>
          <div :style="{ fontSize: '12.5px', color: 'var(--fg2)', lineHeight: 1.55, marginTop: '4px' }">
            VBA macros <code>SRT_Transcript</code> and <code>CMS_Transcript</code> that clean the downloaded <code>.docx</code> for Wistia SRT and CMS publishing. Unzip once, then open in Word → Developer → Visual Basic → Import.
          </div>
        </div>
        <button
          class="btn btn--tertiary"
          :disabled="downloading"
          data-test-id="export-macro-download"
          @click="downloadMacro"
        >{{ downloading ? 'Downloading…' : '↓ Download (.zip)' }}</button>
      </div>
    </div>
  </div>
</template>
