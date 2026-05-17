<script setup lang="ts">
// Phase 3 / U19: Settings (E pattern). 12 sections + drill-ins. IMPLEMENTATION.md §10 / §11.
defineProps<{ section?: string }>();
</script>

<template>
  <div class="scaffolding-banner">
    SCAFFOLD: SettingsView · Phase 3 / U19 — 240px sidebar + content. 12 sections: General · Team &amp; roles · Types &amp; stage defaults · AI models · Upload &amp; storage · Discrepancy classification · Export · Prompt templates · Session manifest · Email · Diagnostics · Deleted sessions. Active section: <code>{{ section ?? 'general' }}</code>
  </div>
  <section class="card"><h1>Settings — {{ section ?? 'general' }}</h1></section>
</template>
