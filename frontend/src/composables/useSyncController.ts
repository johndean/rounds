/**
 * useSyncController — WebSocket sync for /v1/ws/sessions/{id}.
 *
 * Port of MIC `frontend/src/composables/useSyncController.js` (MIC §29 +
 * §12b — processing_update field is `stage`, events emit cross-process via
 * Redis bridge). Strips MIC's store-binding (sessionStore.loadTimeline,
 * uiStore.sttReady, aiTranscriptCache, etc.) — Rounds wires those at the
 * call site if/when needed. The minimum surface ProcessingView needs:
 *
 *   processingStage, processingProgress, processingSubstage
 *   metrics (segments / markers / slides_aligned / slides_total)
 *   failureCategory, failureUserMessage
 *   connect(), disconnect()
 */
import { onUnmounted, ref } from 'vue';

export interface ProcessingMetrics {
  segments?: number;
  markers?: number;
  slides_total?: number;
  slides_aligned?: number;
  speakers?: number;
  duration_sec?: number;
}

export function useSyncController(sessionId: string) {
  const wsStatus            = ref<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  const processingStage     = ref<string | null>(null);
  const processingProgress  = ref<number>(0);
  const processingSubstage  = ref<string>('');
  const metrics             = ref<ProcessingMetrics>({});
  const failureCategory     = ref<string | null>(null);
  const failureUserMessage  = ref<string | null>(null);
  const sttReady            = ref<boolean>(false);
  const sttFailed           = ref<boolean>(false);

  let ws: WebSocket | null = null;
  let disposed = false;

  function connect(): void {
    if (!sessionId || ws) return;
    wsStatus.value = 'connecting';
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${window.location.host}/v1/ws/sessions/${encodeURIComponent(sessionId)}`;
    try {
      ws = new WebSocket(url);
    } catch {
      wsStatus.value = 'error';
      return;
    }

    ws.onopen = () => { wsStatus.value = 'connected'; };
    ws.onerror = () => { wsStatus.value = 'error'; };
    ws.onclose = () => { if (!disposed) wsStatus.value = 'disconnected'; };
    ws.onmessage = (event) => {
      let msg: Record<string, unknown>;
      try { msg = JSON.parse(event.data); } catch { return; }
      dispatch(msg);
    };
  }

  function dispatch(msg: Record<string, unknown>): void {
    switch (msg.type) {
      case 'processing_update':
        if (typeof msg.stage === 'string') processingStage.value = msg.stage;
        if (typeof msg.progress === 'number') processingProgress.value = msg.progress;
        if (typeof msg.substage === 'string') processingSubstage.value = msg.substage;
        break;

      case 'metrics_update': {
        const next: ProcessingMetrics = { ...metrics.value };
        for (const k of ['segments', 'markers', 'slides_total', 'slides_aligned', 'speakers', 'duration_sec'] as const) {
          if (typeof msg[k] === 'number') (next as Record<string, number>)[k] = msg[k] as number;
        }
        metrics.value = next;
        break;
      }

      case 'session_failed':
        failureCategory.value    = typeof msg.category === 'string' ? msg.category : 'unknown';
        failureUserMessage.value = typeof msg.user_message === 'string'
          ? msg.user_message
          : (typeof msg.reason === 'string' ? msg.reason : 'Something went wrong. Try again.');
        processingStage.value = 'failed';
        break;

      case 'stt_ready':
        sttReady.value = true;
        sttFailed.value = false;
        break;

      case 'stt_failed':
      case 'stt_background_failed':
        sttFailed.value = true;
        break;

      // discrepancies_ready, timeline_ready, template_autodetect, alignment_update,
      // correction_applied — handled by their respective views/stores at call site
      // when needed. ProcessingView doesn't need them.
    }
  }

  function disconnect(): void {
    disposed = true;
    try { ws?.close(); } catch { /* ignore */ }
    ws = null;
    wsStatus.value = 'disconnected';
  }

  onUnmounted(disconnect);

  return {
    wsStatus,
    processingStage,
    processingProgress,
    processingSubstage,
    metrics,
    failureCategory,
    failureUserMessage,
    sttReady,
    sttFailed,
    connect,
    disconnect,
  };
}
