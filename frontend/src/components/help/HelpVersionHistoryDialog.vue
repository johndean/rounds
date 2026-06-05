<script setup lang="ts">
/**
 * frontend/src/components/help/HelpVersionHistoryDialog.vue
 *
 * Purpose:
 *     Admin-only modal that lists every prior version of an article and
 *     lets the admin restore one. Restore uses the existing PATCH route
 *     (not a dedicated restore endpoint) — the chosen snapshot is sent
 *     as the PATCH body, which appends a new version row containing the
 *     state right before the restore. This mirrors po.vin's pattern.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §8.3 (X4)
 */
import { computed, ref, watch } from 'vue';
import { listVersions, updateArticle, type HelpArticleDTO, type HelpArticleVersion } from '@/services/helpArticlesApi';
import { toast } from '@/composables/useToast';
import Icon from '@/components/shared/Icon.vue';

const props = defineProps<{ articleId: string; open: boolean }>();
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'restored', article: HelpArticleDTO): void;
}>();

const versions = ref<HelpArticleVersion[]>([]);
const loading = ref(false);
const restoring = ref<number | null>(null);
const err = ref<string | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  err.value = null;
  try {
    versions.value = await listVersions(props.articleId);
  } catch (e) {
    err.value = e instanceof Error ? e.message : 'Failed to load versions';
  } finally {
    loading.value = false;
  }
}

async function restore(v: HelpArticleVersion): Promise<void> {
  if (!confirm(`Restore article to version ${v.version}? This appends a new version with the snapshot.`)) return;
  restoring.value = v.version;
  try {
    const restored = await updateArticle(props.articleId, {
      title: v.snapshot.title,
      summary: v.snapshot.summary,
      category: v.snapshot.category,
      audience: v.snapshot.audience,
      feature_tags: v.snapshot.feature_tags,
      steps: v.snapshot.steps,
      related_article_ids: v.snapshot.related_article_ids,
      display_order: v.snapshot.display_order,
      is_published: v.snapshot.is_published,
      content_domain: v.snapshot.content_domain,
      workflow_slug: v.snapshot.workflow_slug,
    });
    toast.push(`Restored to v${v.version}`, { tone: 'success' });
    emit('restored', restored);
    void load();
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Restore failed', { tone: 'error' });
  } finally {
    restoring.value = null;
  }
}

watch(() => props.open, (open) => { if (open) void load(); });

const sortedVersions = computed(() =>
  [...versions.value].sort((a, b) => b.version - a.version),
);
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="vh-mask" role="dialog" aria-modal="true" @click.self="emit('close')">
      <div class="vh-dialog">
        <div class="vh-head">
          <h2 class="vh-title">Version history</h2>
          <button class="vh-close" type="button" aria-label="Close" @click="emit('close')">
            <Icon name="x" :size="14" />
          </button>
        </div>
        <div class="vh-body">
          <div v-if="err" class="vh-err">{{ err }}</div>
          <div v-else-if="loading" class="vh-loading">Loading…</div>
          <div v-else-if="sortedVersions.length === 0" class="vh-empty">No prior versions. The first edit will create version 1's snapshot.</div>
          <ol v-else class="vh-list">
            <li v-for="v in sortedVersions" :key="v.id" class="vh-row">
              <div class="vh-row__head">
                <span class="vh-row__v">v{{ v.version }}</span>
                <span class="vh-row__meta">
                  {{ v.edited_at ? new Date(v.edited_at).toLocaleString() : '' }}
                  · {{ v.edited_by || 'unknown' }}
                </span>
                <button
                  class="vh-row__restore"
                  type="button"
                  :disabled="restoring !== null"
                  @click="restore(v)"
                >
                  <Icon name="history" :size="12" />
                  {{ restoring === v.version ? 'Restoring…' : 'Restore' }}
                </button>
              </div>
              <div class="vh-row__title">{{ v.snapshot.title }}</div>
              <p class="vh-row__summary">{{ v.snapshot.summary }}</p>
            </li>
          </ol>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.vh-mask {
  position: fixed; inset: 0;
  background: rgba(0, 20, 50, 0.45);
  display: flex; align-items: center; justify-content: center;
  z-index: 900;
}
.vh-dialog {
  width: min(640px, 92vw);
  max-height: 80vh;
  background: var(--color-white);
  border-radius: 12px;
  box-shadow: 0 24px 60px rgba(0, 40, 85, 0.25);
  display: flex; flex-direction: column;
}
.vh-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-subtle);
}
.vh-title { margin: 0; font-size: 15px; font-weight: 800; color: var(--color-navy); }
.vh-close {
  width: 28px; height: 28px;
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
  background: transparent;
  color: var(--color-steel);
  cursor: pointer;
}
.vh-body { flex: 1; overflow-y: auto; padding: 14px 18px; }
.vh-err { color: #b91c1c; font-size: 13px; }
.vh-loading, .vh-empty { color: var(--color-steel); font-size: 13px; }
.vh-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.vh-row {
  padding: 10px 12px;
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
}
.vh-row__head {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 4px;
}
.vh-row__v {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 800;
  color: var(--color-navy);
  background: var(--color-light-steel);
  padding: 2px 6px;
  border-radius: 4px;
}
.vh-row__meta { font-size: 11px; color: var(--color-steel); flex: 1; }
.vh-row__restore {
  display: inline-flex; align-items: center; gap: 4px;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 700;
  color: var(--color-navy);
  cursor: pointer;
}
.vh-row__restore:hover { background: var(--color-light-steel); }
.vh-row__restore:disabled { opacity: 0.5; cursor: not-allowed; }
.vh-row__title { font-size: 13px; font-weight: 800; color: var(--color-navy); margin-bottom: 2px; }
.vh-row__summary { margin: 0; font-size: 12px; color: var(--color-steel); line-height: 1.4; }
</style>
