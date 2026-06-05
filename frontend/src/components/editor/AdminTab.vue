<script setup lang="ts">
/**
 * AdminTab — right-rail "Admin" sub-tab: timeline minimap + per-slide segment
 * list + instructor card + IIL signal previews (cadence / filler ratio).
 *
 * Instructor card pulls from real session_speakers (first row, preferred a
 * speaker with role='moderator'). If none, the card is hidden — no fixture
 * lies. IIL signals likewise only render when real data exists.
 *
 * Phase A5 (2026-06-05): adds a Rescue section gated by isAdmin (current
 * user email === LEGACY_ADMIN_EMAIL). Exposes 5 operator endpoints from
 * /v1/diag/* with native browser confirmation prompts. Server gates the
 * routes via CurrentUser; the v-if here is a UX guard so non-admins don't
 * see destructive buttons.
 *
 * Related ADRs: ADR-001 (admin gate), ADR-006 (operator rescue routes).
 * Related business rules: BR-001 (LEGACY_ADMIN_EMAIL — UX gate mirrors
 * server gate; server is the authoritative check).
 */
import { computed, ref } from 'vue';
import { slideAccent, type Slide, type Segment } from '@/fixtures/transcript';
import { withAlpha, fmtTime } from '@/utils/editorHelpers';
import { useAuthStore } from '@/stores/auth';
import { diag } from '@/services/api';
import { toast } from '@/composables/useToast';

interface IilSignals {
  cadence_wpm?: number | null;
  filler_ratio?: number | null;
}

const props = defineProps<{
  slide: Slide | null | undefined;
  segments: readonly Segment[];
  time: number;
  totalDuration: number;
  slides: readonly Slide[];
  iil?: IilSignals | null;
  sessionId: string;
}>();

const auth = useAuthStore();
// Mirrors app/security/roles.py::LEGACY_ADMIN_EMAIL. When a real role
// flag lands, swap this for a server-driven check.
const LEGACY_ADMIN_EMAIL = 'johndean@vin.com';
const isAdmin = computed(() => (auth.email ?? '').toLowerCase() === LEGACY_ADMIN_EMAIL);

const rescuing = ref<string | null>(null);

interface RescueAction {
  id: string;
  label: string;
  desc: string;
  destructive: boolean;
  confirmMsg: string;
  call: (sid: string) => Promise<unknown>;
}
const rescueActions: RescueAction[] = [
  { id: 'reingest',          label: 'Re-ingest pipeline',     desc: 'Reset status → uploading and re-run the entire ingest pipeline.', destructive: true,  confirmMsg: 'Re-ingest this session? This resets status to uploading and re-runs the entire pipeline.',                   call: diag.reingest },
  { id: 'realign',           label: 'Re-run alignment',       desc: 'Trigger lcs_discrepancies_task to repopulate word_alignment.',     destructive: false, confirmMsg: 'Re-run word alignment on this session?',                                                                          call: diag.realign },
  { id: 'init-stages',       label: 'Initialize SOP stages',  desc: 'Fire session_stage_assignees init for legacy sessions.',           destructive: false, confirmMsg: 'Initialize SOP stage assignees for this session?',                                                                call: diag.initSessionStages },
  { id: 'autoplace-polls',   label: 'Auto-place polls',       desc: 'Backfill poll placements onto their declared slide segments.',     destructive: false, confirmMsg: 'Auto-place polls for this session?',                                                                              call: diag.autoplacePolls },
  { id: 'abort',             label: 'Force-abort session',    desc: 'Set status → failed and kill any in-flight Celery task.',          destructive: true,  confirmMsg: 'Force-abort this session? Status becomes failed and any in-flight Celery task will be revoked. This is destructive.', call: diag.abortSession },
];

async function runRescue(action: RescueAction): Promise<void> {
  if (rescuing.value) return;
  // Native browser confirm — surgical, zero new deps, and the modal
  // affirmance is the load-bearing UX bit. Replace with a styled
  // modal later if we want to.
  if (!window.confirm(action.confirmMsg)) return;
  rescuing.value = action.id;
  try {
    await action.call(props.sessionId);
    toast.push(`${action.label}: dispatched`, { tone: 'success' });
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Request failed';
    toast.push(`${action.label} failed — ${msg}`, { tone: 'error' });
  } finally {
    rescuing.value = null;
  }
}

const accent = computed(() => (props.slide ? slideAccent(props.slide.id) : '#4D6995'));

interface MapRect { id: string; x: number; w: number; fill: string; isCurrent: boolean; }
const minimapRects = computed<MapRect[]>(() => {
  if (!props.slide) return [];
  const out: MapRect[] = [];
  props.slides.forEach((s) => {
    const sSegs = props.segments.filter((g) => g.slide_id === s.id);
    if (!sSegs.length) return;
    const x1 = (sSegs[0]!.start / props.totalDuration) * 200;
    const x2 = (sSegs[sSegs.length - 1]!.end / props.totalDuration) * 200;
    const isCurrent = s.id === props.slide!.id;
    const a = slideAccent(s.id);
    out.push({
      id: s.id,
      x: x1,
      w: Math.max(1, x2 - x1),
      fill: isCurrent ? a : withAlpha(a, '55'),
      isCurrent,
    });
  });
  return out;
});

const headLeft = computed(() => `${(props.time / props.totalDuration) * 100}%`);

const slideSegs = computed<Segment[]>(() =>
  props.slide ? props.segments.filter((s) => s.slide_id === props.slide!.id) : []
);

