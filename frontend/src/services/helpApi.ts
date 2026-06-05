/**
 * frontend/src/services/helpApi.ts
 *
 * Purpose:
 *     Browser-side wrapper around the /v1/help/ask backend route.
 *     Phase 2 ships request/response only — streaming SSE is a Phase 3+
 *     polish item (see plan ยง11 "out of scope" note about simulated
 *     streaming).
 *
 * Responsibilities:
 *     - askHelp({question, page_key?, role?}) -> {answer, sources, used_llm}
 *     - Surface the 429 rate-limit code distinctly from generic errors
 *       so the composer can render a useful chip.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md ยง7.2
 */
import { http } from './http';

export interface HelpAskSource {
  id: string;
  title: string;
  summary: string;
}

export interface HelpAskResponse {
  answer: string;
  sources: HelpAskSource[];
  used_llm: boolean;
}

export interface AskHelpArgs {
  question: string;
  page_key?: string;
  role?: string;
  signal?: AbortSignal;
}

/**
 * POST /v1/help/ask. Returns {answer, sources, used_llm} or throws ApiError.
 * The envelope is unwrapped by the shared http() helper, so callers see
 * the inner data object directly.
 */
export async function askHelp(args: AskHelpArgs): Promise<HelpAskResponse> {
  return http<HelpAskResponse>('/v1/help/ask', {
    method: 'POST',
    body: {
      question: args.question,
      page_key: args.page_key,
      role: args.role,
    },
    signal: args.signal,
  });
}
