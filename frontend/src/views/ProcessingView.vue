<script setup lang="ts">
/**
 * Processing — /p/:id
 *
 * Verbatim port of MIC `frontend/src/views/ProcessingView.vue` — 4-stage
 * "Building your output" card driven by /v1/ws/sessions/{id} processing_update
 * events. Detects AI MODE (direct/enhanced) from /pipeline-config and shows
 * the matching step set:
 *
 *   AI direct:    Preparing files → AI analysis → Mapping slides → Finalizing
 *   AI enhanced:  Uploading → Transcribing → AI enhancement → IIL → Matching slides
 *   Standard:     Uploading → Transcribing → IIL → Boundaries → Matching slides
 *
 * Replaces the pre-existing "G1-G8 pipeline trace" UI that was hardcoded to
 * the standard pipeline regardless of which one was actually running — that
 * was misleading users on AI MODE direct sessions (the visible "STT (Google)
 * running" was a lie; Cloud STT was never invoked).
 *
 * Backend WS event shape (locked):
 *   { type: 'processing_update', stage: 'ai_processing', progress: 30, substage: '...' }
 *   { type: 'metrics_update', segments?: N, markers?: N, slides_total?: N, slides_aligned?: N }
 *   { type: 'session_failed', category: 'gemini_overloaded'|..., user_message: '...' }
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { sessions as sessionsApi, type SessionFailureReason, type SessionSummary, type PipelineConfig } from '@/services/api';
import { useSyncController } from '@/composables/useSyncController';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';
import { ApiError } from '@/services/http';

const props = defineProps<{ id: string }>();
const router = useRouter();

// ─── Step definitions (verbatim from MIC ProcessingView.vue:109-132) ─────
interface Step { label: string; hint: string; iil: boolean }

const STANDARD_STEPS: Step[] = [
  { label: 'Uploading video',      hint: 'Transferring securely',          iil: false },
  { label: 'Transcribing speech',  hint: 'Verbatim word-level output',     iil: false },
  { label: 'Applying IIL',         hint: 'Removing Tier 1/2/3 fillers',    iil: true  },
  { label: 'Detecting boundaries', hint: 'Multi-signal Fusion Engine',     iil: false },
  { label: 'Matching slides',      hint: '4-signal alignment',             iil: false },
];

const AI_DIRECT_STEPS: Step[] = [
  { label: 'Preparing files',      hint: 'Processing audio & slides',      iil: false },
  { label: 'AI analysis',          hint: 'Gemini multimodal transcription', iil: false },
  { label: 'Mapping slides',       hint: 'Matching markers to PDF pages',  iil: false },
  { label: 'Finalizing',           hint: 'Saving to database',             iil: false },
];

const AI_ENHANCED_STEPS: Step[] = [
  { label: 'Uploading files',      hint: 'Transferring securely',          iil: false },
  { label: 'Transcribing speech',  hint: 'Verbatim word-level output',     iil: false },
  { label: 'AI enhancement',       hint: 'Gemini refining transcript',     iil: false },
  { label: 'Applying IIL',         hint: 'Removing Tier 1/2/3 fillers',    iil: true  },
  { label: 'Matching slides',      hint: 'Fusion + alignment',             iil: false },
];

const STANDARD_STAGE_MAP: Record<string, number> = {
  uploading: 0, transcribing: 1, normalizing: 2, fusing: 3, aligning: 4, ready: 5,
};
const AI_DIRECT_STAGE_MAP: Record<string, number> = {
  uploading: 0, ai_processing: 1, ready: 4,
};
const AI_ENHANCED_STAGE_MAP: Record<string, number> = {
  uploading: 0, transcribing: 1, ai_processing: 2, normalizing: 3, fusing: 4, aligning: 4, ready: 5,
};

// ─── State ───────────────────────────────────────────────────────────────
const session       = ref<SessionSummary | null>(null);
const fileName      = ref<string>('');
const templateId    = ref<string>('');
const aiPipeline    = ref<'direct' | 'enhanced' | ''>('');
const isAiMode      = ref<boolean>(false);
const startTime     = ref<number>(Date.now());
const now           = ref<number>(Date.now());
const retrying      = ref<boolean>(false);
const retryError    = ref<string>('');
const deleting      = ref<boolean>(false);
const elapsedDisplay = ref<string>('0:00');

// ─── WS sync ─────────────────────────────────────────────────────────────
const {
  processingStage, processingProgress, processingSubstage,
  metrics, failureCategory, failureUserMessage,
  connect, disconnect,
} = useSyncController(props.id);

// ─── Derived ─────────────────────────────────────────────────────────────
const STEPS = computed<Step[]>(() => {
  if (isAiMode.value && aiPipeline.value === 'direct')   return AI_DIRECT_STEPS;
  if (isAiMode.value && aiPipeline.value === 'enhanced') return AI_ENHANCED_STEPS;
  return STANDARD_STEPS;
});

const STAGE_TO_STEP = computed<Record<string, number>>(() => {
  if (isAiMode.value && aiPipeline.value === 'direct')   return AI_DIRECT_STAGE_MAP;
  if (isAiMode.value && aiPipeline.value === 'enhanced') return AI_ENHANCED_STAGE_MAP;
  return STANDARD_STAGE_MAP;
});

function stepFromProgress(p: number): number {
  if (p <= 15) return 0;
  if (p <= 70) return 1;
  if (p <= 85) return 2;
  return 3;
}

const currentStep = computed<number>(() => {
  // AI Direct: use backend progress percentage
  if (isAiMode.value && aiPipeline.value === 'direct' && processingProgress.value > 0) {
    return stepFromProgress(processingProgress.value);
  }
  const map = STAGE_TO_STEP.value;
  if (processingStage.value && map[processingStage.value] !== undefined) {
    return map[processingStage.value];
  }
  const s = session.value?.status;
  if (s && map[s] !== undefined) return map[s];
  return 0;
});

const progressPct = computed<number>(() => {
  if (isAiMode.value && aiPipeline.value === 'direct' && processingProgress.value > 0) {
    return processingProgress.value;
  }
  const step = currentStep.value;
  if (step >= STEPS.value.length) return 100;
  return Math.round((step / STEPS.value.length) * 100);
});

const estRemaining = computed<string>(() => {
  const elapsed = (now.value - startTime.value) / 1000;
  const pct = progressPct.value;
  if (pct >= 100) return 'Finishing up…';
  if (pct < 10 || elapsed < 3) return 'Estimating…';
  if (pct > 85) return '< 1 min';
  const total = elapsed / (pct / 100);
  const remaining = Math.max(0, Math.round(total - elapsed));
  if (remaining > 60) {
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    return `~${m}:${String(s).padStart(2, '0')} remaining`;
  }
  return remaining > 0 ? `~${remaining}s remaining` : 'Finishing up…';
});

const sessionStatus = computed<string>(() => {
  if (failureCategory.value || processingStage.value === 'failed') return 'failed';
  return session.value?.status || 'uploading';
});

const FAIL_TITLES: Record<string, string> = {
  gemini_overloaded:       'AI service is busy',
  gemini_quota:            'AI quota reached',
  gemini_config:           'AI service unavailable',
  gemini_error:            'AI service error',
  gemini_context_overflow: 'Input too large for selected model',
  storage_error:           'Storage error',
  stt_error:               'Speech-to-text failed',
  unknown:                 'Processing failed',
};
const failTitle = computed<string>(() => FAIL_TITLES[failureCategory.value || 'unknown'] || 'Processing failed');

// ─── Polling fallback (WS may drop) ──────────────────────────────────────
let pollHandle: ReturnType<typeof setInterval> | null = null;
let elapsedHandle: ReturnType<typeof setInterval> | null = null;

async function fetchSession(): Promise<void> {
  try {
    session.value = await sessionsApi.get(props.id);
    fileName.value = session.value?.title || fileName.value;
  } catch {
    /* keep polling */
  }
}

