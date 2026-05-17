<script setup lang="ts">
import { useConfirm } from '@/composables/useConfirm';

const { state, answer } = useConfirm();

function onKey(e: KeyboardEvent): void {
  if (!state.open) return;
  if (e.key === 'Escape') answer(false);
  if (e.key === 'Enter') answer(true);
}

if (typeof window !== 'undefined') {
  window.addEventListener('keydown', onKey);
}
</script>

<template>
  <Teleport to="body">
    <div v-if="state.open" class="scrim" data-test-id="confirm-host" @click.self="answer(false)">
      <div class="confirm">
        <h2 class="confirm__title">{{ state.options?.title }}</h2>
        <p v-if="state.options?.body" class="confirm__body">{{ state.options.body }}</p>
        <div class="confirm__actions">
          <button class="btn" data-test-id="confirm-cancel" @click="answer(false)">
            {{ state.options?.cancelLabel ?? 'Cancel' }}
          </button>
          <button
            class="btn btn--primary"
            :style="state.options?.danger ? 'background: var(--color-red); border-color: var(--color-red);' : ''"
            data-test-id="confirm-ok"
            @click="answer(true)"
          >
            {{ state.options?.confirmLabel ?? 'Confirm' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
