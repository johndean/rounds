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

const keyPoints = ref(false);
const loading = ref(true);

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

function downloadMacro(): void {
  // Phase 2 audit remediation: was previously claiming "Macro downloaded"
  // success while delivering a placeholder zip with `' VBA macro placeholder`
  // inside. Demoted to warn — real macro distribution ships with Phase 10
  // coverage closure (or via static asset hosted alongside the docs).
  toast.push(
    'Macro zip not yet bundled — Word macro distribution ships with Phase 10.',
    { tone: 'warn' },
  );
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
        <button class="btn btn--tertiary" @click="downloadMacro">↓ Download (.zip)</button>
      </div>
    </div>
  </div>
</template>
