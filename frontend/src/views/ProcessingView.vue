<script setup lang="ts">
// Phase 3 / U20: Processing (8-hop ingestion pipeline trace). IMPLEMENTATION.md §5 / §17.
defineProps<{ id: string }>();
</script>

<template>
  <div class="scaffolding-banner">
    SCAFFOLD: ProcessingView · Phase 3 / U20 — 8-hop pipeline trace · Open GCS · Download raw STT · Cancel ingestion. Session id: <code>{{ id }}</code>
  </div>
  <section class="card"><h1>Processing — {{ id }}</h1></section>
</template>
