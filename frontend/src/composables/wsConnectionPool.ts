/**
 * wsConnectionPool — one WebSocket per sessionId, shared across all consumers.
 *
 * Each session can have many subscribers (ProcessingView's useSyncController,
 * EditorView's useWsSubscriber for correction_applied / discrepancy_resolved /
 * timeline_ready, ViewerView for captioned_video_*, etc.). Without a pool,
 * each composable would open its own socket — N views × M sessions sockets,
 * burning Railway connection budget and triggering duplicate dispatch work
 * on the bridge side.
 *
 * The pool refcounts subscribers per sessionId. First subscriber opens the
 * socket; last subscriber to unsubscribe closes it. Every message is fanned
 * out to every registered message handler; every status change is fanned out
 * to every registered status listener.
 *
 * Handlers MUST NOT throw — try/catch wraps each invocation so one bad
 * handler can't break the fan-out for the rest.
 */

export type WsStatus = 'disconnected' | 'connecting' | 'connected' | 'error';
export type WsMessage = Record<string, unknown>;
export type WsMessageHandler = (msg: WsMessage) => void;
export type WsStatusListener = (status: WsStatus) => void;

interface PooledSocket {
  sessionId: string;
  ws: WebSocket | null;
  status: WsStatus;
  messageHandlers: Set<WsMessageHandler>;
  statusListeners: Set<WsStatusListener>;
}

const pool = new Map<string, PooledSocket>();

function emitStatus(entry: PooledSocket, status: WsStatus): void {
  entry.status = status;
  entry.statusListeners.forEach((cb) => {
    try { cb(status); } catch (e) { console.error('[wsPool] status listener threw', e); }
  });
}

function openSocket(entry: PooledSocket): void {
  if (entry.ws) return;
  emitStatus(entry, 'connecting');
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${proto}//${window.location.host}/v1/ws/sessions/${encodeURIComponent(entry.sessionId)}`;
  let ws: WebSocket;
  try {
    ws = new WebSocket(url);
  } catch {
    emitStatus(entry, 'error');
    return;
  }
  entry.ws = ws;
  ws.onopen = () => emitStatus(entry, 'connected');
  ws.onerror = () => emitStatus(entry, 'error');
  ws.onclose = () => {
    if (entry.ws === ws) {
      entry.ws = null;
      emitStatus(entry, 'disconnected');
    }
  };
  ws.onmessage = (event) => {
    let msg: WsMessage;
    try { msg = JSON.parse(event.data); }
    catch { return; }
    entry.messageHandlers.forEach((h) => {
      try { h(msg); } catch (e) { console.error('[wsPool] message handler threw', e); }
    });
  };
}

function destroyIfIdle(sessionId: string): void {
  const entry = pool.get(sessionId);
  if (!entry) return;
  if (entry.messageHandlers.size === 0 && entry.statusListeners.size === 0) {
    try { entry.ws?.close(); } catch { /* ignore */ }
    entry.ws = null;
    pool.delete(sessionId);
  }
}

export interface WsPoolSubscription {
  unsubscribe: () => void;
}

export interface SubscribeOptions {
  onMessage?: WsMessageHandler;
  onStatus?: WsStatusListener;
}

/**
 * Subscribe to a session's WebSocket. Opens the socket if not already open.
 * Returns an unsubscribe function — call it on component unmount.
 *
 * `onStatus` is invoked once synchronously with the current status, then on
 * every change. Useful for refs that mirror connection state.
 */
export function subscribe(sessionId: string, opts: SubscribeOptions): WsPoolSubscription {
  let entry = pool.get(sessionId);
  if (!entry) {
    entry = {
      sessionId,
      ws: null,
      status: 'disconnected',
      messageHandlers: new Set(),
      statusListeners: new Set(),
    };
    pool.set(sessionId, entry);
  }
  if (opts.onMessage) entry.messageHandlers.add(opts.onMessage);
  if (opts.onStatus) {
    entry.statusListeners.add(opts.onStatus);
    try { opts.onStatus(entry.status); } catch (e) { console.error('[wsPool] status listener threw on attach', e); }
  }
  openSocket(entry);
  return {
    unsubscribe: () => {
      const e = pool.get(sessionId);
      if (!e) return;
      if (opts.onMessage) e.messageHandlers.delete(opts.onMessage);
      if (opts.onStatus) e.statusListeners.delete(opts.onStatus);
      destroyIfIdle(sessionId);
    },
  };
}

/** Test helper — close all sockets and clear the pool. */
export function _resetPool(): void {
  pool.forEach((entry) => { try { entry.ws?.close(); } catch { /* ignore */ } });
  pool.clear();
}

/** Test helper — peek pool state. */
export function _poolSize(): number {
  return pool.size;
}