function updateElapsed(): void {
  now.value = Date.now();
  const secs = Math.floor((now.value - startTime.value) / 1000);
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  elapsedDisplay.value = `${m}:${String(s).padStart(2, '0')}`;
}

async function loadPipelineConfig(): Promise<void> {
  try {
    const cfg = (await sessionsApi.pipelineConfig(props.id)) as PipelineConfig & {
      auto_detected_template_id?: string | null;
    };
    templateId.value = cfg.template_id || '';
    aiPipeline.value = (cfg.ai_pipeline === 'enhanced' ? 'enhanced' : 'direct');
    isAiMode.value = Boolean(cfg.ai_mode);
  } catch {
    /* fall back to standard pipeline display */
  }
}

// ─── Actions ─────────────────────────────────────────────────────────────
async function onRetry(): Promise<void> {
  if (retrying.value) return;
  retrying.value = true;
  retryError.value = '';
  try {
    await sessionsApi.retry(props.id);
    failureCategory.value = null;
    failureUserMessage.value = null;
    processingStage.value = null;
    processingProgress.value = 0;
    processingSubstage.value = '';
    startTime.value = Date.now();
    connect();
    void fetchSession();
    toast.push('Reingest queued', { tone: 'success' });
  } catch (e) {
    retryError.value = e instanceof ApiError ? `${e.status} — ${e.message}` : (e instanceof Error ? e.message : 'Retry failed');
  } finally {
    retrying.value = false;
  }
}

