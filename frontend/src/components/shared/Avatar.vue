<script setup lang="ts">
/**
 * Avatar — circle with initials. Faithful port of components.jsx::Avatar.
 */
import { computed } from 'vue';

const props = withDefaults(defineProps<{
  name: string;
  color?: string;
  size?: number;
  ring?: boolean;
}>(), {
  size: 24,
  ring: true,
});

const initials = computed(() =>
  (props.name || '?').split(/\s+/).map(p => p[0]).join('').slice(0, 2).toUpperCase(),
);
</script>

<template>
  <span
    class="avatar"
    :style="{
      width: size + 'px',
      height: size + 'px',
      borderRadius: '50%',
      background: color || 'var(--color-steel)',
      color: '#fff',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: Math.round(size * 0.4) + 'px',
      fontWeight: 800,
      border: ring ? '2px solid var(--surface-card)' : 'none',
      flexShrink: 0,
    }"
  >{{ initials }}</span>
</template>
