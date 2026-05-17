<script setup lang="ts">
// Phase 3 / U17: SOP workflow. IMPLEMENTATION.md §8.
defineProps<{ id: string }>();
</script>

<template>
  <div class="scaffolding-banner">
    SCAFFOLD: SopView · Phase 3 / U17 — 5-KPI strip · 8-stage stepper · stage detail (Prev/Next, advance with confirm) · owner card · approvals · transition history · invariants. Session id: <code>{{ id }}</code>
  </div>
  <section class="card"><h1>SOP — {{ id }}</h1></section>
</template>
