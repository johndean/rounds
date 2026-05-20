<script setup lang="ts">
/**
 * SessionTextEdit — click-to-edit inline text field for session metadata.
 *
 * Port of MIC's mic/frontend/src/components/SessionCode.vue, generalized so
 * the same component edits `code`, `title`, `title_long`, etc. Single click
 * swaps the display span for an <input>; blur or Enter commits via
 * sessionsApi.update(); Escape cancels.
 *
 * The component is "uncontrolled" — it tracks its own edit buffer locally
 * and emits `save` after the PATCH succeeds so the parent can refresh.
 * Failure is non-fatal (toasts an error and keeps the input open so the
 * user can fix and retry).
 */
import { ref, nextTick, computed } from 'vue';
import { sessions as sessionsApi, type SessionPatch } from '@/services/api';
import { toast } from '@/composables/useToast';
import { ApiError } from '@/services/http';

const props = withDefaults(defineProps<{
  /** Current displayed value. Parent owns the source of truth. */
  value:     string | null;
  /** Session UUID — required for the PATCH call. */
  sessionId: string;
  /** Which field on `sessions` to update. Matches SessionPatch keys. */
  field:     keyof SessionPatch;
  /** Show a "+ Add <label>" affordance when value is empty/null. */
  emptyLabel?: string;
  /** Placeholder shown inside the <input>. */
  placeholder?: string;
  /** Disable interaction (e.g. for non-admin viewers). */
  readonly?: boolean;
  /** Visual variant — 'title' bumps font weight, 'code' uses mono. */
  variant?:  'title' | 'code' | 'plain';
}>(), {
  emptyLabel: '+ Add',
  placeholder: '',
  readonly: false,
  variant: 'plain',
});

const emit = defineEmits<{
  (e: 'save', value: string): void;
}>();

const editing   = ref(false);
const draft     = ref('');
const saving    = ref(false);
const inputRef  = ref<HTMLInputElement | null>(null);

const displayed = computed(() => (props.value ?? '').trim());
const isEmpty   = computed(() => displayed.value === '');

function startEdit(ev?: MouseEvent | KeyboardEvent): void {
  if (props.readonly || saving.value) return;
  ev?.stopPropagation();
  draft.value = props.value ?? '';
  editing.value = true;
  nextTick(() => inputRef.value?.focus());
}

function cancel(): void {
  editing.value = false;
  draft.value = '';
}

async function commit(): Promise<void> {
  if (!editing.value) return;
  const next = draft.value.trim();
  // No-op when unchanged.
  if (next === (props.value ?? '').trim()) {
    editing.value = false;
    return;
  }
  saving.value = true;
  try {
    const patch: SessionPatch = { [props.field]: next } as SessionPatch;
    await sessionsApi.update(props.sessionId, patch);
    emit('save', next);
    editing.value = false;
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      toast.push('Another session already uses that code.', { tone: 'warn' });
    } else {
      const msg = err instanceof Error ? err.message : 'Save failed';
      toast.push(`Could not save: ${msg}`, { tone: 'warn' });
    }
    // Keep the input open so the user can fix + retry. Don't drop the draft.
  } finally {
    saving.value = false;
  }
}

function onKeyDown(e: KeyboardEvent): void {
  if (e.key === 'Enter') {
    e.preventDefault();
    void commit();
  } else if (e.key === 'Escape') {
    e.preventDefault();
    cancel();
  }
}

const valClass = computed(() => {
  const c = ['ste__val', `ste__val--${props.variant}`];
  if (!props.readonly) c.push('ste__val--editable');
  return c.join(' ');
});

const inputClass = computed(() => `ste__input ste__input--${props.variant}`);
</script>

<template>
  <span class="ste">
    <template v-if="!editing">
      <span
        v-if="!isEmpty"
        :class="valClass"
        :title="readonly ? '' : 'Click to edit'"
        @click="startEdit"
      >{{ displayed }}</span>
      <span
        v-else-if="!readonly"
        class="ste__add"
        @click="startEdit"
      >{{ emptyLabel }}</span>
    </template>
    <input
      v-else
      ref="inputRef"
      v-model="draft"
      :class="inputClass"
      :placeholder="placeholder"
      :disabled="saving"
      @keydown="onKeyDown"
      @blur="commit"
      @click.stop
    />
  </span>
</template>

<style scoped>
.ste {
  display: inline-flex;
  align-items: baseline;
}
.ste__val,
.ste__add,
.ste__input {
  font-size: inherit;
  line-height: 1.2;
  color: inherit;
}
.ste__val--editable {
  cursor: text;
  border-bottom: 1px dashed transparent;
  transition: border-color 120ms ease;
}
.ste__val--editable:hover {
  border-bottom-color: var(--border-strong, currentColor);
}
.ste__val--title {
  font-weight: var(--weight-semibold, 600);
}
.ste__val--code {
  font-family: var(--font-mono, monospace);
  font-weight: var(--weight-semibold, 600);
}
.ste__add {
  cursor: pointer;
  opacity: 0.55;
  font-style: italic;
}
.ste__add:hover {
  opacity: 0.8;
}
.ste__input {
  background: transparent;
  border: none;
  border-bottom: 2px solid var(--color-navy, currentColor);
  outline: none;
  padding: 0 2px;
  min-width: 240px;
  font: inherit;
}
.ste__input--title {
  font-weight: var(--weight-semibold, 600);
  min-width: 320px;
}
.ste__input--code {
  font-family: var(--font-mono, monospace);
  font-weight: var(--weight-semibold, 600);
}
.ste__input:disabled {
  opacity: 0.6;
  cursor: progress;
}
</style>
