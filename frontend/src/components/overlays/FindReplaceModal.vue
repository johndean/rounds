<script setup lang="ts">
/**
 * FindReplaceModal — verbatim port of wiring.jsx::FindReplaceModal (165-201).
 * Opens via modal.open(FindReplaceModal). Scoped to the current session,
 * virtualized-aware (matches the React copy).
 *
 * Phase 1 (audit remediation): Replace All is DISABLED until Phase 4 ships
 * the corrections API. The prior implementation toasted a random count and
 * mutated nothing — a data-integrity lie. We keep the form visible (operator
 * muscle memory + Phase 4 will re-enable it) but no fake success.
 */
import { ref } from 'vue';
import { modal } from '@/composables/useModal';

const find = ref('');
const replace = ref('');
const caseSensitive = ref(false);
</script>

<template>
  <div :style="{ width: '480px', padding: '20px' }">
    <h3 class="modal__title">Find &amp; Replace</h3>

    <div
      role="status"
      :style="{
        marginTop: '12px', padding: '10px 12px',
        background: 'rgba(217,119,6,0.08)', border: '1px solid rgba(217,119,6,0.35)',
        borderRadius: 'var(--radius-sm)', color: '#b45309',
        fontSize: '12px', lineHeight: 1.55
      }"
    >
      <strong>Find &amp; Replace is not yet available.</strong>
      Bulk-replace ships with the corrections audit (Phase 4) — until then,
      use per-segment Edit in the transcript so changes can be reviewed and
      reversed individually.
    </div>

    <div :style="{ display: 'grid', gap: '10px', marginTop: '14px', opacity: 0.6 }">
      <label :style="{ display: 'grid', gap: '4px', fontSize: '11px', color: 'var(--fg2)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }">
        Find
        <input
          v-model="find"
          disabled
          placeholder="search term…"
          :style="{ padding: '8px 10px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)', fontSize: '13px' }"
        />
      </label>
      <label :style="{ display: 'grid', gap: '4px', fontSize: '11px', color: 'var(--fg2)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }">
        Replace with
        <input
          v-model="replace"
          disabled
          placeholder="replacement…"
          :style="{ padding: '8px 10px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)', fontSize: '13px' }"
        />
      </label>
      <label :style="{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '12px', color: 'var(--fg2)' }">
        <input v-model="caseSensitive" type="checkbox" disabled />
        Case-sensitive
      </label>
    </div>

    <div class="modal__actions">
      <button class="btn btn--ghost" @click="modal.close()">Close</button>
      <button class="btn btn--primary" disabled title="Available with Phase 4 corrections audit">
        Replace all
      </button>
    </div>
  </div>
</template>
