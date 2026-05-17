<script setup lang="ts">
/**
 * Editor (D pattern, 3-column resizable, 4 tabs). IMPLEMENTATION.md §6.
 *
 * Phase 8 part 4: minimum-viable editor — segment list with inline edit
 * via PATCH /v1/segments/{id}. Full 3-column layout + AI/STT/Discrepancies/
 * Audit tabs + slide rail + right rail land per plan §7 Phase 4
 * (gated on prototype CSS bundle for pixel parity).
 */
import { ref, onMounted } from 'vue';
import { sessions as sessionsApi, segments as segmentsApi, type SessionSummary, type SegmentRow } from '@/services/api';
import { toast } from '@/composables/useToast';
import { ApiError } from '@/services/http';

const props = defineProps<{ id: string }>();

const session = ref<SessionSummary | null>(null);
const segs    = ref<SegmentRow[]>([]);
const error   = ref<string | null>(null);
const loading = ref(true);

const editing = ref<{ id: string; text: string } | null>(null);
const saving  = ref(false);

async function load(): Promise<void> {
  loading.value = true;
  try {
    const [s, rows] = await Promise.all([
      sessionsApi.get(props.id),
      segmentsApi.list(props.id),
    ]);
    session.value = s;
    segs.value = rows;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) error.value = 'Session not found';
    else error.value = e instanceof Error ? e.message : 'Failed to load';
  } finally {
    loading.value = false;
  }
}

function startEdit(s: SegmentRow): void {
  editing.value = { id: s.id, text: s.text };
}

async function saveEdit(): Promise<void> {
  if (!editing.value) return;
  saving.value = true;
  try {
    const updated = await segmentsApi.edit(props.id, editing.value.id, { text: editing.value.text });
    const idx = segs.value.findIndex(s => s.id === updated.id);
    if (idx >= 0) segs.value[idx] = updated;
    toast.push('Segment saved', { tone: 'success' });
    editing.value = null;
  } catch (e) {
    toast.push(`Save failed: ${e instanceof Error ? e.message : 'unknown'}`, { tone: 'error' });
  } finally {
    saving.value = false;
  }
}

function fmtMs(ms: number): string {
  const total = Math.floor(ms / 1000);
  return `${Math.floor(total / 60).toString().padStart(2, '0')}:${(total % 60).toString().padStart(2, '0')}`;
}

onMounted(load);
</script>

<template>
  <div class="editor">
    <header class="editor__header">
      <div>
        <RouterLink :to="`/s/${props.id}`" style="color: var(--fg2); font-size: var(--fs-xs); text-decoration: none;">
          ← Session
        </RouterLink>
        <h1 v-if="session" style="margin: var(--space-1) 0 0;">
          <span class="mono" style="color: var(--color-navy); font-size: var(--fs-sm);">{{ session.code }}</span> ·
          {{ session.title }}
        </h1>
      </div>
      <div style="display: flex; gap: var(--space-2);">
        <RouterLink :to="`/e/${props.id}/sop`" class="btn">Workflow</RouterLink>
        <RouterLink :to="`/e/${props.id}/audit`" class="btn">Audit</RouterLink>
      </div>
    </header>

    <p v-if="loading" style="color: var(--fg2);">Loading…</p>
    <p v-else-if="error" style="color: var(--color-red);">{{ error }}</p>

    <section v-if="!loading && !error" class="card">
      <h2 style="margin: 0 0 var(--space-3); font-size: var(--fs-md); font-weight: var(--fw-extrabold);">
        AI Transcript · {{ segs.length }} segment{{ segs.length === 1 ? '' : 's' }}
      </h2>
      <p style="margin: 0 0 var(--space-3); color: var(--fg2); font-size: var(--fs-xs);">
        Full 3-column layout + STT/Discrepancies/Audit tabs + Slide Rail land in Phase 4 per the plan.
        Inline edit (Click any segment) writes through to /v1/segments/{id} and is captured in the corrections ledger.
      </p>
      <p v-if="!segs.length" style="margin: 0; color: var(--fg2);">No segments yet — ingest hasn't run for this session.</p>

      <ul v-else class="segments">
        <li v-for="s in segs" :key="s.id" class="segment">
          <span class="segment__time mono">{{ fmtMs(s.start_ms) }}</span>
          <div class="segment__body">
            <template v-if="editing && editing.id === s.id">
              <textarea
                v-model="editing.text"
                class="segment__textarea"
                rows="3"
                :disabled="saving"
              />
              <div style="display: flex; gap: var(--space-2); margin-top: var(--space-2);">
                <button class="btn" :disabled="saving" @click="editing = null">Cancel</button>
                <button class="btn btn--primary" :disabled="saving" @click="saveEdit">
                  {{ saving ? 'Saving…' : 'Save' }}
                </button>
              </div>
            </template>
            <span v-else class="segment__text" @click="startEdit(s)">{{ s.text }}</span>
          </div>
          <span v-if="s.confidence !== null" class="segment__conf mono">{{ Math.round(s.confidence * 100) }}%</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.editor { padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-4); }
.editor__header { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4); }
.editor__header h1 { margin: 0; font-size: var(--fs-md); font-weight: var(--fw-extrabold); }
.segments { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.segment {
  display: grid; grid-template-columns: 64px 1fr 64px;
  gap: var(--space-3); padding: var(--space-3); align-items: start;
  border-bottom: 1px solid var(--border-subtle);
}
.segment__time, .segment__conf { color: var(--fg2); font-size: var(--fs-xs); }
.segment__conf { text-align: right; }
.segment__body { font-size: var(--fs-sm); }
.segment__text { cursor: text; display: block; padding: var(--space-1); border-radius: var(--radius-sm); }
.segment__text:hover { background: var(--surface-muted); }
.segment__textarea {
  width: 100%; font-family: var(--font-family); font-size: var(--fs-sm);
  padding: var(--space-2); border: 2px solid var(--color-blue); border-radius: var(--radius-sm);
  background: var(--surface-card); resize: vertical;
}
</style>
