/**
 * frontend/src/stores/featureFlags.ts
 *
 * Purpose:
 *     Pinia store for backend-SSOT feature flags surfaced via /v1/version.
 *     AppHeader.vue fetches /v1/version on mount and pipes the relevant
 *     fields into this store; consumers read the refs reactively.
 *
 *     Phase 3.5 + 4 (2026-06-06): `splitMergeEnabled` gates the split/merge
 *     UI in SegmentText.vue (right-click "Split here", Ctrl+Shift+S, etc.).
 *     Defaults to `false` so the menu items stay hidden on environments
 *     where the backend flag (`SPLIT_MERGE_ENABLED`) is off.
 *
 * Related plan:
 *     docs/plans/2026-06-06-002-phase-3.5-split-merge-executor-v2.md §4.6 + §4.7
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useFeatureFlagsStore = defineStore('featureFlags', () => {
  /** Backend SSOT — set from /v1/version on app mount (AppHeader). */
  const splitMergeEnabled = ref(false);

  function setSplitMergeEnabled(v: boolean): void {
    splitMergeEnabled.value = v;
  }

  return { splitMergeEnabled, setSplitMergeEnabled };
});
