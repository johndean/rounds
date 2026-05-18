<script setup lang="ts">
/**
 * SectionExport — verbatim port of settings-pages.jsx::SectionExport (252-276).
 */
import { ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import FormRow from './FormRow.vue';
import TogglePill from './TogglePill.vue';
import { toast } from '@/composables/useToast';

const keyPoints = ref(false);

function downloadMacro(): void {
  const blob = new Blob(["' VBA macro placeholder"], { type: 'application/zip' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'macro_COMPLETE_v5.zip';
  a.click();
  URL.revokeObjectURL(url);
  toast.push('Macro downloaded', { tone: 'success' });
}
</script>

<template>
  <SettingsHeader title="Export" lead="What gets included when you download a session." />
  <div class="set-form">
    <FormRow label="Include key points" sub="Add suggested key points to exported documents.">
      <template #control>
        <TogglePill :on="keyPoints" @update:on="(v) => (keyPoints = v)" />
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
