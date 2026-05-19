<script setup lang="ts">
import { useModal } from '@/composables/useModal';

const { component, state, close } = useModal();
</script>

<template>
  <Teleport to="body">
    <div
      v-if="component"
      :class="state.mode === 'ribbon' ? 'modal-ribbon' : 'modal-backdrop'"
      data-test-id="modal-host"
      @click.self="state.mode === 'overlay' ? close() : null"
      @keydown.esc.window="close()"
    >
      <component :is="component" v-bind="state.props ?? {}" @close="close" />
    </div>
  </Teleport>
</template>
