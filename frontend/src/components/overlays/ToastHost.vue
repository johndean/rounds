<script setup lang="ts">
import { useToast } from '@/composables/useToast';

const { state, dismiss } = useToast();
</script>

<template>
  <div class="toast-host" data-test-id="toast-host" aria-live="polite">
    <div
      v-for="entry in state.entries"
      :key="entry.id"
      class="toast"
      :class="`toast--${entry.tone}`"
      :data-test-id="`toast-${entry.id}`"
    >
      <span>{{ entry.msg }}</span>
      <button
        v-if="entry.action"
        class="btn"
        :data-test-id="`toast-${entry.id}-action`"
        @click="() => { entry.action!.onClick(); dismiss(entry.id); }"
      >{{ entry.action.label }}</button>
    </div>
  </div>
</template>
