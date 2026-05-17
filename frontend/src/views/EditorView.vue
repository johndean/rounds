<script setup lang="ts">
// Phase 4 / U21-U30: Editor (D pattern, 3-column resizable, 4 tabs). IMPLEMENTATION.md §6.
// The heaviest surface — see plan §7 Phase 4 for the 10-unit breakdown.
defineProps<{ id: string }>();
</script>

<template>
  <div class="scaffolding-banner">
    SCAFFOLD: EditorView · Phase 4 / U21-U30 — 3-column resizable layout: VideoStrip + SlideRail | Transcript | RightRail.
    4 tabs: AI · STT · Discrepancies · Audit. Session id: <code>{{ id }}</code>
  </div>
  <section class="card"><h1>Editor — {{ id }}</h1></section>
</template>
