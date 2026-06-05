/**
 * frontend/src/stores/help.ts
 *
 * Purpose:
 *     Pinia store for the rounds.vin Help Center inline panel. Mirrors the
 *     po.vin help store shape (open/hide/toggle + pageKey + resolved
 *     content + search + askThread) so future phases can layer in the
 *     backend wiring (Phase 2: Ask AI Gemini; Phase 3: backend CMS;
 *     Phase 4: CC-Rounds compliance; Phase 5: AI FAQ corpus) without
 *     reshaping the consumer components.
 *
 *     Phase 1 surface (this file):
 *       - open / hide / toggle
 *       - pageKey (auto-resolved from route via setPageKey())
 *       - resolved content (read directly from HELP_CONTENT — no override
 *         layer yet; that ships in Phase 3 with the backend CMS)
 *       - client-side search (substring + title-rank fallback; semantic
 *         backend lands in Phase 2)
 *       - askThread + isStreaming placeholders (Ask AI tab is a UI-only
 *         placeholder in Phase 1 — Phase 2 wires the real backend route)
 *
 * Responsibilities:
 *     - Panel open/close lifecycle.
 *     - Route → pageKey resolution.
 *     - Searchable corpus accessor.
 *     - Stable API surface for Phase 2+ to extend.
 *
 * Critical invariants:
 *     - The panel state (open) MUST be driven only by user action (button
 *       or Esc key). Routes do not auto-open the panel.
 *     - HELP_CONTENT shape is the SSOT for Phase 1 content; future phases
 *       layer overrides on top of resolved (mirroring po.vin's pattern).
 *
 * Related plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md
 */
import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import {
  HELP_CONTENT,
  type HelpContentShape,
  type HelpTopic,
} from '@/constants/help-content';

export type HelpRole = 'user' | 'admin';

export interface AskTurn {
  id: string;
  question: string;
  answer: string;
  citations: { id: string; title: string }[];
  streaming: boolean;
  done: boolean;
  errorCode: string | null;
  errorMessage: string | null;
  startedAt: number;
}

export const useHelpStore = defineStore('help', () => {
  // ── Panel state ─────────────────────────────────────────
  const open = ref(false);
  const pageKey = ref<string>('dashboard');

  function setPageKey(key: string): void { pageKey.value = key; }
  function toggle(): void { open.value = !open.value; }
  function show(): void { open.value = true; }
  function hide(): void { open.value = false; }

  // ── Search (client-side substring + title-rank, Phase 1) ─
  const searchQuery = ref<string>('');
  const semanticLoading = ref(false);      // placeholder — wired in Phase 2
  const semanticError = ref<string | null>(null);

  const searchResults = computed<HelpTopic[]>(() => {
    const q = searchQuery.value.trim().toLowerCase();
    if (q.length < 2) return [];
    const out: HelpTopic[] = [];
    for (const page of Object.values(HELP_CONTENT.pages)) {
      for (const role of ['user', 'admin'] as const) {
        const entry = page[role];
        if (!entry) continue;
        for (const t of entry.topics) {
          const hay = (t.q + ' ' + t.a).toLowerCase();
          if (hay.includes(q)) out.push(t);
        }
      }
    }
    for (const t of HELP_CONTENT.faq) {
      const hay = (t.q + ' ' + t.a).toLowerCase();
      if (hay.includes(q)) out.push(t);
    }
    // Rank: title matches first.
    out.sort((a, b) => {
      const aTitle = a.q.toLowerCase().includes(q) ? 0 : 1;
      const bTitle = b.q.toLowerCase().includes(q) ? 0 : 1;
      return aTitle - bTitle;
    });
    return out;
  });

  // ── Resolved content (Phase 1: passthrough; Phase 3 will layer overrides) ──
  const resolved = computed<HelpContentShape>(() => HELP_CONTENT);

  // ── Ask AI placeholder state (wired in Phase 2) ─────────
  const askThread = ref<AskTurn[]>([]);
  const isStreaming = ref(false);
  const askEnabled = ref(false); // backend reports this via /v1/version in Phase 2

  function startAsk(question: string): null {
    // Phase 1 stub — Phase 2 will replace this with real Gemini wiring.
    // Caller component handles the user-facing "coming soon" surface.
    void question;
    return null;
  }
  function abortAsk(): void { isStreaming.value = false; }
  function clearAskThread(): void { askThread.value = []; }

  return {
    // panel
    open, pageKey, setPageKey, toggle, show, hide,
    // search
    searchQuery, searchResults, semanticLoading, semanticError,
    // resolved
    resolved,
    // ask
    askThread, isStreaming, askEnabled,
    startAsk, abortAsk, clearAskThread,
  };
});