async function onDelete(): Promise<void> {
  if (deleting.value) return;
  const ok = await confirm.open({
    title: `Delete ${session.value?.code || props.id}?`,
    body: 'This will mark the session as deleted. Recoverable from Settings → Deleted Sessions for 30 days.',
    danger: true,
    confirmLabel: 'Delete',
  });
  if (!ok) return;
  deleting.value = true;
  try {
    await sessionsApi.remove(props.id);
    toast.push('Session deleted', { tone: 'success' });
    router.push('/upload');
  } catch (e) {
    retryError.value = e instanceof ApiError ? `${e.status} — ${e.message}` : (e instanceof Error ? e.message : 'Delete failed');
    deleting.value = false;
  }
}

// On reaching ready, auto-redirect to editor (verbatim from MIC pattern).
watch(processingStage, (stage) => {
  if (stage === 'ready') {
    setTimeout(() => router.push(`/e/${props.id}`), 600);
  }
});
watch(() => session.value?.status, (s, prev) => {
  if ((s === 'ready' || s === 'complete') && prev && prev !== s) {
    setTimeout(() => router.push(`/e/${props.id}`), 600);
  }
});

// Fetch failure reason on demand (when WS missed the session_failed event)
async function hydrateFailureReason(): Promise<void> {
  try {
    const r: SessionFailureReason = await sessionsApi.failureReason(props.id);
    if (r.reason && !failureUserMessage.value) failureUserMessage.value = r.reason;
    if (r.category && !failureCategory.value) failureCategory.value = r.category;
  } catch { /* non-fatal */ }
}

watch(() => session.value?.status, (s) => {
  if (s === 'failed' && !failureUserMessage.value) void hydrateFailureReason();
});

// ─── Lifecycle ───────────────────────────────────────────────────────────
onMounted(async () => {
  startTime.value = Date.now();
  await fetchSession();
  await loadPipelineConfig();
  connect();
  pollHandle = setInterval(fetchSession, 3000);
  elapsedHandle = setInterval(updateElapsed, 1000);
});

onUnmounted(() => {
  if (pollHandle) clearInterval(pollHandle);
  if (elapsedHandle) clearInterval(elapsedHandle);
  disconnect();
});
</script>

