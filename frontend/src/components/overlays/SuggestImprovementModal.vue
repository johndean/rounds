<script setup lang="ts">
/**
 * SuggestImprovementModal — verbatim port of wiring.jsx::SuggestImprovementModal (204-260).
 * Opens via modal.open(SuggestImprovementModal, { onSubmit }).
 */
import { ref } from 'vue';
import { modal } from '@/composables/useModal';
import { toast } from '@/composables/useToast';

interface Submission { id: string; title: string; surface: string; priority: string; description: string; }

const props = defineProps<{
  onSubmit?: (s: Submission) => void;
}>();

const title = ref('');
const surface = ref('Editor / Transcript');
const priority = ref<'low' | 'med' | 'high' | 'crit'>('med');
const desc = ref('');

function submit(): void {
  if (!title.value) {
    toast.push('Title required', { tone: 'warn' });
    return;
  }
  const id = 'IMP-' + Date.now();
  props.onSubmit?.({ id, title: title.value, surface: surface.value, priority: priority.value, description: desc.value });
  toast.push(`Submitted as ${id}`, { tone: 'success' });
  modal.close();
}

const labelStyle = { display: 'grid', gap: '4px', fontSize: '11px', fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase' as const, color: 'var(--fg2)' };
const inputStyle = { padding: '8px 10px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '13px' };
</script>

<template>
  <div :style="{ width: '520px', padding: '20px' }">
    <h3 class="modal__title">Suggest Improvement</h3>
    <div :style="{ display: 'grid', gap: '12px', marginTop: '14px' }">
      <label :style="labelStyle">
        Title
        <input v-model="title" autofocus :style="inputStyle" />
      </label>
      <label :style="labelStyle">
        Surface
        <select v-model="surface" :style="inputStyle">
          <option>Editor / Transcript</option>
          <option>Editor / Slide Rail</option>
          <option>Editor / Right Rail</option>
          <option>Sessions list</option>
          <option>Dashboard</option>
          <option>Upload</option>
          <option>Settings</option>
          <option>Audit</option>
        </select>
      </label>
      <label :style="labelStyle">
        Priority
        <select v-model="priority" :style="inputStyle">
          <option value="low">Low</option>
          <option value="med">Medium</option>
          <option value="high">High</option>
          <option value="crit">Critical</option>
        </select>
      </label>
      <label :style="labelStyle">
        Description
        <textarea
          v-model="desc"
          :rows="4"
          :style="{ ...inputStyle, fontFamily: 'inherit', resize: 'vertical' }"
        />
      </label>
    </div>
    <div class="modal__actions">
      <button class="btn btn--ghost" @click="modal.close()">Cancel</button>
      <button class="btn btn--primary" @click="submit">Submit</button>
    </div>
  </div>
</template>
