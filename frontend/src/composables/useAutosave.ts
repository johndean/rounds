/**
 * useAutosave — debounced per-segment autosave on the editor.
 *
 * Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 2.
 * Audit IDs closed: E24 (autosave — never lose another keystroke).
 *
 * Critical design corrections from review:
 *   1. Anti-no-op guard lives in the backend (corrections.py, Phase 1.5)
 *      so the redo tail is not silently truncated by blur-without-edit.
 *      This composable still calls the endpoint; backend short-circuits.
 *   2. Status indicator uses a shallowRef<Map> with manual triggerRef
 *      so the v-for over 600 segments in TranscriptPane does NOT
 *      reconcile on every save. Per-segment status is consumed via
 *      `provide('autosaveStatus')` -> per-segment computed reads.
 *   3. Lock-gated: `enabled.value === true` is required before any
 *      write fires. When the lock is held by another user (Phase 1
 *      banner state), autosave silently no-ops; manual Save still
 *      works for emergency last-write-wins recovery.
 *   4. Compaction: per-segment debounce 400ms (typing-friendly) plus
 *      a 3-second rate-limit on consecutive writes (correction_ledger
 *      protection per reviewer flag). Flush-on-blur and
 *      flush-on-segment-switch bypass the rate limit so the user
 *      always gets latest-saved-state when context changes.
 *
 * Usage (in EditorView):
 *
 *     import { provide } from 'vue';
 *     import { useAutosave, AUTOSAVE_STATUS_KEY } from '@/composables/useAutosave';
 *     const { schedule, flush, status } = useAutosave(props.id, isHolder);
 *     provide(AUTOSAVE_STATUS_KEY, status);
 *
 *     // Listen for editor child events:
 *     function onAutosave(segId: string, oldText: string, newText: string) {
 *       schedule(segId, oldText, newText);
 *     }
 *     function onSegmentSwitch() { flush(); }
 *
 * Usage (in TranscriptPane / SegmentText):
 *
 *     import { inject } from 'vue';
 *     import { AUTOSAVE_STATUS_KEY } from '@/composables/useAutosave';
 *     const status = inject(AUTOSAVE_STATUS_KEY, null);
 *     const mySeg = computed(() => status?.value.get(seg.id) ?? 'idle');
 */
import { computed, onUnmounted, shallowRef, triggerRef, type ComputedRef, type InjectionKey, type Ref, type ShallowRef } from 'vue';

import { corrections as correctionsApi } from '@/services/api';
import { ApiError } from '@/services/http';

export type AutosaveStatus = 'idle' | 'saving' | 'saved' | 'error';

export interface AutosaveStatusMap {
  get(segId: string): AutosaveStatus | undefined;
}

export const AUTOSAVE_STATUS_KEY: InjectionKey<ShallowRef<AutosaveStatusMap>> = Symbol('autosaveStatus');

const DEBOUNCE_MS = 400;
const COMPACTION_MS = 3000;  // reviewer-requested: prevent correction_ledger explosion

interface PendingWrite {
  oldText: string;
  newText: string;
  // The segment's content_hash as the client last knew it. Sent as
  // expected_content_hash so a stale autosave is dropped server-side when a
  // split/merge rewrote the row. undefined => legacy unconditional write.
  contentHash: string | undefined;
  timer: ReturnType<typeof setTimeout> | null;
  lastFlushedAt: number;
}

export function useAutosave(
  sessionId: string,
  enabled: Ref<boolean | null> | ComputedRef<boolean>,
) {
  // shallowRef<Map> so mutations don't reconcile the v-for in TranscriptPane.
  // Components subscribe by id; on triggerRef, only computed-returning-id
  // reads invalidate.
  const status = shallowRef<Map<string, AutosaveStatus>>(new Map());
  const pending = new Map<string, PendingWrite>();

  const isEnabled = computed(() => enabled.value === true);

  function _setStatus(segId: string, next: AutosaveStatus): void {
    const m = status.value;
    m.set(segId, next);
    triggerRef(status);
  }

  function _clearPending(segId: string): void {
    const p = pending.get(segId);
    if (p?.timer) clearTimeout(p.timer);
    pending.delete(segId);
  }

  async function _writeOnce(segId: string, oldText: string, newText: string, contentHash: string | undefined): Promise<void> {
    _setStatus(segId, 'saving');
    try {
      await correctionsApi.apply(sessionId, {
        segment_id:      segId,
        correction_type: 'text_edit',
        old_text:        oldText,
        new_text:        newText,
        ...(contentHash ? { expected_content_hash: contentHash } : {}),
      });
      _setStatus(segId, 'saved');
      // Fade the "Saved" badge to idle after 2s. Re-render only the
      // affected segment via triggerRef.
      setTimeout(() => {
        const m = status.value;
        if (m.get(segId) === 'saved') {
          m.set(segId, 'idle');
          triggerRef(status);
        }
      }, 2000);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        // http.ts already redirected; quiet exit.
        return;
      }
      _setStatus(segId, 'error');
    }
  }

  /**
   * Schedule a debounced save. Caller passes the segment id, the old
   * (committed) text, and the new draft. Backend anti-no-op guard
   * (Phase 1.5) short-circuits when old == new, so the network call
   * still fires but produces no ledger churn.
   *
   * Rate-limit: if a save fired for this segment within COMPACTION_MS,
   * the next save waits the remaining window so we don't explode
   * correction_ledger row count on rapid typing.
   */
  function schedule(segId: string, oldText: string, newText: string, contentHash?: string): void {
    if (!isEnabled.value) return;
    const existing = pending.get(segId);
    if (existing?.timer) clearTimeout(existing.timer);

    const now = Date.now();
    const lastFlushedAt = existing?.lastFlushedAt ?? 0;
    const sinceFlush = now - lastFlushedAt;
    const debounce = sinceFlush < COMPACTION_MS
      ? Math.max(DEBOUNCE_MS, COMPACTION_MS - sinceFlush)
      : DEBOUNCE_MS;

    const entry: PendingWrite = {
      oldText,
      newText,
      contentHash,
      timer: null,
      lastFlushedAt,
    };
    entry.timer = setTimeout(() => {
      const p = pending.get(segId);
      if (!p) return;
      p.timer = null;
      p.lastFlushedAt = Date.now();
      void _writeOnce(segId, p.oldText, p.newText, p.contentHash);
    }, debounce);
    pending.set(segId, entry);
  }

  /**
   * Flush pending writes immediately. Pass a segId to flush just one,
   * or omit to flush all pending. Used on blur and on segment-switch
   * — context changes should be persisted right away.
   *
   * Bypasses the COMPACTION_MS rate-limit (the user is leaving the
   * field; correctness > ledger compaction).
   */
  function flush(segId?: string): void {
    if (!isEnabled.value) {
      if (segId) _clearPending(segId);
      else { for (const id of [...pending.keys()]) _clearPending(id); }
      return;
    }
    const ids = segId ? [segId] : [...pending.keys()];
    for (const id of ids) {
      const p = pending.get(id);
      if (!p) continue;
      if (p.timer) clearTimeout(p.timer);
      pending.delete(id);
      void _writeOnce(id, p.oldText, p.newText, p.contentHash);
    }
  }

  onUnmounted(() => {
    for (const p of pending.values()) if (p.timer) clearTimeout(p.timer);
    pending.clear();
  });

  return {
    schedule,
    flush,
    status,
    isEnabled,
  };
}
