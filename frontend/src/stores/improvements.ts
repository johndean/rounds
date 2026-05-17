/**
 * Improvements store — list + per-row detail + wizard payload management.
 * Backs ImprovementsView master/detail (IMPLEMENTATION.md §13).
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { improvements as imprApi, type ImprovementSummary } from '@/services/api';
import { ApiError } from '@/services/http';

export const useImprovementsStore = defineStore('improvements', () => {
  const list = ref<ImprovementSummary[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const activeStatus = ref<string>('all');

  const filteredCount = computed(() => list.value.length);
  const countsByStatus = computed(() => {
    const out: Record<string, number> = {};
    for (const i of list.value) out[i.status] = (out[i.status] ?? 0) + 1;
    return out;
  });

  async function fetch(statusFilter?: string): Promise<void> {
    isLoading.value = true;
    error.value = null;
    if (statusFilter !== undefined) activeStatus.value = statusFilter;
    try {
      const f = activeStatus.value === 'all' ? undefined : activeStatus.value;
      list.value = await imprApi.list(f);
    } catch (e) {
      if (e instanceof ApiError) error.value = `${e.status}`;
      else error.value = e instanceof Error ? e.message : 'Failed';
      list.value = [];
    } finally {
      isLoading.value = false;
    }
  }

  async function suggest(payload: Parameters<typeof imprApi.suggest>[0]): Promise<ImprovementSummary | null> {
    try {
      const row = await imprApi.suggest(payload);
      list.value = [row, ...list.value];
      return row;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Suggest failed';
      return null;
    }
  }

  return { list, isLoading, error, activeStatus, filteredCount, countsByStatus, fetch, suggest };
});
