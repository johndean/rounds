/**
 * useModal — IMPLEMENTATION.md §12.
 *   modal.open(VueComponent, props?) → Promise<unknown>  // resolves with whatever modal.close(value) is called with
 *   modal.close(value?)
 *
 * Used for Find&Replace, Suggest Improvement (currently inline), Segment Edit, Command Palette.
 */
import { reactive, readonly, shallowRef, type Component } from 'vue';

export type ModalMode = 'overlay' | 'ribbon';

interface ModalState {
  component: Component | null;
  props: Record<string, unknown> | null;
  mode: ModalMode;
}

interface ModalOptions {
  mode?: ModalMode;
}

const state = reactive<ModalState>({ component: null, props: null, mode: 'overlay' });
const _component = shallowRef<Component | null>(null);

let _resolver: ((value: unknown) => void) | null = null;

function open<T = unknown>(
  component: Component,
  props: Record<string, unknown> = {},
  options: ModalOptions = {},
): Promise<T> {
  _component.value = component;
  state.component = component;  // marker only — actual render uses _component shallowRef
  state.props = props;
  state.mode = options.mode ?? 'overlay';
  return new Promise<T>((resolve) => { _resolver = resolve as (v: unknown) => void; });
}

function close(value?: unknown): void {
  _component.value = null;
  state.component = null;
  state.props = null;
  state.mode = 'overlay';
  if (_resolver) {
    _resolver(value);
    _resolver = null;
  }
}

export const modal = { open, close };

export function useModal() {
  return { state: readonly(state), component: _component, open, close };
}
