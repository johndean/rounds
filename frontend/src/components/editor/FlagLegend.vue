<script setup lang="ts">
/**
 * FlagLegend — verbatim port of components.jsx::FlagLegend (295-309).
 * Three-chip legend (drift / uncertain / low confidence) shown in the editor
 * tab-bar's meta slot.
 */
</script>

<template>
  <div :style="{ display: 'flex', gap: '14px', fontSize: '11px', color: 'var(--fg2)', alignItems: 'center' }">
    <span :style="{ display: 'inline-flex', alignItems: 'center', gap: '6px' }">
      <em class="word flag-drift" :style="{ display: 'inline-block', padding: '0 6px', borderRadius: '2px' }">drift</em>
    </span>
    <span :style="{ display: 'inline-flex', alignItems: 'center', gap: '6px' }">
      <em class="word flag-uncertain" :style="{ display: 'inline-block', padding: '0 6px', borderRadius: '2px' }">uncertain</em>
    </span>
    <span :style="{ display: 'inline-flex', alignItems: 'center', gap: '6px' }">
      <em class="word flag-low_confidence" :style="{ display: 'inline-block', padding: '0 6px', borderRadius: '2px' }">low confidence</em>
    </span>
  </div>
</template>
