<script setup lang="ts">
/**
 * frontend/src/components/help/HelpFaqAccordion.vue
 *
 * Purpose:
 *     Single FAQ-category article rendered as an expandable accordion.
 *     The question is the article title; the answer is the summary +
 *     numbered steps inline. Cross-link chips appear at the bottom when
 *     related_article_ids is non-empty (X7).
 *
 *     Used by the FAQ tab in HelpPanel.vue when articles come from the
 *     /v1/help/articles API (Phase 5 cutover for faq-category items).
 *     HelpItem.vue is still used for the simpler q/a pairs the hardcoded
 *     fallback ships.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md ยง10.2
 */
import { ref, watch } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import type { HelpArticleDTO } from '@/services/helpArticlesApi';
import HelpStepList from '@/components/help/HelpStepList.vue';
import HelpRelatedLinks from '@/components/help/HelpRelatedLinks.vue';

const props = defineProps<{
  article: HelpArticleDTO;
  defaultOpen?: boolean;
}>();

const emit = defineEmits<{
  (e: 'open-related', articleId: string): void;
}>();

const open = ref(!!props.defaultOpen);
watch(() => props.article.id, () => { open.value = !!props.defaultOpen; });
</script>

<template>
  <div :class="['help-faq', { 'is-open': open }]">
    <button
      class="help-faq__q"
      type="button"
      :aria-expanded="open"
      @click="open = !open"
    >
      <span class="help-faq__q-text">{{ article.title }}</span>
      <span class="help-faq__chev" :style="open ? 'transform: rotate(180deg)' : ''">
        <Icon name="chevron-down" :size="12" />
      </span>
    </button>
    <div v-if="open" class="help-faq__a">
      <p v-if="article.summary" class="help-faq__summary">{{ article.summary }}</p>
      <HelpStepList v-if="article.steps && article.steps.length > 0" :steps="article.steps" />
      <HelpRelatedLinks
        v-if="article.related_article_ids && article.related_article_ids.length > 0"
        :related-ids="article.related_article_ids"
        @select="(id) => emit('open-related', id)"
      />
    </div>
  </div>
</template>

<style scoped>
.help-faq {
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: var(--color-white);
  overflow: hidden;
  transition: border-color var(--duration-fast) var(--easing-out);
}
.help-faq.is-open { border-color: var(--color-steel-hover); }

.help-faq__q {
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  padding: 10px 12px;
  display: flex; align-items: center; gap: 10px;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  color: var(--color-navy);
  cursor: pointer;
}
.help-faq.is-open .help-faq__q { background: var(--color-off-white); }
.help-faq__q-text { flex: 1; }
.help-faq__chev {
  width: 18px; height: 18px;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--color-steel);
  transition: transform var(--duration-fast) var(--easing-out);
}

.help-faq__a {
  padding: 12px;
  background: var(--color-white);
  border-top: 1px solid var(--border-subtle);
}
.help-faq__summary {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--color-steel);
}
</style>