<template>
  <main class="page proc-page" data-screen-label="Processing">
    <div class="proc-body">
      <!-- Failure card -->
      <div v-if="sessionStatus === 'failed'" class="proc-card">
        <div class="proc-h proc-h--err">{{ failTitle }}</div>
        <div class="proc-file">{{ fileName || props.id }}</div>
        <p class="proc-err-msg">{{ failureUserMessage || 'Something went wrong. Try again.' }}</p>
        <p v-if="failureCategory === 'gemini_overloaded'" class="proc-err-tip">
          Tip: wait 1–2 minutes before retrying — Google's load usually clears.
        </p>
        <p v-else-if="failureCategory === 'gemini_context_overflow'" class="proc-err-tip">
          Tip: the input exceeds this model's context window. Settings → AI models lets you pick a larger one (Gemini 2.5 Pro = 2M tokens).
        </p>
        <div class="proc-err-actions">
          <button class="btn btn--primary" :disabled="retrying" @click="onRetry">
            {{ retrying ? 'Retrying…' : 'Retry' }}
          </button>
          <button class="btn btn--secondary" :disabled="deleting" @click="onDelete">
            {{ deleting ? 'Deleting…' : 'Delete & start over' }}
          </button>
        </div>
        <p v-if="retryError" class="proc-retry-error">{{ retryError }}</p>
      </div>

      <!-- Processing card -->
      <div v-else class="proc-card">
        <div class="proc-h">Building your output</div>
        <div class="proc-file">{{ fileName || props.id }}</div>

        <!-- Template badge -->
        <div v-if="templateId" class="tmpl-proc-badge">
          <span class="tmpl-proc-name">{{ templateId }}</span>
        </div>

        <!-- Steps -->
        <div class="steps">
          <div
            v-for="(step, i) in STEPS"
            :key="i"
            class="step"
            :class="i === currentStep ? (step.iil ? 's-iil' : 's-active') : i < currentStep ? 's-done' : 's-wait'"
          >
            <div
              class="step-ico"
              :class="i < currentStep ? 'done' : i === currentStep ? (step.iil ? 'iil-a' : 'active') : 'wait'"
            >
              <span v-if="i < currentStep" class="step-check">✓</span>
              <div v-else-if="i === currentStep" class="spinner" :class="{ 'spinner-iil': step.iil }"></div>
              <span v-else class="step-num">{{ i + 1 }}</span>
            </div>
            <div class="step-body">
              <div class="step-name" :class="{ 'step-name--iil': i === currentStep && step.iil }">{{ step.label }}</div>
              <div class="step-hint">{{ i === currentStep && processingSubstage ? processingSubstage : step.hint }}</div>
            </div>
            <span v-if="step.iil" class="step-iil-tag">IIL</span>
          </div>
        </div>

        <!-- Progress -->
        <div class="prog-track">
          <div class="prog-fill" :style="{ width: progressPct + '%' }"></div>
        </div>
        <div class="prog-meta">
          <span>{{ progressPct }}% complete</span>
          <span>{{ elapsedDisplay }}</span>
          <span>{{ estRemaining }}</span>
        </div>

        <!-- Metrics -->
        <div class="metrics-panel">
          <div class="metric">
            <div class="metric-lbl">Segments</div>
            <div class="metric-val">{{ metrics.segments ?? '—' }}</div>
          </div>
          <div class="metric">
            <div class="metric-lbl">Markers</div>
            <div class="metric-val">{{ metrics.markers ?? '—' }}</div>
          </div>
          <div class="metric">
            <div class="metric-lbl">Slides</div>
            <div class="metric-val">
              {{ metrics.slides_aligned ?? '—' }}<span v-if="metrics.slides_total !== undefined" class="metric-of">/{{ metrics.slides_total }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
/* MIC ProcessingView.vue port — uses Rounds CSS tokens. */

.proc-page  { width: 100%; min-height: 100vh; background: var(--surface-bg); display: flex; flex-direction: column; }
.proc-body  { flex: 1; display: flex; align-items: center; justify-content: center; padding: 32px 24px 64px; }

.proc-card  { width: 100%; max-width: 520px; background: var(--surface); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 36px; box-shadow: 0 1px 3px rgba(8,14,24,0.04), 0 4px 12px rgba(8,14,24,0.06); }
.proc-h     { font-size: 22px; font-weight: 700; letter-spacing: -0.03em; margin-bottom: 6px; color: var(--fg1); }
.proc-h--err { color: var(--color-red); }
.proc-file  { font-size: 13px; color: var(--fg2); font-family: var(--font-mono); margin-bottom: 32px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Error state */
.proc-err-msg     { font-size: 13px; color: var(--fg1); margin: 0 0 8px; line-height: 1.55; }
.proc-err-tip     { font-size: 11px; color: var(--fg2); margin: 0 0 20px; font-family: var(--font-mono); }
.proc-err-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.proc-retry-error { margin-top: 10px; color: var(--color-red); font-size: 11px; font-family: var(--font-mono); }

/* Template badge */
.tmpl-proc-badge { display: inline-flex; align-items: center; gap: 8px; padding: 9px 14px; background: rgba(37,99,235,0.06); border: 1px solid rgba(37,99,235,0.35); border-radius: 8px; margin-bottom: 20px; margin-top: -12px; }
.tmpl-proc-name  { font-size: 12px; font-weight: 600; color: var(--fg-link, #2563eb); font-family: var(--font-mono); }

/* Steps */
.steps      { display: flex; flex-direction: column; gap: 3px; margin-bottom: 32px; }
.step       { display: flex; align-items: center; gap: 12px; padding: 11px 12px; border-radius: 8px; transition: background 0.15s; }
.step.s-active { background: rgba(37,99,235,0.06); }
.step.s-iil    { background: rgba(217,119,6,0.07); }
.step-body  { flex: 1; min-width: 0; }
.step-ico   { width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; flex-shrink: 0; }
.step-ico.done    { background: rgba(13,122,94,0.10); color: #0d7a5e; border: 1px solid #0d7a5e; }
.step-ico.active  { background: rgba(37,99,235,0.08); border: 2px solid #2563eb; }
.step-ico.iil-a   { background: rgba(217,119,6,0.08); border: 2px solid #d97706; }
.step-ico.wait    { background: var(--surface-bg); color: var(--fg2); border: 1px solid var(--border-subtle); }
.step-check { color: #0d7a5e; font-size: 13px; font-weight: 700; }
.step-num   { font-size: 10px; color: var(--fg2); font-family: var(--font-mono); }
.spinner    { width: 13px; height: 13px; border: 2px solid rgba(37,99,235,0.15); border-top-color: #2563eb; border-radius: 50%; animation: proc-spin 0.7s linear infinite; }
.spinner-iil { border-color: rgba(217,119,6,0.15); border-top-color: #d97706; }
@keyframes proc-spin { to { transform: rotate(360deg); } }
.step-name  { font-size: 14px; font-weight: 500; color: var(--fg1); }
.step-name--iil { color: #b45309; }
.step.s-wait .step-name { color: var(--fg2); }
.step-hint  { font-size: 11px; color: var(--fg2); margin-top: 1px; }
.step-iil-tag { font-size: 9px; font-family: var(--font-mono); color: #b45309; opacity: 0.7; }

/* Progress */
.prog-track { height: 5px; background: var(--border-subtle); border-radius: 3px; overflow: hidden; margin-bottom: 10px; }
.prog-fill  { height: 100%; background: #2563eb; border-radius: 3px; transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1); }
.prog-meta  { display: flex; justify-content: space-between; font-size: 11px; color: var(--fg2); font-family: var(--font-mono); }

/* Metrics panel */
.metrics-panel { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 18px; padding: 12px; background: var(--surface-bg); border: 1px solid var(--border-subtle); border-radius: 8px; }
.metric        { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; }
.metric-lbl    { font-size: 9px; font-family: var(--font-mono); color: var(--fg2); text-transform: uppercase; letter-spacing: 0.09em; }
.metric-val    { font-size: 18px; font-weight: 700; color: var(--fg1); font-family: var(--font-mono); letter-spacing: -0.02em; }
.metric-of     { font-size: 13px; font-weight: 500; color: var(--fg2); margin-left: 2px; }
</style>
