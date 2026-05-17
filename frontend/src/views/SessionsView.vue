<script setup lang="ts">
// Phase 3 / U14: Sessions list (B pattern). IMPLEMENTATION.md §6 / §9.
// Reads ?stage / ?ai / ?f query params and shows ActiveFilterChip with × clear.
import { useRoute } from 'vue-router';
const route = useRoute();
</script>

<template>
  <div class="scaffolding-banner">
    SCAFFOLD: SessionsView · Phase 3 / U14 — header strip · tabs · CSS-grid table with fixed pixel columns.
    Filters from URL: <code>{{ JSON.stringify(route.query) }}</code>
  </div>
  <section class="card">
    <h1 style="margin: 0; font-size: var(--fs-xl); font-weight: var(--fw-extrabold);">Sessions</h1>
  </section>
</template>
