<script setup lang="ts">
/**
 * Dashboard (F pattern). IMPLEMENTATION.md §9.
 * Phase 3 / U13. Live KPIs hydrated from /v1/sessions + /v1/improvements.
 * Full layout (pipeline rails + SLA grid + 3-widget rows) ships when prototype
 * CSS bundle lands; this is the working dataflow surface.
 */
import { computed, onMounted } from 'vue';
import { useSessionsStore } from '@/stores/sessions';
import { useImprovementsStore } from '@/stores/improvements';
import { useAuthStore } from '@/stores/auth';

const sessionsStore = useSessionsStore();
const improvementsStore = useImprovementsStore();
const auth = useAuthStore();

const greeting = computed(() => {
  const h = new Date().getHours();
  const prefix = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
  const name = auth.email?.split('@')[0] ?? 'there';
  return `${prefix}, ${name}.`;
});

const today = computed(() =>
  new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }),
);

const kpis = computed(() => [
  { label: 'AI Sessions',          value: sessionsStore.byStatus['ready']      ?? 0 },
  { label: 'In Ingest',            value: sessionsStore.byStatus['ingesting']  ?? 0 },
  { label: 'Failed',               value: sessionsStore.byStatus['failed']     ?? 0 },
  { label: 'Improvement Requests', value: improvementsStore.filteredCount },
  { label: 'Pending Improvements', value: improvementsStore.countsByStatus['pending'] ?? 0 },
  { label: 'Approved',             value: improvementsStore.countsByStatus['approved'] ?? 0 },
]);

onMounted(() => {
  void sessionsStore.fetch();
  void improvementsStore.fetch();
});
</script>

<template>
  <div class="dashboard">
    <div class="dashboard__eyebrow mono uppercase">{{ today }}</div>
    <h1 class="dashboard__greeting">{{ greeting }}</h1>
    <p class="dashboard__lead">
      AI processing pipeline + SOP control layer. Pipeline rails + SLA grid land with
      the prototype CSS bundle; live KPIs below are pulled from the production API.
    </p>

    <section class="kpi-strip">
      <div v-for="k in kpis" :key="k.label" class="kpi" :data-test-id="`kpi-${k.label.toLowerCase().replace(/ /g,'-')}`">
        <div class="kpi__value">{{ k.value }}</div>
        <div class="kpi__label">{{ k.label }}</div>
      </div>
    </section>

    <section class="card">
      <h2 style="margin: 0 0 var(--space-3); font-size: var(--fs-lg); font-weight: var(--fw-extrabold);">
        Your Queue
      </h2>
      <p v-if="sessionsStore.isLoading" style="color: var(--fg2);">Loading sessions…</p>
      <p v-else-if="sessionsStore.error" style="color: var(--color-red);">
        Failed to load sessions: {{ sessionsStore.error }}
      </p>
      <p v-else-if="sessionsStore.total === 0" style="color: var(--fg2);">
        No sessions yet. Upload your first lecture from <RouterLink to="/upload">/upload</RouterLink>.
      </p>
      <ul v-else style="margin: 0; padding-left: var(--space-5);">
        <li v-for="s in sessionsStore.list.slice(0, 5)" :key="s.id">
          <RouterLink :to="`/s/${s.id}`"><span class="mono">{{ s.code }}</span></RouterLink> &middot;
          {{ s.title }} &middot;
          <span class="chip">{{ s.status }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.dashboard {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
.dashboard__eyebrow {
  font-size: var(--fs-xs);
  color: var(--fg2);
  opacity: 0.85;
}
.dashboard__greeting {
  margin: 0;
  font-size: var(--fs-3xl);
  font-weight: var(--fw-extrabold);
  color: var(--fg1);
}
.dashboard__lead { margin: 0; color: var(--fg2); font-size: var(--fs-sm); max-width: 720px; }
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--space-3);
}
.kpi {
  background: var(--surface-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  box-shadow: var(--shadow-sm);
}
.kpi__value {
  font-size: var(--fs-2xl);
  font-weight: var(--fw-extrabold);
  color: var(--color-navy);
  line-height: 1;
}
.kpi__label {
  margin-top: var(--space-2);
  font-size: var(--fs-2xs);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
  color: var(--fg2);
}
@media (max-width: 1100px) {
  .kpi-strip { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 720px) {
  .kpi-strip { grid-template-columns: repeat(2, 1fr); }
}
</style>
