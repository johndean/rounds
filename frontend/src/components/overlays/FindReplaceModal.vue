<script setup lang="ts">
/**
 * FindReplaceModal — bulk find/replace via Phase 4 corrections API.
 *
 * Two-phase flow:
 *   1. Dry run (default): preview every segment that would be modified.
 *   2. Replace All: apply for real. Backend writes one text_edit correction
 *      per affected segment so undo is per-segment in the audit ledger.
 *
 * Modal closes after a successful Replace All and the parent reloads.
 */
import { ref } from 'vue';
import { modal } from '@/composables/useModal';
import { corrections as correctionsApi, type FindReplaceResult } from '@/services/api';
import { ApiError } from '@/services/http';
import { toast } from '@/composables/useToast';

const props = defineProps<{
  sessionId: string;
  onApplied?: () => void;
}>();

const find = ref('');
const replace = ref('');
const caseSensitive = ref(false);
const preview = ref<FindReplaceResult | null>(null);
const running = ref(false);

async function doDryRun(): Promise<void> {
  if (!find.value) return;
  running.value = true;
  try {
    preview.value = await correctionsApi.findReplace(props.sessionId, {
      find: find.value, replace: replace.value, case_sensitive: caseSensitive.value, dry_run: true,
    });
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Preview failed';
    toast.push(msg, { tone: 'error' });
  } finally {
    running.value = false;
  }
}

async function doApply(): Promise<void> {
  if (!find.value) return;
  running.value = true;
  try {
    const r = await correctionsApi.findReplace(props.sessionId, {
      find: find.value, replace: replace.value, case_sensitive: caseSensitive.value, dry_run: false,
    });
    toast.push(`Replaced ${r.total_matches} occurrence${r.total_matches === 1 ? '' : 's'} in ${r.segment_count} segment${r.segment_count === 1 ? '' : 's'}`, { tone: 'success' });
    props.onApplied?.();
    modal.close();
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Replace failed';
    toast.push(msg, { tone: 'error' });
  } finally {
    running.value = false;
  }
}
</script>

<template>
  <div :style="{ width: '560px', padding: '20px' }">
    <h3 class="modal__title">Find &amp; Replace</h3>

    <div :style="{ display: 'grid', gap: '10px', marginTop: '14px' }">
      <label :style="{ display: 'grid', gap: '4px', fontSize: '11px', color: 'var(--fg2)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }">
        Find
        <input
          v-model="find"
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
    </div>

    <div
      v-if="preview"
      :style="{
        marginTop: '14px', padding: '10px 12px',
        background: 'rgba(8,97,206,0.06)', border: '1px solid rgba(8,97,206,0.25)',
        borderRadius: 'var(--radius-sm)', color: 'var(--color-blue)',
        fontSize: '12px', lineHeight: 1.55, maxHeight: '180px', overflowY: 'auto',
      }"
    >
      <strong>Preview:</strong> {{ preview.total_matches }} match{{ preview.total_matches === 1 ? '' : 'es' }} across {{ preview.segment_count }} segment{{ preview.segment_count === 1 ? '' : 's' }}.
      <ul v-if="preview.matches.length" :style="{ margin: '8px 0 0', paddingLeft: '18px' }">
        <li v-for="m in preview.matches.slice(0, 8)" :key="m.segment_id" :style="{ fontFamily: 'var(--font-mono)', fontSize: '11.5px', marginTop: '4px' }">
          {{ m.match_count }}× — {{ m.old_text.slice(0, 60) }}…
        </li>
      </ul>
    </div>

    <div class="modal__actions">
      <button class="btn btn--ghost" @click="modal.close()">Close</button>
      <button class="btn btn--secondary" :disabled="!find || running" @click="doDryRun">
        {{ running ? 'Working…' : 'Preview' }}
      </button>
      <button class="btn btn--primary" :disabled="!find || running" @click="doApply">
        {{ running ? 'Working…' : 'Replace all' }}
      </button>
    </div>
  </div>
</template>
