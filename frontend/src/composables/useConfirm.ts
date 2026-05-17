/**
 * useConfirm — IMPLEMENTATION.md §12.
 *   confirm.open({title, body, danger, confirmLabel, cancelLabel}) → Promise<boolean>
 * Single host mounted in App.vue. Resolves with true (confirm) or false (cancel/dismiss).
 */
import { reactive, readonly } from 'vue';

export interface ConfirmOptions {
  title: string;
  body?: string;
  danger?: boolean;
  confirmLabel?: string;
  cancelLabel?: string;
}

interface ConfirmState {
  open: boolean;
  options: ConfirmOptions | null;
}

const state = reactive<ConfirmState>({ open: false, options: null });
let _resolver: ((ok: boolean) => void) | null = null;

function open(opts: ConfirmOptions): Promise<boolean> {
  state.options = opts;
  state.open = true;
  return new Promise<boolean>((resolve) => { _resolver = resolve; });
}

function answer(ok: boolean): void {
  state.open = false;
  state.options = null;
  if (_resolver) {
    _resolver(ok);
    _resolver = null;
  }
}

export const confirm = { open, answer };

export function useConfirm() {
  return { state: readonly(state), open, answer };
}
