<script setup lang="ts">
/**
 * frontend/src/components/help/HelpRelatedLinks.vue
 *
 * Purpose:
 *     Render `related_article_ids[]` as a chip list at the bottom of an
 *     article detail. Clicking a chip emits `select` with the related
 *     article id so the parent (HelpPanel or HelpEditor) can swap the
 *     currently-displayed article in-place.
 *
 *     Phase 3 ships the rendering + emit contract; the swap behavior on
 *     the panel side wires up in a follow-up when the panel switches
 *     from hardcoded HELP_CONTENT to the API.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §8.3 (X7)
 */
import { onMounted, ref } from 'vue';
import { getArticle, type HelpArticleDTO } from '@/services/helpArticlesApi';

const props = defineProps<{ relatedIds: string[] }>();
const emit = defineEmits<{ (e: 'select', id: string): void }>();

const related = ref<HelpArticleDTO[]>([]);
const loading = ref(false);

async function load(): Promise<void> {
  if (props.relatedIds.length === 0) {
    related.value = [];
    return;
  }
  loading.value = true;
  try {
    const fetched = await Promise.all(
      props.relatedIds.slice(0, 5).map((id) => getArticle(id).catch(() => null)),
    );
    related.value = fetched.filter((a): a is HelpArticleDTO => a !== null);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div v-if="related.length > 0" class="help-related-links">
    <div class="help-related-links__head">Related articles</div>
    <div class="help-related-links__chips">
      <button
        v-for="r in related"
        :key="r.id"
        type="button"
        class="help-related-links__chip"
        @click="emit('select', r.id)"
      >
        {{ r.title }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.help-related-links {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--border-subtle);
}
.help-related-links__head {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-steel);
  margin-bottom: 8px;
}
.help-related-links__chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.help-related-links__chip {
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  color: var(--color-navy);
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: all var(--duration-fast) var(--easing-out);
}
.help-related-links__chip:hover {
  background: var(--color-white);
  border-color: var(--color-blue);
  color: var(--color-blue);
}
</style>
