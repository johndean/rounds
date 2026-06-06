<script setup lang="ts">
/**
 * EditorSkeleton — shown while EditorView's initial fetches are in flight.
 *
 * Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 1.
 * Audit IDs closed: E3 (loading indicator on editor).
 *
 * Purely CSS — no animations beyond the existing app.css `.skeleton-block`
 * shimmer. Zero JS cost, zero re-render impact on the karaoke watcher.
 */
</script>

<template>
  <div class="editor__skeleton" data-test-id="editor-skeleton" aria-busy="true" aria-label="Loading editor">
    <div class="editor__skeleton-topbar">
      <span class="skeleton-block" style="width: 220px; height: 14px;" />
      <span class="skeleton-block" style="width: 80px; height: 14px;" />
    </div>
    <div class="editor__skeleton-grid">
      <aside class="editor__skeleton-rail">
        <span class="skeleton-block" v-for="i in 8" :key="i" style="width: 100%; height: 60px; margin-bottom: 8px;" />
      </aside>
      <main class="editor__skeleton-main">
        <span class="skeleton-block" style="width: 100%; height: 42px; margin-bottom: 12px;" />
        <span class="skeleton-block" v-for="i in 10" :key="i" style="width: 100%; height: 46px; margin-bottom: 6px;" />
      </main>
      <aside class="editor__skeleton-side">
        <span class="skeleton-block" v-for="i in 4" :key="i" style="width: 100%; height: 110px; margin-bottom: 10px;" />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.editor__skeleton {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface, #fff);
  padding: 12px 16px;
  gap: 12px;
}
.editor__skeleton-topbar {
  display: flex;
  gap: 12px;
  align-items: center;
}
.editor__skeleton-grid {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr) 320px;
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.editor__skeleton-rail,
.editor__skeleton-main,
.editor__skeleton-side {
  overflow: hidden;
}
:deep(.skeleton-block) {
  display: inline-block;
  background: linear-gradient(90deg, rgba(0,0,0,0.04) 0%, rgba(0,0,0,0.08) 50%, rgba(0,0,0,0.04) 100%);
  background-size: 200% 100%;
  animation: editor-skeleton-shimmer 1.6s infinite linear;
  border-radius: 6px;
  vertical-align: middle;
}
@keyframes editor-skeleton-shimmer {
  0%   { background-position: 0% 0%; }
  100% { background-position: -200% 0%; }
}
</style>
