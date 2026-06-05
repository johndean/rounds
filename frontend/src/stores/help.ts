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
import { askHelp, type HelpAskSource } from '@/services/helpApi';
import { ApiError } from '@/services/http';

export type HelpRole = 'user' | 'admin';

export interface AskTurn {
  id: string;
  question: string;
  answer: string;
  citations: HelpAskSource[];
  streaming: boolean;
  done: boolean;
  errorCode: string | null;
  errorMessage: string | null;
  startedAt: number;
}

function makeAskTurnId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `ask-${Math.floor(Math.random() * 1e9).toString(36)}-${Date.now().toString(36)}`;
}

function helpErrorMessage(e: unknown): { code: string; message: string } {
  if (e instanceof ApiError) {
    // The backend returns 429 with a structured detail; surface that
    // distinctly so the composer can render a useful chip.
    if (e.status === 429) {
      return {
        code: 'HELP_ASK_RATE_LIMIT',
        message: 'Hourly Ask AI limit reached. Try again in a few minutes.',
      };
    }
    if (e.status === 404) {
      return { code: 'NOT_ENABLED', message: 'Ask AI is not enabled on this environment.' };
    }
    if (e.status === 400) {
      return { code: 'BAD_REQUEST', message: 'That question is empty or too long.' };
    }
    return { code: `HTTP_${e.status}`, message: e.message || 'Ask AI request failed.' };
  }
  if (e instanceof DOMException && e.name === 'AbortError') {
    return { code: 'ABORTED', message: 'Cancelled.' };
  }
  return { code: 'UNKNOWN', message: (e as Error)?.message || 'Ask AI request failed.' };
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

  // ── Ask AI state (Phase 2 — real backend wiring) ─────────
  const askThread = ref<AskTurn[]>([]);
  const isStreaming = ref(false);
  /** Backend SSOT — frontend reads this from /v1/version at app mount. */
  const askEnabled = ref(false);
  let activeAbortController: AbortController | null = null;

  function setAskEnabled(v: boolean): void { askEnabled.value = v; }

  /**
   * Phase 2 — calls POST /v1/help/ask, mutates the matching turn in
   * askThread with the answer (and citations) or with an error code.
   * Returns the turn after the call resolves; returns null if a turn is
   * already in flight or the question is too short.
   */
  async function startAsk(questionRaw: string): Promise<AskTurn | null> {
    const q = questionRaw.trim();
    if (q.length < 2) return null;
    if (isStreaming.value) return null;

    const turn: AskTurn = {
      id: makeAskTurnId(),
      question: q,
      answer: '',
      citations: [],
      streaming: true,
      done: false,
      errorCode: null,
      errorMessage: null,
      startedAt: Date.now(),
    };
    askThread.value = [...askThread.value, turn];
    isStreaming.value = true;
    activeAbortController = new AbortController();
    const controller = activeAbortController;

    try {
      const resp = await askHelp({
        question: q,
        page_key: pageKey.value,
        signal: controller.signal,
      });
      const i = askThread.value.findIndex((t) => t.id === turn.id);
      if (i >= 0) {
        const next = [...askThread.value];
        next[i] = {
          ...next[i],
          answer: resp.answer,
          citations: resp.sources,
          streaming: false,
          done: true,
        };
        askThread.value = next;
      }
    } catch (e) {
      const i = askThread.value.findIndex((t) => t.id === turn.id);
      if (i >= 0) {
        const next = [...askThread.value];
        const err = helpErrorMessage(e);
        next[i] = {
          ...next[i],
          streaming: false,
          done: false,
          errorCode: err.code,
          errorMessage: err.message,
        };
        askThread.value = next;
      }
    } finally {
      isStreaming.value = false;
      if (activeAbortController === controller) activeAbortController = null;
    }
    return askThread.value.find((t) => t.id === turn.id) ?? null;
  }

  function abortAsk(): void {
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }
    isStreaming.value = false;
  }
  function clearAskThread(): void {
    abortAsk();
    askThread.value = [];
  }

  return {
    // panel
    open, pageKey, setPageKey, toggle, show, hide,
    // search
    searchQuery, searchResults, semanticLoading, semanticError,
    // resolved
    resolved,
    // ask
    askThread, isStreaming, askEnabled, setAskEnabled,
    startAsk, abortAsk, clearAskThread,
  };
});
