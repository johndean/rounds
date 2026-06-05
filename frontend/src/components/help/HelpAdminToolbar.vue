<script setup lang="ts">
/**
 * frontend/src/components/help/HelpAdminToolbar.vue
 *
 * Purpose:
 *     Top-of-page toolbar inside the admin Help Editor. Phase 3 ships
 *     three buttons: New article, Publish all eligible drafts, Refresh.
 *     Phase 4 will add the bulk-AI buttons (Fix CC-Rounds / Expand Steps
 *     / Expand FAQs) and the Coverage Report toggle.
 *
 *     "Publish all eligible drafts" is intentionally NOT wired in Phase 3
 *     — that requires the CC-Rounds compliance check (Phase 4). The
 *     button slot is visible but disabled with a tooltip explaining
 *     when it lights up.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §8.3
 */
import Icon from '@/components/shared/Icon.vue';

defineProps<{
  isPublishingAll?: boolean;
}>();

const emit = defineEmits<{
  (e: 'new'): void;
  (e: 'refresh'): void;
}>();
</script>

<template>
  <div class="hat" role="toolbar" aria-label="Help admin toolbar">
    <button class="hat__btn hat__btn--primary" type="button" @click="emit('new')">
      <Icon name="edit" :size="12" /> + New article
    </button>
    <button class="hat__btn" type="button" disabled title="Bulk publish ships in Phase 4 with CC-Rounds compliance.">
      <Icon name="check" :size="12" /> Publish all drafts
    </button>
    <button class="hat__btn" type="button" disabled title="Bulk AI rewrite ships in Phase 4.">
      <Icon name="lightning" :size="12" /> Fix CC-Rounds
    </button>
    <button class="hat__btn" type="button" disabled title="Bulk AI expansion ships in Phase 4.">
      <Icon name="list" :size="12" /> Expand Steps
    </button>
    <button class="hat__btn" type="button" disabled title="Bulk AI expansion ships in Phase 4.">
      <Icon name="list" :size="12" /> Expand FAQs
    </button>
    <button class="hat__btn hat__btn--ghost" type="button" aria-label="Refresh list" @click="emit('refresh')">
      <Icon name="history" :size="12" /> Refresh
    </button>
  </div>
</template>

<style scoped>
.hat {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin-bottom: 14px;
}
.hat__btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 700;
  color: var(--color-navy);
  cursor: pointer;
}
.hat__btn:hover { background: var(--color-white); }
.hat__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.hat__btn--primary {
  background: var(--color-navy);
  color: #fff;
  border-color: var(--color-navy);
}
.hat__btn--primary:hover { background: var(--color-navy-deep); color: #fff; }
.hat__btn--ghost {
  background: transparent;
  border-color: transparent;
}
</style>
