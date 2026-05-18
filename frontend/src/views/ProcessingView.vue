<script setup lang="ts">
/**
 * Processing — /p/:id  (8-hop pipeline trace)
 *
 * Wired to GET /v1/sessions/{id}. DOM matches React processing.jsx.
 * Hop statuses are derived from the session.status field — until the
 * Celery ingest task is implemented they stay at "queued" past hop 2.
 */
import { computed, onMounted, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { sessions as sessionsApi, type SessionSummary } from '@/services/api';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';

const props = defineProps<{ id: string }>();
const session = ref<SessionSummary | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  try { session.value = await sessionsApi.get(props.id); }
  catch (e) { error.value = e instanceof Error ? e.message : 'Failed to load'; }
  finally { loading.value = false; }
}
onMounted(load);

type HopStatus = 'done' | 'running' | 'pending' | 'failed';
interface Hop { n: number; name: string; desc: string; status: HopStatus; t: string }

const hops = computed<Hop[]>(() => {
  const s = session.value?.status ?? 'ingesting';
  const isReady = s === 'ready' || s === 'complete';
  const isFailed = s === 'failed';
  // Today: upload-complete writes Source rows but no Celery task runs.
  // Hops 1-3 (upload + persist) are done; 4+ stay queued until ingest exists.
  const after3: HopStatus = isFailed ? 'failed' : isReady ? 'done' : 'pending';
  return [
    { n: 1, name: 'Asset Upload',               desc: 'Audio + slide deck received from presenter',     status: 'done',    t: '0:00:01' },
    { n: 2, name: 'Media Probe',                desc: 'FFmpeg probe · duration / channels / sample rate', status: 'done',    t: '0:00:01' },
    { n: 3, name: 'GCS Persist',                desc: 'Bytes streamed direct-to-bucket',                  status: 'done',    t: '0:00:01' },
    { n: 4, name: 'STT (Google)',               desc: 'Streaming recognition · chunked',                  status: after3,    t: after3 === 'done' ? '—' : 'queued' },
    { n: 5, name: 'Gemini Reconstruction',      desc: 'Verbatim-minus-fillers · 3-tier normalization',    status: after3,    t: 'queued' },
    { n: 6, name: 'Slide Alignment',            desc: 'Segment ↔ slide_id assignment',                    status: after3,    t: 'queued' },
    { n: 7, name: 'Discrepancy Classification', desc: 'STT vs base_text · server-side LCS',               status: after3,    t: 'queued' },
    { n: 8, name: 'Ready for Edit',             desc: 'Session graduates to Prep stage',                  status: isReady ? 'done' : 'pending', t: isReady ? '—' : 'queued' },
  ];
});

function openGcs(): void { toast.push(`Open in GCS console: ${props.id} (mock)`); }
function downloadStt(): void { toast.push(`Download raw STT for ${props.id} (mock)`); }
async function cancelIngestion(): Promise<void> {
  const ok = await confirm.open({
    title: `Cancel ingestion for ${props.id}?`,
    body: 'In-flight Gemini work will be abandoned. The session will be marked failed and can be re-ingested.',
    danger: true,
    confirmLabel: 'Cancel ingestion',
  });
  if (ok) toast.push('Ingestion cancelled', { tone: 'warn' });
}
</script>

