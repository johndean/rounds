/**
 * useEditorPersistence — restore scroll position, active segment,
 * currentTime, and playback rate across page reloads.
 *
 * Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 3.
 * Audit IDs closed: E20 (refresh persistence), E21 (rate persistence).
 *
 * Critical design corrections from review:
 *   1. localStorage keyed by (session_id, tabRole) where tabRole is
 *      'writer' or 'reader'. Phase 1 lock state determines the role;
 *      a read-only tab does NOT clobber the writer's record.
 *   2. Schema-versioned blob — bump SCHEMA_VERSION when the shape
 *      changes. Older blobs are discarded silently.
 *   3. Debounced 500ms writes; rAF-coalesced reads. localStorage is
 *      synchronous; we don't want it on the timeupdate hot path.
 *   4. If localStorage is full / unavailable, all operations no-op
 *      gracefully (private browsing, storage quota, SSR build).
 */
import { computed, onUnmounted, watch, type Ref } from 'vue';

const SCHEMA_VERSION = 1 as const;

interface PersistedState {
  v: typeof SCHEMA_VERSION;
  /** Playback time in seconds. */
  t: number;
  /** Playback rate (1.0 / 1.25 / 1.5 / etc). */
  r: number;
  /** TranscriptPane scrollTop in pixels. */
  s: number;
  /** Active segment id (so we restore even if scroll math drifts). */
  a: string | null;
  /** ISO timestamp of the write (for debugging stale blobs). */
  ts: string;
}

function _key(sessionId: string, tabRole: 'writer' | 'reader'): string {
  return `rounds:editor:v${SCHEMA_VERSION}:${tabRole}:${sessionId}`;
}

function _safeRead(key: string): PersistedState | null {
  try {
    if (typeof localStorage === 'undefined') return null;
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedState;
    if (parsed.v !== SCHEMA_VERSION) return null;
    return parsed;
  } catch {
    return null;
  }
}

function _safeWrite(key: string, state: PersistedState): void {
  try {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(key, JSON.stringify(state));
  } catch {
    // Quota exceeded / private browsing — silent fail.
  }
}

export interface EditorPersistenceOptions {
  sessionId: string;
  /** Phase 1 lock state. true => writer; null/false => reader. */
  isHolder: Ref<boolean | null>;
  /** Live refs of the values we persist. */
  time: Ref<number>;
  rate: Ref<number>;
  scrollTop: Ref<number>;
  activeSegmentId: Ref<string | null>;
}

export function useEditorPersistence(opts: EditorPersistenceOptions) {
  const tabRole = computed<'writer' | 'reader'>(() => (opts.isHolder.value === true ? 'writer' : 'reader'));
  const storageKey = computed(() => _key(opts.sessionId, tabRole.value));

  // ── Restore ─────────────────────────────────────────────────────────
  function restore(): PersistedState | null {
    // Only the writer tab restores from the writer slot; reader tabs
    // restore from their own (or get nothing on first open).
    return _safeRead(storageKey.value);
  }

  // ── Persist (debounced 500ms) ──────────────────────────────────────
  let writeTimer: ReturnType<typeof setTimeout> | null = null;
  function _scheduleWrite(): void {
    if (writeTimer) clearTimeout(writeTimer);
    writeTimer = setTimeout(() => {
      writeTimer = null;
      _safeWrite(storageKey.value, {
        v:  SCHEMA_VERSION,
        t:  opts.time.value,
        r:  opts.rate.value,
        s:  opts.scrollTop.value,
        a:  opts.activeSegmentId.value,
        ts: new Date().toISOString(),
      });
    }, 500);
  }

  // Reactive watchers — any of the 4 fields changing reschedules a write.
  // We do NOT watch on the timeupdate hot path directly; the parent
  // throttles time updates upstream.
  watch(
    () => [opts.time.value, opts.rate.value, opts.scrollTop.value, opts.activeSegmentId.value] as const,
    () => _scheduleWrite(),
    { flush: 'post' },
  );

  onUnmounted(() => {
    if (writeTimer) {
      clearTimeout(writeTimer);
      // Best-effort final flush so closing the tab cleanly preserves state.
      _safeWrite(storageKey.value, {
        v:  SCHEMA_VERSION,
        t:  opts.time.value,
        r:  opts.rate.value,
        s:  opts.scrollTop.value,
        a:  opts.activeSegmentId.value,
        ts: new Date().toISOString(),
      });
    }
  });

  return {
    restore,
    storageKey,
    tabRole,
  };
}
