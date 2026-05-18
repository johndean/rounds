<script setup lang="ts">
/**
 * TogglePill — verbatim port of settings-pages.jsx::TogglePill (818-824).
 * Pill-shaped on/off switch.
 */
defineProps<{ on: boolean }>();
const emit = defineEmits<{ (e: 'update:on', v: boolean): void }>();
</script>

<template>
  <button
    :class="['set-toggle', on ? 'is-on' : '']"
    :aria-pressed="on"
    @click="emit('update:on', !on)"
  >
    <span class="set-toggle__knob" />
  </button>
</template>
