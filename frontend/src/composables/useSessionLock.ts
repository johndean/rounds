/**
 * useSessionLock — concurrent-edit lock for the session editor.
 *
 * Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 1.
 * Audit IDs closed: E1 (silent concurrent-edit overwrite).
 *
 * Backend: app/api/locks.py exposes acquire / heartbeat / release / holder
 * / force-take. TTL is 90s (3 missed 30s heartbeats). Heartbeats pause when
 * the tab is hidden (Page Visibility API) so background tabs don't keep
 * the lock alive forever.
 *
 * Critical: this composable FAILS CLOSED. If the lock service is
 * unreachable, `isHolder.value` becomes false and `lockError.value` is
 * populated — the editor MUST gate destructive writes on isHolder. The
 * earlier UIFER draft said fail-open; reviewers flagged that as the exact
 * bug Phase 1 is meant to prevent.
 *
 * Usage:
 *
 *   const { isHolder, holder, lockError, forceTake, release } = useSessionLock(props.id);
 *
 *   // Render-time:
 *   v-if="lockError" → red banner "Lock service unavailable"
 *   v-else-if="!isHolder && holder" → yellow banner "In use by ${holder.user_email}"
 *
 * Lifecycle:
 *   onMounted → acquire(), start 30s heartbeat (skipped while document.hidden)
 *   onUnmounted / beforeunload / visibilitychange→hidden → release()
 */
import { computed, onMounted, onUnmounted, ref, type Ref } from 'vue';

import { http, ApiError } from '@/services/http';

const HEARTBEAT_INTERVAL_MS = 30_000;

export interface LockHolder {
  user_email: string;
  acquired_at: string;
  heartbeat_at: string;
  expires_at: string;
}

interface LockState {
  acquired: boolean;
  is_self: boolean;
  holder: LockHolder | null;
}

export function useSessionLock(sessionId: Ref<string> | string) {
  const sid = computed(() => (typeof sessionId === 'string' ? sessionId : sessionId.value));

  // Tri-state: null = haven't checked yet; true = we hold it; false = someone else does.
  const isHolder = ref<boolean | null>(null);
  const holder = ref<LockHolder | null>(null);
  /** Non-null when the lock service is unreachable. Frontend treats this as fail-closed. */
  const lockError = ref<string | null>(null);

  let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  let cancelled = false;

  async function _post(path: string): Promise<LockState | null> {
    try {
      const resp = await http<LockState>(path, { method: 'POST' });
      lockError.value = null;
      return resp;
    } catch (e) {
      if (e instanceof ApiError) {
        // 401 → http.ts handles redirect. 403 means we tried force-take without admin.
        lockError.value = e.message || `lock_${e.status}`;
      } else {
        lockError.value = (e as Error)?.message || 'lock_unreachable';
      }
      return null;
    }
  }

  function _apply(state: LockState | null): void {
    if (cancelled) return;
    if (state === null) {
      isHolder.value = false;
      // keep holder.value as the last-known so the banner can still render
      return;
    }
    isHolder.value = state.acquired && state.is_self;
    holder.value = state.holder;
  }

  async function acquire(): Promise<void> {
    const state = await _post(`/v1/sessions/${sid.value}/lock/acquire`);
    _apply(state);
  }

  async function heartbeat(): Promise<void> {
    // Page Visibility API — pause heartbeat when the tab is hidden. Reduces
    // load + lets stale locks expire so other operators aren't blocked by
    // a tab someone forgot in another window.
    if (typeof document !== 'undefined' && document.hidden) return;
    const state = await _post(`/v1/sessions/${sid.value}/lock/heartbeat`);
    _apply(state);
  }

  async function release(): Promise<void> {
    try {
      // Use sendBeacon when releasing from a beforeunload — fetch may be cancelled.
      // But we still want a POST with auth, so fall back to http() and accept the
      // race. The 90s TTL is the safety net.
      await http<void>(`/v1/sessions/${sid.value}/lock/release`, { method: 'POST' });
    } catch {
      // best-effort
    }
  }

  async function forceTake(): Promise<void> {
    const state = await _post(`/v1/sessions/${sid.value}/lock/force-take`);
    _apply(state);
  }

  function onVisibilityChange(): void {
    if (typeof document === 'undefined') return;
    if (!document.hidden) {
      // Tab regained focus — re-heartbeat immediately so banner state catches up.
      void heartbeat();
    }
  }

  function onBeforeUnload(): void {
    // Best-effort synchronous release. Beacon would be cleaner but bypasses auth.
    void release();
  }

  onMounted(() => {
    void acquire();
    heartbeatTimer = setInterval(() => { void heartbeat(); }, HEARTBEAT_INTERVAL_MS);
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibilityChange);
    }
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', onBeforeUnload);
    }
  });

  onUnmounted(() => {
    cancelled = true;
    if (heartbeatTimer !== null) clearInterval(heartbeatTimer);
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibilityChange);
    }
    if (typeof window !== 'undefined') {
      window.removeEventListener('beforeunload', onBeforeUnload);
    }
    void release();
  });

  return {
    isHolder,
    holder,
    lockError,
    forceTake,
    release,
  };
}
