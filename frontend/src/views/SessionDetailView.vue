<script setup lang="ts">
// Phase 3 / U15: Session Detail (mixed). IMPLEMENTATION.md §7.
defineProps<{ id: string }>();
</script>

<template>
  <div class="scaffolding-banner">
    SCAFFOLD: SessionDetailView · Phase 3 / U15 — 3-column (280/1fr/320): meta · 5-KPI grid + alignment + AI mode + files attention · stage assignments + publishing links. Session id: <code>{{ id }}</code>
  </div>
  <section class="card"><h1>Session {{ id }}</h1></section>
</template>
