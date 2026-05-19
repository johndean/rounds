<script setup lang="ts">
/**
 * ⌘K command palette — IMPLEMENTATION.md §12.
 * Search across routes + actions. Globally toggled by Cmd/Ctrl+K.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';

interface Command {
  id: string;
  label: string;
  hint?: string;
  to?: string;
  action?: () => void;
}

const router = useRouter();
const open = ref(false);
const query = ref('');
const inputRef = ref<HTMLInputElement | null>(null);

const COMMANDS: Command[] = [
  { id: 'go-dashboard',      label: 'Dashboard',              hint: '/dashboard',     to: '/dashboard' },
  { id: 'go-sessions',       label: 'Sessions',               hint: '/sessions',      to: '/sessions' },
  { id: 'go-upload',         label: 'Upload new session',     hint: '/upload',        to: '/upload' },
  { id: 'go-improvements',   label: 'Improvements',           hint: '/improvements',  to: '/improvements' },
  { id: 'go-settings',       label: 'Settings',               hint: '/settings',      to: '/settings' },
  { id: 'go-audit',          label: 'Audit ledger',           hint: '/audit',         to: '/audit' },
  { id: 'go-gcs',            label: 'GCS QA',                 hint: '/gcs',           to: '/gcs' },
  { id: 'go-editor',         label: 'Editor (demo)',          hint: '/e/se_001',      to: '/e/se_001' },
  { id: 'go-sop',            label: 'SOP workflow',           hint: '/e/se_001/sop',  to: '/e/se_001/sop' },
  { id: 'go-session-detail', label: 'Session detail (demo)',  hint: '/s/se_001',      to: '/s/se_001' },
  { id: 'go-viewer',         label: 'Viewer (demo)',          hint: '/v/se_004',      to: '/v/se_004' },
  { id: 'go-processing',     label: 'Processing (demo)',      hint: '/p/se_007',      to: '/p/se_007' },
];

const filtered = computed<Command[]>(() => {
  const q = query.value.trim().toLowerCase();
  if (!q) return COMMANDS;
  return COMMANDS.filter(c =>
    c.label.toLowerCase().includes(q) ||
    (c.hint && c.hint.toLowerCase().includes(q)),
  );
});

const selected = ref(0);

function reset(): void {
  query.value = '';
  selected.value = 0;
}

function toggle(): void {
  open.value = !open.value;
  if (open.value) {
    reset();
    setTimeout(() => inputRef.value?.focus(), 0);
  }
}

function close(): void {
  open.value = false;
  reset();
}

function pick(c?: Command): void {
  const cmd = c ?? filtered.value[selected.value];
  if (!cmd) return;
  close();
  if (cmd.to) router.push(cmd.to);
  cmd.action?.();
}

function onKey(e: KeyboardEvent): void {
  // Global ⌘K / ctrl-K
  if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault();
    toggle();
    return;
  }
  if (!open.value) return;
  if (e.key === 'Escape') { e.preventDefault(); close(); }
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    selected.value = Math.min(selected.value + 1, filtered.value.length - 1);
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault();
    selected.value = Math.max(selected.value - 1, 0);
  }
  if (e.key === 'Enter') {
    e.preventDefault();
    pick();
  }
}

onMounted(() => window.addEventListener('keydown', onKey));
onUnmounted(() => window.removeEventListener('keydown', onKey));

defineExpose({ toggle, close });
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-backdrop" data-test-id="command-palette" @click.self="close">
      <div class="command-palette" @click.stop>
        <input
          ref="inputRef"
          v-model="query"
          class="command-palette__input"
          placeholder="Search commands…"
          data-test-id="cmdp-input"
        />
        <ul class="cmdp-list">
          <li
            v-for="(c, i) in filtered"
            :key="c.id"
            :class="['cmdp-item', { 'is-selected': i === selected }]"
            :data-test-id="`cmdp-item-${c.id}`"
            @mouseenter="selected = i"
            @click="pick(c)"
          >
            <span class="cmdp-label">{{ c.label }}</span>
            <span v-if="c.hint" class="cmdp-hint mono">{{ c.hint }}</span>
          </li>
          <li v-if="!filtered.length" class="cmdp-empty">No commands match.</li>
        </ul>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cmdp-list { list-style: none; margin: 0; padding: 0; max-height: 320px; overflow-y: auto; }
.cmdp-item {
  display: flex; align-items: center; justify-content: space-between; gap: var(--space-3);
  padding: var(--space-3); cursor: pointer; border-radius: var(--radius-sm);
}
.cmdp-item.is-selected { background: var(--surface-muted); }
.cmdp-label { font-size: var(--fs-sm); }
.cmdp-hint { font-size: var(--fs-xs); color: var(--fg2); opacity: 0.7; }
.cmdp-empty { padding: var(--space-3); color: var(--fg2); font-size: var(--fs-sm); text-align: center; }
</style>
