<script setup lang="ts">
import { useModal } from '@/composables/useModal';

const { component, state, close } = useModal();
</script>

<template>
  <Teleport to="body">
    <div v-if="component" class="scrim" data-test-id="modal-host" @click.self="close()">
      <component :is="component" v-bind="state.props ?? {}" @close="close" />
    </div>
  </Teleport>
</template>
