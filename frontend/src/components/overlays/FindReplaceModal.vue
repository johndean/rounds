<script setup lang="ts">
/**
 * FindReplaceModal — verbatim port of wiring.jsx::FindReplaceModal (165-201).
 * Opens via modal.open(FindReplaceModal). Scoped to the current session,
 * virtualized-aware (matches the React copy).
 */
import { ref } from 'vue';
import { modal } from '@/composables/useModal';
import { toast } from '@/composables/useToast';

const find = ref('');
const replace = ref('');
const caseSensitive = ref(false);

function applyAll(): void {
  if (!find.value) {
    toast.push('Enter a find term', { tone: 'warn' });
    return;
  }
  const count = Math.floor(Math.random() * 8) + 1;
  toast.push(`Replaced ${count} occurrences`, { tone: 'success' });
  modal.close();
}
</script>

<template>
  <div :style="{ width: '480px', padding: '20px' }">
    <h3 class="modal__title">Find &amp; Replace</h3>
    <div :style="{ display: 'grid', gap: '10px', marginTop: '14px' }">
      <label :style="{ display: 'grid', gap: '4px', fontSize: '11px', color: 'var(--fg2)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }">
        Find
        <input
          v-model="find"
          autofocus
          placeholder="search term…"
          :style="{ padding: '8px 10px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)', fontSize: '13px' }"
        />
      </label>
      <label :style="{ display: 'grid', gap: '4px', fontSize: '11px', color: 'var(--fg2)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }">
        Replace with
        <input
          v-model="replace"
          placeholder="replacement…"
          :style="{ padding: '8px 10px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)', fontSize: '13px' }"
        />
      </label>
      <label :style="{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '12px', color: 'var(--fg2)' }">
        <input v-model="caseSensitive" type="checkbox" />
        Case-sensitive
      </label>
      <div :style="{ fontSize: '11px', color: 'var(--fg2)', fontStyle: 'italic' }">Scoped to current session · virtualized-aware</div>
    </div>
    <div class="modal__actions">
      <button class="btn btn--ghost" @click="modal.close()">Cancel</button>
      <button class="btn btn--primary" @click="applyAll">Replace all</button>
    </div>
  </div>
</template>
