<script setup lang="ts">
/**
 * Sessions list (B pattern). IMPLEMENTATION.md §6 / §9.
 * Reads ?stage / ?ai / ?f query params, hits /v1/sessions, renders ActiveFilterChip.
 */
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSessionsStore } from '@/stores/sessions';

const route = useRoute();
const router = useRouter();
const store = useSessionsStore();

const filters = computed(() => ({
  stage: route.query.stage as string | undefined,
  ai:    route.query.ai    as string | undefined,
  f:     route.query.f     as string | undefined,
}));

const activeFilterLabel = computed(() => {
  if (filters.value.stage) return `SOP: ${filters.value.stage}`;
  if (filters.value.ai)    return `AI: ${filters.value.ai}`;
  if (filters.value.f)     return `Search: ${filters.value.f}`;
  return null;
});

function clearFilters(): void {
  router.replace({ path: '/sessions' });
}

watch(filters, (f) => store.fetch(f), { deep: true });
onMounted(() => store.fetch(filters.value));
</script>

<template>
  <div class="sessions">
    <header class="sessions__header">
      <div>
        <h1 style="margin: 0; font-size: var(--fs-xl); font-weight: var(--fw-extrabold);">Sessions</h1>
        <p style="margin: var(--space-1) 0 0; color: var(--fg2); font-size: var(--fs-sm);">
          {{ store.total }} session{{ store.total === 1 ? '' : 's' }}
        </p>
      </div>
      <button
        v-if="activeFilterLabel"
        class="chip"
        style="cursor: pointer; background: var(--color-navy); color: var(--fg-on-dark); border-color: var(--color-navy);"
        data-test-id="active-filter-chip"
        @click="clearFilters"
      >
        {{ activeFilterLabel }} ×
      </button>
    </header>

    <section class="card">
      <p v-if="store.isLoading" style="margin: 0; color: var(--fg2);">Loading…</p>
      <p v-else-if="store.error" style="margin: 0; color: var(--color-red);">{{ store.error }}</p>
      <p v-else-if="store.total === 0" style="margin: 0; color: var(--fg2);">
        No sessions match{{ activeFilterLabel ? ' the active filter' : '' }}.
      </p>
      <table v-else class="sessions__table">
        <thead>
          <tr>
            <th>Code</th>
            <th>Title</th>
            <th>Presenter</th>
            <th>Status</th>
            <th style="text-align: right;">Segments</th>
            <th style="text-align: right;">Words</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in store.list" :key="s.id">
            <td><RouterLink :to="`/s/${s.id}`"><span class="mono">{{ s.code }}</span></RouterLink></td>
            <td>{{ s.title }}</td>
            <td>{{ s.presenter ?? '—' }}</td>
            <td><span class="chip">{{ s.status }}</span></td>
            <td style="text-align: right;">{{ s.segment_count ?? '—' }}</td>
            <td style="text-align: right;">{{ s.word_count ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.sessions { padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-5); }
.sessions__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
}
.sessions__table { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
.sessions__table th,
.sessions__table td { padding: var(--space-3); border-bottom: 1px solid var(--border-subtle); text-align: left; }
.sessions__table th { color: var(--fg2); font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: var(--tracking-wide); font-weight: var(--fw-medium); }
</style>
