/**
 * Sessions store — list + per-session detail. Backs SessionsView,
 * SessionDetailView, EditorView, and the dashboard counters.
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { sessions as sessionsApi, type SessionSummary, type SessionFilters } from '@/services/api';
import { ApiError } from '@/services/http';

export const useSessionsStore = defineStore('sessions', () => {
  const list = ref<SessionSummary[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const lastFilters = ref<SessionFilters>({});

  const total = computed(() => list.value.length);
  const byStatus = computed(() => {
    const out: Record<string, number> = {};
    for (const s of list.value) out[s.status] = (out[s.status] ?? 0) + 1;
    return out;
  });

  async function fetch(filters: SessionFilters = {}): Promise<void> {
    isLoading.value = true;
    error.value = null;
    lastFilters.value = filters;
    try {
      list.value = await sessionsApi.list(filters);
    } catch (e) {
      if (e instanceof ApiError) error.value = `${e.status}: ${JSON.stringify(e.body)}`;
      else error.value = e instanceof Error ? e.message : 'Failed to load sessions';
      list.value = [];
    } finally {
      isLoading.value = false;
    }
  }

  return { list, total, byStatus, isLoading, error, lastFilters, fetch };
});
