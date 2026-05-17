/**
 * useToast — IMPLEMENTATION.md §12.
 *   toast.push(msg, { tone, action, duration })
 *   tones: info | success | warn | error
 *   bottom-right stack, auto-dismiss after `duration` ms (default 3500).
 *
 * Single global host mounted in App.vue via <ToastHost />.
 */
import { reactive, readonly } from 'vue';

export type ToastTone = 'info' | 'success' | 'warn' | 'error';

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastEntry {
  id: number;
  msg: string;
  tone: ToastTone;
  action?: ToastAction;
  expiresAt: number;
}

interface ToastState {
  entries: ToastEntry[];
}

const state = reactive<ToastState>({ entries: [] });
let _nextId = 1;

function push(msg: string, opts: { tone?: ToastTone; action?: ToastAction; duration?: number } = {}) {
  const id = _nextId++;
  const tone = opts.tone ?? 'info';
  const duration = opts.duration ?? 3500;
  const expiresAt = Date.now() + duration;
  state.entries.push({ id, msg, tone, action: opts.action, expiresAt });
  if (duration > 0) {
    setTimeout(() => dismiss(id), duration);
  }
  return id;
}

function dismiss(id: number) {
  const idx = state.entries.findIndex((e) => e.id === id);
  if (idx >= 0) state.entries.splice(idx, 1);
}

function clear() { state.entries.splice(0, state.entries.length); }

export const toast = { push, dismiss, clear } as const;

export function useToast() {
  return { state: readonly(state), push, dismiss, clear };
}
