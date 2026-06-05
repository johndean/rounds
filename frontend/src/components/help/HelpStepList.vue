<script setup lang="ts">
/**
 * frontend/src/components/help/HelpStepList.vue
 *
 * Purpose:
 *     Read-only render of an article's `steps[]` as a numbered list.
 *     Used inside the Help panel detail view (Phase 4 wiring) and in the
 *     admin Version History snapshot preview. The edit-mode equivalent
 *     lives in HelpArticleEditorDialog.vue.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §8.3 (X8)
 */
import type { HelpStep } from '@/services/helpArticlesApi';

defineProps<{ steps: HelpStep[] }>();
</script>

<template>
  <ol v-if="steps.length > 0" class="help-steps">
    <li v-for="(s, i) in steps" :key="i" class="help-steps__item">
      <div class="help-steps__title">
        <span class="help-steps__n">{{ i + 1 }}</span>
        {{ s.title }}
      </div>
      <p class="help-steps__body">{{ s.body }}</p>
    </li>
  </ol>
</template>

<style scoped>
.help-steps {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  counter-reset: none;
}
.help-steps__item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
}
.help-steps__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 800;
  color: var(--color-navy);
}
.help-steps__n {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--color-navy);
  color: #fff;
  font-size: 11px;
  font-weight: 800;
}
.help-steps__body {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-steel);
  padding-left: 30px;
}
</style>
