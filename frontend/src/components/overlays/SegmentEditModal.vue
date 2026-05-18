<script setup lang="ts">
/**
 * SegmentEditModal — verbatim port of wiring.jsx::SegmentEditModal (263-281).
 * Opens via modal.open(SegmentEditModal, { seg }). Saves through the onSave
 * callback. Closes the modal on Save.
 */
import { ref } from 'vue';
import type { Segment } from '@/fixtures/transcript';
import { modal } from '@/composables/useModal';

const props = defineProps<{
  seg: Segment;
  onSave?: (text: string) => void;
}>();

const text = ref<string>(props.seg.text);

function save(): void {
  props.onSave?.(text.value);
  modal.close();
}
</script>

<template>
  <div :style="{ width: '600px', padding: '20px' }">
    <h3 class="modal__title">
      Edit segment
      <code :style="{ fontFamily: 'var(--font-mono)', color: 'var(--fg-link)', fontSize: '13px' }">{{ seg.id }}</code>
    </h3>
    <textarea
      v-model="text"
      :rows="6"
      autofocus
      :style="{ width: '100%', padding: '10px 12px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '14px', fontFamily: 'inherit', lineHeight: 1.6, marginTop: '12px', resize: 'vertical' }"
    />
    <div class="modal__actions">
      <button class="btn btn--ghost" @click="modal.close()">Cancel</button>
      <button class="btn btn--primary" @click="save">Save</button>
    </div>
  </div>
</template>