function isActive(s: Segment): boolean {
  // Boundary-preferring: same rule as EditorView.activeSegment so clicks /
  // playback crossings don't keep the previous segment lit for 250 ms.
  const all = props.segments;
  const idx = all.indexOf(s);
  if (idx < 0) return false;
  const next = all[idx + 1];
  return props.time >= s.start && (!next || props.time < next.start);
}

function segStyle(s: Segment): Record<string, string | number> {
  const active = isActive(s);
  return {
    background: active ? withAlpha(accent.value, '33') : withAlpha(accent.value, '12'),
    borderLeftColor: accent.value,
    borderLeftWidth: active ? '3px' : '2px',
  };
}
</script>

<template>
  <div v-if="!slide" :style="{ fontSize: '12px', color: 'var(--fg2)' }">No active slide.</div>
  <div v-else>
    <div class="rightrail__sectionhead">Timeline · session map</div>
    <div class="minimap" aria-label="Session timeline minimap" :style="{ marginBottom: '12px' }">
      <svg viewBox="0 0 200 20" preserveAspectRatio="none">
        <rect
          v-for="r in minimapRects"
          :key="r.id"
          :x="r.x"
          y="4"
          :width="r.w"
          height="12"
          :fill="r.fill"
          :stroke="r.isCurrent ? r.fill : 'none'"
          :stroke-width="r.isCurrent ? 0.5 : 0"
        />
      </svg>
      <div class="minimap__head" :style="{ left: headLeft }" />
    </div>

    <div class="rightrail__sectionhead">Segments on this slide · {{ slideSegs.length }}</div>
    <ul class="admin-segment-list">
      <li v-for="s in slideSegs" :key="s.id" :style="segStyle(s)">
        <span class="t" :style="{ color: accent }">{{ fmtTime(s.start) }}</span>
        <span :style="{ display: '-webkit-box', '-webkit-line-clamp': 1, '-webkit-box-orient': 'vertical', overflow: 'hidden' }">{{ s.text }}</span>
      </li>
    </ul>

    <template v-if="iil && (iil.cadence_wpm != null || iil.filler_ratio != null)">
      <div class="rightrail__sectionhead">IIL signals</div>
      <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '11px' }">
        <div v-if="iil.cadence_wpm != null" :style="{ padding: '6px 8px', background: 'var(--surface-bg)', border: '1px solid var(--border-subtle)', borderRadius: '6px' }">
          <div :style="{ color: 'var(--fg2)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 700 }">Cadence</div>
          <div :style="{ fontSize: '12px', fontWeight: 700, color: 'var(--fg1)' }">{{ Math.round(iil.cadence_wpm) }} wpm</div>
        </div>
        <div v-if="iil.filler_ratio != null" :style="{ padding: '6px 8px', background: 'var(--surface-bg)', border: '1px solid var(--border-subtle)', borderRadius: '6px' }">
          <div :style="{ color: 'var(--fg2)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 700 }">Filler ratio</div>
          <div :style="{ fontSize: '12px', fontWeight: 700, color: 'var(--fg1)' }">{{ (iil.filler_ratio * 100).toFixed(1) }}%</div>
        </div>
      </div>
    </template>

    <!-- Phase A5 — Rescue section. Admin-only; hits /v1/diag/* via diagApi. -->
    <template v-if="isAdmin">
      <div class="rightrail__sectionhead" :style="{ marginTop: '16px' }">Rescue · operator actions</div>
      <div class="admin-rescue" data-test-id="admin-rescue">
        <div :style="{ fontSize: '11px', color: 'var(--fg2)', marginBottom: '8px', lineHeight: 1.4 }">
          Operator-only. Each action calls <code>/v1/diag/*</code>; backend gates by CurrentUser. Confirmation required before dispatch.
        </div>
        <button
          v-for="a in rescueActions"
          :key="a.id"
          :class="['admin-rescue__btn', a.destructive ? 'admin-rescue__btn--danger' : '']"
          :disabled="rescuing !== null"
          :data-test-id="`admin-rescue-${a.id}`"
          @click="runRescue(a)"
        >
          <span class="admin-rescue__btn-label">
            {{ a.label }}
            <span v-if="rescuing === a.id" class="admin-rescue__btn-spinner">…</span>
          </span>
          <span class="admin-rescue__btn-desc">{{ a.desc }}</span>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.admin-rescue { display: flex; flex-direction: column; gap: 6px; }
.admin-rescue__btn {
  display: flex; flex-direction: column; align-items: flex-start; gap: 2px;
  padding: 8px 10px; text-align: left; cursor: pointer;
  background: var(--surface-card, #fff);
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 6px;
  font: inherit; color: inherit;
  transition: border-color 0.12s, background 0.12s;
}
.admin-rescue__btn:hover:not(:disabled) {
  border-color: var(--color-blue, #0861CE);
  background: var(--surface-hover, #f7f7f7);
}
.admin-rescue__btn:disabled { opacity: 0.55; cursor: not-allowed; }
.admin-rescue__btn--danger { border-left: 3px solid var(--color-red, #C54644); }
.admin-rescue__btn-label { font-size: 12px; font-weight: 700; color: var(--fg1, #002855); }
.admin-rescue__btn-desc  { font-size: 10.5px; color: var(--fg2, #6b7280); line-height: 1.35; }
.admin-rescue__btn-spinner { margin-left: 4px; color: var(--color-blue, #0861CE); font-weight: 400; }
</style>
