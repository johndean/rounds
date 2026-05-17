<script setup lang="ts">
/**
 * Processing — /p/:id  (8-hop pipeline trace)
 * Faithful 1:1 port of docs/port-source/processing.jsx::ProcessingRoute.
 */
import { computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { SESSIONS } from '@/fixtures/sessions';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';

const props = defineProps<{ id: string }>();

const session = computed(() =>
  SESSIONS.find(s => s.id === props.id)
    ?? SESSIONS.find(s => s.status === 'processing')
    ?? SESSIONS[0]!,
);

const hops = [
  { n: 1, name: 'Asset Upload',               desc: 'Audio + slide deck received from presenter',     status: 'done',     t: '0:00:32' },
  { n: 2, name: 'Media Probe',                desc: 'FFmpeg probe · duration / channels / sample rate', status: 'done',     t: '0:00:11' },
  { n: 3, name: 'GCS Persist',                desc: 'Upload to gs://vin-transcripts/se_007/...',       status: 'done',     t: '0:01:48' },
  { n: 4, name: 'STT (Google)',               desc: 'Streaming recognition · 47 min audio',            status: 'done',     t: '0:08:14' },
  { n: 5, name: 'Gemini Reconstruction',      desc: 'Verbatim-minus-fillers · 3-tier normalization',   status: 'running',  t: '0:03:42 …' },
  { n: 6, name: 'Slide Alignment',            desc: 'Segment ↔ slide_id assignment',                   status: 'pending',  t: '—' },
  { n: 7, name: 'Discrepancy Classification', desc: 'STT vs base_text · server-side LCS',              status: 'pending',  t: '—' },
  { n: 8, name: 'Ready for Edit',             desc: 'Session graduates to Prep stage',                 status: 'pending',  t: '—' },
];

function openGcs(): void { toast.push(`Open in GCS console: ${session.value.id} (mock)`); }
function downloadStt(): void { toast.push(`Download raw STT for ${session.value.id} (mock)`); }
async function cancelIngestion(): Promise<void> {
  const ok = await confirm.open({
    title: `Cancel ingestion for ${session.value.id}?`,
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
      <span>Processing · {{ session.id }}</span>
    </div>
    <h1 class="page-title">{{ session.title }}</h1>
    <p class="page-desc">
      Session is ingesting. The 8-hop pipeline trace below mirrors the GCS QA surface (G1–G14). Editor opens automatically when hop 8 completes.
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
            <div v-if="h.status === 'running'" class="progress progress--blue"><span :style="{ width: '55%', animation: 'indet 2s linear infinite' }" /></div>
            <div v-if="h.status === 'pending'" class="progress"><span :style="{ width: '0%' }" /></div>
          </div>
          <div class="trace-hop__t">{{ h.t }}</div>
          <div>
            <span v-if="h.status === 'done'"    class="chip chip--green"><Icon name="check" :size="10" /> done</span>
            <span v-if="h.status === 'running'" class="chip chip--blue"><Icon name="spinner" :size="10" /> running</span>
            <span v-if="h.status === 'pending'" class="chip chip--ghost"><span class="chip__dot" /> queued</span>
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
              <span>Queue depth</span><strong :style="{ color: 'var(--fg1)', fontFamily: 'var(--font-mono)' }">2</strong>
            </div>
            <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }">
              <span>Avg STT time</span><strong :style="{ color: 'var(--fg1)', fontFamily: 'var(--font-mono)' }">0.18× realtime</strong>
            </div>
            <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }">
              <span>Avg Gemini time</span><strong :style="{ color: 'var(--fg1)', fontFamily: 'var(--font-mono)' }">0.07× realtime</strong>
            </div>
            <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }">
              <span>Dead-letter</span><strong :style="{ color: 'var(--color-green)', fontFamily: 'var(--font-mono)' }">0</strong>
            </div>
            <div :style="{ display: 'flex', justifyContent: 'space-between' }">
              <span>Last failure</span><strong :style="{ color: 'var(--fg1)', fontFamily: 'var(--font-mono)' }">—</strong>
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
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<style>
@keyframes indet { 0% { transform: translateX(-30%) } 100% { transform: translateX(80%) } }
</style>
