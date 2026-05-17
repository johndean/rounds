<script setup lang="ts">
/**
 * Sparkline — faithful port of dashboard.jsx::Sparkline.
 * 100×18 viewBox, polyline of normalized points, stroke=currentColor.
 * Empty class when data has < 2 points.
 */
import { computed } from 'vue';

const props = defineProps<{ data: readonly number[] }>();

const isEmpty = computed(() => !props.data || props.data.length < 2);

const points = computed<string | null>(() => {
  if (isEmpty.value) return null;
  const w = 100, h = 18;
  const data = props.data;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  return data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
});
</script>

<template>
  <div v-if="isEmpty" class="dash-spark dash-spark--empty" />
  <svg v-else class="dash-spark" viewBox="0 0 100 18" preserveAspectRatio="none">
    <polyline :points="points!" fill="none" stroke="currentColor" stroke-width="1.5" />
  </svg>
</template>
