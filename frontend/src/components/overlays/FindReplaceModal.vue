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
import { ref, watch, computed } from 'vue';
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
let dryRunTimer: ReturnType<typeof setTimeout> | null = null;

async function doDryRun(): Promise<void> {
  if (!find.value) { preview.value = null; return; }
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

// Debounced live preview. Re-runs the dry-run any time find/replace/case changes.
watch([find, replace, caseSensitive], () => {
  if (dryRunTimer) clearTimeout(dryRunTimer);
  if (!find.value) { preview.value = null; return; }
  dryRunTimer = setTimeout(() => { void doDryRun(); }, 280);
});

function htmlEscape(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

interface PreviewLine {
  segmentId: string;
  countLabel: string;
  snippetHtml: string;
}

// Per-match contextual snippet: ±40 chars around each occurrence of `find`,
// rendering "before <s>old</s> → <mark>new</mark> after". One line per
// occurrence so the user sees exactly what changes.
const previewLines = computed<PreviewLine[]>(() => {
  const p = preview.value;
  if (!p || !find.value) return [];
  const out: PreviewLine[] = [];
  const needle = find.value;
  const flags = caseSensitive.value ? 'g' : 'gi';
  const escRe = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  for (const m of p.matches) {
    const text = m.old_text || '';
    const re = new RegExp(escRe, flags);
    let match: RegExpExecArray | null;
    while ((match = re.exec(text)) !== null) {
      const start = Math.max(0, match.index - 40);
      const end = Math.min(text.length, match.index + needle.length + 40);
      const beforeFrag = (start > 0 ? '…' : '') + text.slice(start, match.index);
      const hit = match[0]!;
      const afterFrag = text.slice(match.index + needle.length, end) + (end < text.length ? '…' : '');
      out.push({
        segmentId: m.segment_id,
        countLabel: '',
        snippetHtml:
          htmlEscape(beforeFrag) +
          `<s class="dc-was-strike">${htmlEscape(hit)}</s>` +
          ' → ' +
          `<mark class="dc-now-mark">${htmlEscape(replace.value)}</mark>` +
          htmlEscape(afterFrag),
      });
      if (re.lastIndex === match.index) re.lastIndex++;
    }
    if (out.length >= 50) break;
  }
  return out;
});

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
      v-if="preview && find"
      :style="{
        marginTop: '14px', padding: '10px 12px',
        background: 'var(--surface-bg)', border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-sm)',
        fontSize: '12px', lineHeight: 1.55, maxHeight: '220px', overflowY: 'auto',
      }"
    >
      <div :style="{ marginBottom: '6px', fontSize: '11px', color: 'var(--fg2)', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase' }">
        {{ preview.total_matches }} match{{ preview.total_matches === 1 ? '' : 'es' }} across {{ preview.segment_count }} segment{{ preview.segment_count === 1 ? '' : 's' }}
      </div>
      <div
        v-for="(line, i) in previewLines"
        :key="i"
        :style="{ fontSize: '12px', padding: '4px 0', borderTop: i > 0 ? '1px dashed var(--border-subtle)' : 'none' }"
        v-html="line.snippetHtml"
      />
      <div v-if="preview.total_matches === 0" :style="{ color: 'var(--fg2)', fontStyle: 'italic' }">No matches.</div>
    </div>

    <div class="modal__actions">
      <button class="btn btn--ghost" @click="modal.close()">Close</button>
      <button class="btn btn--primary" :disabled="!find || running || preview?.total_matches === 0" @click="doApply">
        {{ running ? 'Working…' : 'Replace all' }}
      </button>
    </div>
  </div>
</template>
