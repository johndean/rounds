/**
 * useWsSubscriber — register typed WS message handlers for the current view.
 *
 * Counterpart to useSyncController: that composable owns the ProcessingView's
 * specific refs (processingStage / metrics / failureCategory / sttReady).
 * useWsSubscriber is the generic surface — pass a {type: handler} map and the
 * underlying connection pool routes matching messages to your handler.
 *
 * Multiple views on the same session share one WebSocket via wsConnectionPool;
 * each view registers only the types it cares about. Unhandled types are
 * dropped silently per-subscriber but other subscribers on the same socket
 * still see them.
 *
 * Usage:
 *
 *   useWsSubscriber(props.id, {
 *     correction_applied:    (msg) => scheduleRefresh(),
 *     timeline_ready:        ()    => void load(),
 *     discrepancy_resolved:  (msg) => scheduleRefresh(),
 *   });
 *
 * Lifecycle is automatic: subscribes on call, unsubscribes onUnmounted.
 */
import { onUnmounted, ref } from 'vue';
import { subscribe, type WsMessage, type WsMessageHandler, type WsPoolSubscription, type WsStatus } from './wsConnectionPool';

export type WsMessageHandlers = Partial<Record<string, (msg: WsMessage) => void>>;

export function useWsSubscriber(sessionId: string, handlers: WsMessageHandlers) {
  const wsStatus = ref<WsStatus>('disconnected');
  let sub: WsPoolSubscription | null = null;

  const dispatch: WsMessageHandler = (msg) => {
    const t = typeof msg.type === 'string' ? msg.type : '';
    if (!t) return;
    const fn = handlers[t];
    if (fn) {
      try { fn(msg); }
      catch (e) { console.error(`[useWsSubscriber] handler for "${t}" threw`, e); }
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

  // Auto-connect on mount (caller can immediately destructure refs).
  connect();
  onUnmounted(disconnect);

  return { wsStatus, connect, disconnect };
}
