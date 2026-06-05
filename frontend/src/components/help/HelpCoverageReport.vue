<script setup lang="ts">
/**
 * frontend/src/components/help/HelpCoverageReport.vue
 *
 * Purpose:
 *     Admin-only grid showing how many PUBLISHED articles exist per
 *     content_domain. Any domain with <2 published articles is flagged
 *     red ("needs coverage"). Mirrors po.vin's HelpCoverageReport
 *     pattern; threshold is a hardcoded 2 to match po.vin's locked
 *     constant (frontend SSOT — see plan §3 audit table).
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §8.3
 */
import { computed, onMounted, ref } from 'vue';
import { getCoverage, type HelpCoverageResponse } from '@/services/helpArticlesApi';

const COVERAGE_RED_THRESHOLD = 2;

const KNOWN_DOMAINS = [
  'sessions',
  'editor',
  'sop',
  'processing',
  'dashboard',
  'improvements',
  'settings',
  'general',
] as const;

const data = ref<HelpCoverageResponse | null>(null);
const loading = ref(false);
const err = ref<string | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  err.value = null;
  try {
    data.value = await getCoverage();
  } catch (e) {
    err.value = e instanceof Error ? e.message : 'Coverage load failed';
  } finally {
    loading.value = false;
  }
}

const rows = computed(() => {
  const byDomain = data.value?.by_domain ?? {};
  // Show known domains in canonical order; append any extras encountered.
  const seen = new Set<string>();
  const out: { domain: string; n: number; flagged: boolean }[] = [];
  for (const d of KNOWN_DOMAINS) {
    const n = byDomain[d] ?? 0;
    out.push({ domain: d, n, flagged: n < COVERAGE_RED_THRESHOLD });
    seen.add(d);
  }
  for (const [d, n] of Object.entries(byDomain)) {
    if (!seen.has(d)) out.push({ domain: d, n, flagged: n < COVERAGE_RED_THRESHOLD });
  }
  return out;
});

const flaggedCount = computed(() => rows.value.filter((r) => r.flagged).length);

onMounted(load);
defineExpose({ refresh: load });
</script>

<template>
  <section class="help-coverage" aria-label="Coverage by content domain">
    <div class="help-coverage__head">
      <h3 class="help-coverage__title">Coverage by content domain</h3>
      <span v-if="data" class="help-coverage__totals">
        {{ data.total_published }} published · {{ data.total_drafts }} drafts
        <span v-if="flaggedCount > 0" class="help-coverage__flag">
          · {{ flaggedCount }} domain{{ flaggedCount === 1 ? '' : 's' }} &lt; {{ COVERAGE_RED_THRESHOLD }} flagged red
        </span>
      </span>
    </div>
    <div v-if="err" class="help-coverage__err">{{ err }}</div>
    <div v-else-if="loading && !data" class="help-coverage__loading">Loading…</div>
    <div v-else class="help-coverage__grid">
      <div
        v-for="r in rows"
        :key="r.domain"
        :class="['help-coverage__cell', { 'is-flagged': r.flagged }]"
      >
        <span class="help-coverage__domain">{{ r.domain }}</span>
        <span class="help-coverage__count">{{ r.n }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.help-coverage { margin-bottom: 14px; }
.help-coverage__head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.help-coverage__title { margin: 0; font-size: 13px; font-weight: 800; color: var(--color-navy); }
.help-coverage__totals { font-size: 11px; color: var(--color-steel); }
.help-coverage__flag { color: #b91c1c; font-weight: 700; }
.help-coverage__loading, .help-coverage__err { font-size: 12px; color: var(--color-steel); padding: 8px 0; }
.help-coverage__err { color: #b91c1c; }
.help-coverage__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}
.help-coverage__cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  font-size: 12px;
}
.help-coverage__cell.is-flagged {
  border-color: #fca5a5;
  background: rgba(220, 38, 38, 0.04);
}
.help-coverage__cell.is-flagged .help-coverage__count {
  color: #b91c1c;
  font-weight: 800;
}
.help-coverage__domain {
  text-transform: capitalize;
  color: var(--color-navy);
  font-weight: 700;
}
.help-coverage__count {
  font-family: var(--font-mono);
  color: var(--color-steel);
  font-weight: 700;
}
</style>
