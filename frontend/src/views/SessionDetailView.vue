<script setup lang="ts">
/**
 * Session Detail (mixed). IMPLEMENTATION.md §7.
 * Phase 8 part 3 — live-hydrated from /v1/sessions/{id} + /v1/sessions/{id}/segments
 * + /v1/sessions/{id}/sop.
 */
import { onMounted, ref } from 'vue';
import { sessions as sessionsApi, segments as segmentsApi, sop as sopApi, type SessionSummary, type SegmentRow } from '@/services/api';
import { ApiError } from '@/services/http';

const props = defineProps<{ id: string }>();

const session = ref<SessionSummary | null>(null);
const segs    = ref<SegmentRow[]>([]);
const sopState = ref<{ current_stage: string; is_blocked: boolean } | null>(null);
const error = ref<string | null>(null);
const loading = ref(true);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [s, segRows, sop] = await Promise.allSettled([
      sessionsApi.get(props.id),
      segmentsApi.list(props.id),
      sopApi.state(props.id),
    ]);
    if (s.status === 'fulfilled')   session.value  = s.value;
    if (segRows.status === 'fulfilled') segs.value     = segRows.value;
    if (sop.status === 'fulfilled') sopState.value = sop.value as { current_stage: string; is_blocked: boolean };
    if (s.status === 'rejected') {
      const e = s.reason;
      if (e instanceof ApiError && e.status === 404) error.value = 'Session not found';
      else error.value = e instanceof Error ? e.message : 'Failed to load';
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load';
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="session-detail">
    <header v-if="session" class="session-detail__header">
      <div>
        <RouterLink to="/sessions" style="color: var(--fg2); font-size: var(--fs-xs); text-decoration: none;">
          ← Sessions
        </RouterLink>
        <h1 style="margin: var(--space-1) 0 0;">
          <span class="mono" style="color: var(--color-navy); font-size: var(--fs-sm);">{{ session.code }}</span><br>
          {{ session.title }}
        </h1>
      </div>
      <div style="display: flex; gap: var(--space-2);">
        <RouterLink :to="`/e/${session.id}`" class="btn btn--primary">Open Editor →</RouterLink>
        <RouterLink :to="`/e/${session.id}/sop`" class="btn">SOP Workflow</RouterLink>
        <RouterLink :to="`/e/${session.id}/audit`" class="btn">Audit</RouterLink>
      </div>
    </header>

    <p v-if="loading" style="color: var(--fg2);">Loading…</p>
    <p v-else-if="error" style="color: var(--color-red);">{{ error }}</p>

    <template v-if="session && !loading">
      <section class="kpi-grid">
        <div class="card kpi"><div class="kpi__value">{{ segs.length }}</div><div class="kpi__label">Segments</div></div>
        <div class="card kpi"><div class="kpi__value">{{ session.word_count ?? '—' }}</div><div class="kpi__label">Words</div></div>
        <div class="card kpi">
          <div class="kpi__value">{{ session.duration_sec ? Math.round(session.duration_sec / 60) : '—' }}<small style="font-size: var(--fs-sm); margin-left: 2px;">min</small></div>
          <div class="kpi__label">Duration</div>
        </div>
        <div class="card kpi"><div class="kpi__value">{{ session.attendee_count ?? '—' }}</div><div class="kpi__label">Attendees</div></div>
        <div class="card kpi"><div class="kpi__value"><span class="chip">{{ session.status }}</span></div><div class="kpi__label">Status</div></div>
      </section>

      <section class="card">
        <h2 style="margin: 0 0 var(--space-3); font-size: var(--fs-lg); font-weight: var(--fw-extrabold);">SOP Workflow</h2>
        <p v-if="!sopState" style="margin: 0; color: var(--fg2);">No SOP state yet.</p>
        <p v-else style="margin: 0; font-size: var(--fs-sm);">
          Current stage: <span class="chip" style="background: var(--color-warm-light);">{{ sopState.current_stage }}</span>
          <span v-if="sopState.is_blocked" class="chip" style="background: rgba(197,70,68,0.15); color: var(--color-red); margin-left: var(--space-2);">BLOCKED</span>
        </p>
      </section>

      <section class="card">
        <h2 style="margin: 0 0 var(--space-3); font-size: var(--fs-lg); font-weight: var(--fw-extrabold);">
          Segments ({{ segs.length }})
        </h2>
        <p v-if="!segs.length" style="margin: 0; color: var(--fg2);">No segments yet — ingest hasn't run.</p>
        <ul v-else style="list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: var(--space-2);">
          <li v-for="s in segs.slice(0, 10)" :key="s.id" style="display: grid; grid-template-columns: 80px 1fr auto; gap: var(--space-3); padding: var(--space-2); border-bottom: 1px solid var(--border-subtle);">
            <span class="mono" style="color: var(--fg2); font-size: var(--fs-xs);">{{ Math.floor(s.start_ms/60000).toString().padStart(2,'0') }}:{{ Math.floor((s.start_ms%60000)/1000).toString().padStart(2,'0') }}</span>
            <span style="font-size: var(--fs-sm);">{{ s.text }}</span>
            <span v-if="s.confidence !== null" class="mono" style="color: var(--fg2); font-size: var(--fs-xs);">{{ (s.confidence * 100).toFixed(0) }}%</span>
          </li>
        </ul>
        <p v-if="segs.length > 10" style="margin: var(--space-3) 0 0; color: var(--fg2); font-size: var(--fs-xs);">+ {{ segs.length - 10 }} more</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.session-detail { padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-5); }
.session-detail__header {
  display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4);
}
.session-detail__header h1 { margin: 0; font-size: var(--fs-xl); font-weight: var(--fw-extrabold); line-height: 1.2; }
.kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: var(--space-3); }
.kpi { padding: var(--space-4); }
.kpi__value { font-size: var(--fs-xl); font-weight: var(--fw-extrabold); color: var(--color-navy); line-height: 1; }
.kpi__label { margin-top: var(--space-2); font-size: var(--fs-2xs); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--fg2); }
@media (max-width: 900px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
