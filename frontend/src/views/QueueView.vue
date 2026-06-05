<script setup lang="ts">
/**
 * QueueView — per-user work queue.
 *
 * Sessions where the current user is the assignee for the session's
 * CURRENT SOP stage. Sourced from GET /v1/queue/mine (Phase 7-broader
 * 2 of 2). Ordered server-side by entered_current_at ascending so the
 * longest-waiting items surface first; client doesn't re-sort.
 *
 * Each row shows: code · title · current stage · time-in-stage · an
 * "OVERDUE" pill when past SLA. Click a row to navigate to the
 * session's SOP tab so the user can act on the queue item.
 */
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { queue as queueApi, type QueueItem } from '@/services/api';
import { toast } from '@/composables/useToast';

const router = useRouter();

const items = ref<QueueItem[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    items.value = await queueApi.mine();
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load queue';
    toast.push(error.value, { tone: 'error' });
  } finally {
    loading.value = false;
  }
}
onMounted(load);

function displayTitle(it: QueueItem): string {
  return (it.title_long || it.title_short || it.title || '(untitled)').trim();
}

function hoursInStage(it: QueueItem): string {
  if (!it.entered_current_at) return '—';
  const entered = new Date(it.entered_current_at).getTime();
  const now = Date.now();
  // Math.max guard against client clock skew — without it a laptop
  // whose clock is ~5 min behind the server would render "-5m" which
  // looks like a bug.
  const h = Math.max(0, (now - entered) / 1000 / 3600);
  if (h < 1) return `${Math.round(h * 60)}m`;
  if (h < 24) return `${h.toFixed(1)}h`;
  return `${Math.floor(h / 24)}d ${Math.floor(h % 24)}h`;
}

function openItem(it: QueueItem): void {
  router.push(`/e/${it.session_id}/sop`);
}

const overdueCount = computed<number>(() =>
  items.value.filter(it => typeof it.overdue_hours === 'number' && it.overdue_hours > 0).length,
);
</script>

<template>
  <main class="route" data-test-id="route-queue">
    <header class="route__header">
      <div>
        <h1>My queue</h1>
        <p class="route__subtitle">
          Sessions where you're the current-stage assignee. Click any row to open its SOP tab.
        </p>
      </div>
      <div class="route__header-meta">
        <span class="chip chip--ghost" data-test-id="queue-count">{{ items.length }} item{{ items.length === 1 ? '' : 's' }}</span>
        <span v-if="overdueCount > 0" class="chip chip--amber" data-test-id="queue-overdue-count">{{ overdueCount }} overdue</span>
      </div>
    </header>

    <div v-if="loading" class="route__loading">Loading…</div>
    <div v-else-if="error" class="route__error">{{ error }}</div>
    <div v-else-if="items.length === 0" class="route__empty" data-test-id="queue-empty">
      <p><strong>You have no pending items.</strong></p>
      <p>Sessions assigned to you at their current stage will appear here.</p>
    </div>
    <div v-else class="queue-list">
      <button
        v-for="it in items"
        :key="it.session_id"
        type="button"
        class="queue-row"
        :class="{ 'queue-row--overdue': (it.overdue_hours ?? 0) > 0 }"
        :data-test-id="`queue-row-${it.code}`"
        @click="openItem(it)"
      >
        <div class="queue-row__main">
          <div class="queue-row__hd">
            <span class="queue-row__code">{{ it.code }}</span>
            <span class="queue-row__title">{{ displayTitle(it) }}</span>
          </div>
          <div class="queue-row__meta">
            <span class="queue-row__stage">{{ it.current_stage }}</span>
            <span class="queue-row__sep">·</span>
            <span class="queue-row__age">{{ hoursInStage(it) }} in stage</span>
            <span
              v-if="(it.overdue_hours ?? 0) > 0"
              class="queue-row__overdue-pill"
              :data-test-id="`queue-row-${it.code}-overdue`"
            >+{{ it.overdue_hours }}h OVERDUE</span>
          </div>
        </div>
        <div class="queue-row__action">Open →</div>
      </button>
    </div>
  </main>
</template>

<style scoped>
.route {
  max-width: 880px; margin: 0 auto; padding: 24px 20px;
  font-family: var(--font-family); color: var(--fg1, #002855);
}
.route__header {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px; margin-bottom: 16px;
}
.route__header h1 { margin: 0 0 4px; font-size: 22px; }
.route__subtitle { margin: 0; color: var(--fg2, #6b7280); font-size: 13px; }
.route__header-meta { display: flex; gap: 8px; }
.route__loading, .route__error, .route__empty {
  padding: 24px; text-align: center; color: var(--fg2, #6b7280);
  background: var(--surface, #fff); border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
}
.route__error { color: var(--color-red, #b00); }

.queue-list { display: flex; flex-direction: column; gap: 6px; }
.queue-row {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; text-align: left; cursor: pointer;
  background: var(--surface, #fff); border: 1px solid var(--border, #e5e7eb);
  border-radius: 6px; color: inherit; font: inherit;
  transition: background 0.12s ease-out, border-color 0.12s ease-out;
}
.queue-row:hover { background: var(--surface-hover, #f7f7f7); border-color: var(--border-strong, #d4d4d8); }
.queue-row--overdue { border-left: 3px solid var(--color-amber, #B45A1A); }
.queue-row__main { flex: 1; min-width: 0; }
.queue-row__hd { display: flex; align-items: baseline; gap: 8px; }
.queue-row__code {
  font-family: var(--font-mono, monospace); font-size: 11px;
  color: var(--fg2, #6b7280); font-weight: 700;
}
.queue-row__title {
  font-size: 14px; font-weight: 600; color: var(--fg1, #002855);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.queue-row__meta { display: flex; align-items: center; gap: 6px; margin-top: 4px; font-size: 12px; color: var(--fg2, #6b7280); }
.queue-row__stage { font-weight: 600; }
.queue-row__sep { opacity: 0.5; }
.queue-row__overdue-pill {
  margin-left: 4px; padding: 2px 6px; border-radius: 3px;
  background: var(--color-amber-bg, #FEF3C7); color: var(--color-amber, #B45A1A);
  font-size: 10.5px; font-weight: 700; letter-spacing: 0.04em;
}
.queue-row__action {
  font-size: 12px; color: var(--color-blue, #0861CE); font-weight: 600;
}
</style>
