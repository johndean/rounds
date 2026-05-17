<script setup lang="ts">
// Phase 3 / U20: Viewer (export preview document mock). IMPLEMENTATION.md §5.
defineProps<{ id: string }>();
</script>

<template>
  <div class="scaffolding-banner">
    SCAFFOLD: ViewerView · Phase 3 / U20 — export preview document + Download SRT + Edit. Session id: <code>{{ id }}</code>
  </div>
  <section class="card"><h1>Viewer — {{ id }}</h1></section>
</template>
