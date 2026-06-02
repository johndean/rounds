/**
 * useSyncController — ProcessingView's WS-driven refs.
 *
 * Originally owned its own WebSocket; now subscribes via wsConnectionPool so
 * multiple views (ProcessingView + EditorView + ViewerView + ...) on the same
 * sessionId share one underlying socket. The dispatched message types and the
 * exposed ref surface are unchanged — ProcessingView and EditorView consume
 * this composable directly.
 *
 * Per-view subscribers (useWsSubscriber) handle the wider set of backend
 * events (correction_applied, timeline_ready, captioned_video_*, etc.) that
 * this composable intentionally does not — see the per-view wiring in
 * EditorView.vue / ViewerView.vue / etc.
 */
import { onUnmounted, ref } from 'vue';
import { subscribe, type WsMessage, type WsMessageHandler, type WsPoolSubscription, type WsStatus } from './wsConnectionPool';

export interface ProcessingMetrics {
  segments?: number;
  markers?: number;
  slides_total?: number;
  slides_aligned?: number;
  speakers?: number;
  duration_sec?: number;
}

export function useSyncController(sessionId: string) {
  const wsStatus            = ref<WsStatus>('disconnected');
  const processingStage     = ref<string | null>(null);
  const processingProgress  = ref<number>(0);
  const processingSubstage  = ref<string>('');
  const metrics             = ref<ProcessingMetrics>({});
  const failureCategory     = ref<string | null>(null);
  const failureUserMessage  = ref<string | null>(null);
  const sttReady            = ref<boolean>(false);
  const sttFailed           = ref<boolean>(false);

  let sub: WsPoolSubscription | null = null;

  const dispatch: WsMessageHandler = (msg) => {
    switch (msg.type) {
      case 'processing_update':
        if (typeof msg.stage === 'string') processingStage.value = msg.stage;
        if (typeof msg.progress === 'number') processingProgress.value = msg.progress;
        if (typeof msg.substage === 'string') processingSubstage.value = msg.substage;
        break;

      case 'metrics_update': {
        const next: ProcessingMetrics = { ...metrics.value };
        for (const k of ['segments', 'markers', 'slides_total', 'slides_aligned', 'speakers', 'duration_sec'] as const) {
          if (typeof (msg as WsMessage)[k] === 'number') (next as Record<string, number>)[k] = (msg as WsMessage)[k] as number;
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

      // Backend dispatches 'stt_background_failed' only — the legacy
      // 'stt_failed' case was a dead consumer (no producer) and has been
      // removed. If a producer ever resurfaces, add the case back here.
      case 'stt_background_failed':
        sttFailed.value = true;
        break;

      // Other backend types (correction_applied, discrepancy_resolved,
      // timeline_ready, captioned_video_*, classification_*, polls_autoplaced,
      // align_gate_failed, template_autodetect, slide_progress,
      // gemini_loop_truncated, sop.*) are handled by per-view subscribers
      // via useWsSubscriber against the same pooled connection.
    }
  };

  function connect(): void {
    if (!sessionId || sub) return;
    sub = subscribe(sessionId, {
      onMessage: dispatch,
      onStatus: (s) => { wsStatus.value = s; },
    });
  }

  function disconnect(): void {
    sub?.unsubscribe();
    sub = null;
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
