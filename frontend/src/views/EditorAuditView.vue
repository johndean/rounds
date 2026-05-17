<script setup lang="ts">
// Phase 4 / U27 (per-session) and Phase 3 / U20 (standalone variant). IMPLEMENTATION.md §6 Audit tab.
defineProps<{ id: string }>();
</script>

<template>
  <div class="scaffolding-banner">
    SCAFFOLD: EditorAuditView · Phase 4 / U27 — Decisions/Ledger toggle · per-correction cards with WAS/NOW. Session id: <code>{{ id }}</code>
  </div>
  <section class="card"><h1>Audit ledger — {{ id }}</h1></section>
</template>