<template>
  <main class="page" data-screen-label="Processing">
    <div class="page-eyebrow">
      <RouterLink to="/sessions">Sessions</RouterLink><span class="sep">/</span>
      <span>Processing · {{ props.id }}</span>
    </div>
    <div v-if="loading" :style="{ padding: '60px', textAlign: 'center', color: 'var(--fg2)' }">Loading session…</div>
    <div v-else-if="error" :style="{ padding: '60px', textAlign: 'center', color: 'var(--color-red)' }">{{ error }}</div>
    <template v-else>
      <h1 class="page-title">{{ session?.title || 'Session not found' }}</h1>
      <p class="page-desc">
        <template v-if="session?.status === 'ready' || session?.status === 'complete'">
          Session is ready. <RouterLink :to="`/e/${props.id}`">Open the editor →</RouterLink>
        </template>
        <template v-else-if="session?.status === 'failed'">
          Ingestion failed. Check Celery worker logs.
        </template>
        <template v-else>
          Session is ingesting. The 8-hop pipeline trace below mirrors the GCS QA surface (G1–G14). Editor opens automatically when hop 8 completes.
        </template>
      </p>
      <div :style="{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '18px' }">
        <div class="processing-trace">
          <div v-for="h in hops" :key="h.n" class="trace-hop">
            <div class="trace-hop__n">G{{ h.n }}</div>
            <div>
              <div class="trace-hop__name">{{ h.name }}</div>
              <div class="trace-hop__desc">{{ h.desc }}</div>
            </div>
            <div>
              <div v-if="h.status === 'done'"    class="progress progress--green"><span :style="{ width: '100%' }" /></div>
              <div v-else-if="h.status === 'running'" class="progress progress--blue"><span :style="{ width: '55%', animation: 'indet 2s linear infinite' }" /></div>
              <div v-else-if="h.status === 'failed'"  class="progress"><span :style="{ width: '100%', background: 'var(--color-red)' }" /></div>
              <div v-else class="progress"><span :style="{ width: '0%' }" /></div>
            </div>
            <div class="trace-hop__t">{{ h.t }}</div>
            <div>
              <span v-if="h.status === 'done'"    class="chip chip--green"><Icon name="check" :size="10" /> done</span>
              <span v-else-if="h.status === 'running'" class="chip chip--blue"><Icon name="spinner" :size="10" /> running</span>
              <span v-else-if="h.status === 'failed'"  class="chip" :style="{ background: 'rgba(197,70,68,0.12)', color: 'var(--color-red)' }">failed</span>
              <span v-else class="chip chip--ghost"><span class="chip__dot" /> queued</span>
            </div>
          </div>
        </div>
        <div>
          <div class="card">
            <div class="card__header">
              <h3>Pipeline Health</h3>
              <span class="dot" :style="{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--color-green)', boxShadow: '0 0 6px rgba(0,125,97,0.6)' }" />
            </div>
            <div class="card__body" :style="{ fontSize: '12.5px', color: 'var(--fg2)', lineHeight: 1.6 }">
              <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }">
                <span>Status</span><strong :style="{ color: 'var(--fg1)', fontFamily: 'var(--font-mono)' }">{{ session?.status || '—' }}</strong>
              </div>
              <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }">
                <span>Segments produced</span><strong :style="{ color: 'var(--fg1)', fontFamily: 'var(--font-mono)' }">{{ session?.segment_count ?? 0 }}</strong>
              </div>
              <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }">
                <span>Words</span><strong :style="{ color: 'var(--fg1)', fontFamily: 'var(--font-mono)' }">{{ (session?.word_count ?? 0).toLocaleString() }}</strong>
              </div>
              <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }">
                <span>Dead-letter</span><strong :style="{ color: 'var(--color-green)', fontFamily: 'var(--font-mono)' }">0</strong>
              </div>
              <div :style="{ display: 'flex', justifyContent: 'space-between' }">
                <span>Code</span><strong :style="{ color: 'var(--fg1)', fontFamily: 'var(--font-mono)' }">{{ session?.code || '—' }}</strong>
              </div>
            </div>
          </div>
          <div class="card" :style="{ marginTop: '14px' }">
            <div class="card__header"><h3>Operator Actions</h3></div>
            <div class="card__body" :style="{ display: 'grid', gap: '6px' }">
              <button class="btn btn--secondary btn--sm" data-test-id="proc-open-gcs" @click="openGcs">
                <Icon name="external" /> Open in GCS console
              </button>
              <button class="btn btn--secondary btn--sm" data-test-id="proc-download-stt" @click="downloadStt">
                <Icon name="download" /> Download raw STT
              </button>
              <button class="btn btn--ghost btn--sm" data-test-id="proc-cancel" :style="{ color: 'var(--color-red)' }" @click="cancelIngestion">
                <Icon name="x" /> Cancel ingestion
              </button>
              <RouterLink
                v-if="session?.status === 'ready' || session?.status === 'complete'"
                :to="`/e/${props.id}`"
                class="btn btn--primary btn--sm"
              ><Icon name="edit" /> Open Editor →</RouterLink>
              <RouterLink
                :to="`/s/${props.id}`"
                class="btn btn--ghost btn--sm"
              ><Icon name="external" /> Session detail</RouterLink>
            </div>
          </div>
        </div>
      </div>
    </template>
  </main>
</template>

<style>
@keyframes indet { 0% { transform: translateX(-30%) } 100% { transform: translateX(80%) } }
</style>
