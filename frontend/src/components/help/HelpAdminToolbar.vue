<script setup lang="ts">
/**
 * frontend/src/components/help/HelpAdminToolbar.vue
 *
 * Purpose:
 *     Top-of-page toolbar inside the admin Help Editor. Phase 4 wires
 *     all five action buttons (plus Refresh) end-to-end:
 *       - New article (opens the dialog)
 *       - Publish all drafts (inline POST /v1/help/admin/bulk-publish;
 *         server runs CC-Rounds on each draft and publishes only the
 *         passing ones; the modal shows which drafts were skipped + why)
 *       - Fix CC-Rounds (enqueues fix_help_summaries_task)
 *       - Expand Steps (enqueues expand_help_steps_task)
 *       - Expand FAQs (enqueues expand_faq_steps_task)
 *
 *     All three Celery enqueues are fire-and-forget — the admin gets a
 *     toast confirming the task_id and is told to refresh the list in
 *     ~30 seconds to see the new drafts. (Phase 5 will wire a WS event
 *     so the list auto-refreshes on completion.)
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §9.3
 */
import { ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { toast } from '@/composables/useToast';
import {
  bulkPublishDrafts,
  fixSummaries,
  expandSteps,
  expandFaqs,
  type BulkPublishResponse,
} from '@/services/helpArticlesApi';

const emit = defineEmits<{
  (e: 'new'): void;
  (e: 'refresh'): void;
  (e: 'bulk-publish-done', summary: BulkPublishResponse): void;
}>();

const publishing = ref(false);
const fixing = ref(false);
const expandingHelp = ref(false);
const expandingFaqs = ref(false);

async function onPublishAll(): Promise<void> {
  if (publishing.value) return;
  if (!confirm('Publish every compliant draft? Drafts failing CC-Rounds stay as drafts.')) return;
  publishing.value = true;
  try {
    const res = await bulkPublishDrafts();
    const msg = res.published > 0
      ? `Published ${res.published} of ${res.total_attempted}.` + (res.skipped.length ? ` ${res.skipped.length} skipped.` : '')
      : `Nothing to publish — ${res.total_attempted} draft(s) all failed CC-Rounds.`;
    toast.push(msg, { tone: res.published > 0 ? 'success' : 'warn' });
    emit('bulk-publish-done', res);
    emit('refresh');
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Bulk publish failed', { tone: 'error' });
  } finally {
    publishing.value = false;
  }
}

async function onFixCc(): Promise<void> {
  if (fixing.value) return;
  if (!confirm('Queue Fix CC-Rounds? Every non-compliant summary will be rewritten by Gemini and saved as a new draft for your review.')) return;
  fixing.value = true;
  try {
    const res = await fixSummaries();
    toast.push(`Queued Fix CC-Rounds (task ${res.task_id.slice(0, 8)}). Refresh in ~30s to see new drafts.`, { tone: 'success' });
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Could not enqueue Fix CC-Rounds', { tone: 'error' });
  } finally {
    fixing.value = false;
  }
}

async function onExpandSteps(): Promise<void> {
  if (expandingHelp.value) return;
  if (!confirm('Queue Expand Steps? Non-FAQ articles with too few steps will get AI-drafted steps appended as drafts.')) return;
  expandingHelp.value = true;
  try {
    const res = await expandSteps();
    toast.push(`Queued Expand Steps (task ${res.task_id.slice(0, 8)}). Refresh in ~30s.`, { tone: 'success' });
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Could not enqueue Expand Steps', { tone: 'error' });
  } finally {
    expandingHelp.value = false;
  }
}

async function onExpandFaqs(): Promise<void> {
  if (expandingFaqs.value) return;
  if (!confirm('Queue Expand FAQs? FAQ articles with too few steps will get AI-drafted steps appended as drafts.')) return;
  expandingFaqs.value = true;
  try {
    const res = await expandFaqs();
    toast.push(`Queued Expand FAQs (task ${res.task_id.slice(0, 8)}). Refresh in ~30s.`, { tone: 'success' });
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Could not enqueue Expand FAQs', { tone: 'error' });
  } finally {
    expandingFaqs.value = false;
  }
}
</script>

<template>
  <div class="hat" role="toolbar" aria-label="Help admin toolbar">
    <button class="hat__btn hat__btn--primary" type="button" data-test-id="help-admin-new" @click="emit('new')">
      <Icon name="edit" :size="12" /> + New article
    </button>
    <button class="hat__btn" type="button" :disabled="publishing" data-test-id="help-admin-publish-all" @click="onPublishAll">
      <Icon name="check" :size="12" />
      {{ publishing ? 'Publishing…' : 'Publish all drafts' }}
    </button>
    <button class="hat__btn" type="button" :disabled="fixing" data-test-id="help-admin-fix-cc" @click="onFixCc">
      <Icon name="lightning" :size="12" />
      {{ fixing ? 'Queuing…' : 'Fix CC-Rounds' }}
    </button>
    <button class="hat__btn" type="button" :disabled="expandingHelp" data-test-id="help-admin-expand-steps" @click="onExpandSteps">
      <Icon name="list" :size="12" />
      {{ expandingHelp ? 'Queuing…' : 'Expand Steps' }}
    </button>
    <button class="hat__btn" type="button" :disabled="expandingFaqs" data-test-id="help-admin-expand-faqs" @click="onExpandFaqs">
      <Icon name="list" :size="12" />
      {{ expandingFaqs ? 'Queuing…' : 'Expand FAQs' }}
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
