/**
 * frontend/src/services/helpArticlesApi.ts
 *
 * Purpose:
 *     Typed wrappers around the Phase 3 /v1/help/articles/* CMS routes.
 *     Separate file from helpApi.ts so the Ask AI surface (Phase 2)
 *     stays compact and the article CRUD lives where its consumers do
 *     (HelpEditor view, HelpArticleEditorDialog, panel API-fetch path).
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §8.2
 */
import { http } from './http';

export interface HelpStep {
  title: string;
  body: string;
}

export interface HelpArticleDTO {
  id: string;
  slug: string;
  title: string;
  summary: string;
  category: string;
  audience: 'users' | 'admin';
  feature_tags: string[];
  steps: HelpStep[];
  related_article_ids: string[];
  display_order: number;
  is_published: boolean;
  content_domain: string;
  workflow_slug: string | null;
  version: number;
  last_edited_by: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface HelpArticleVersion {
  id: string;
  article_id: string;
  version: number;
  snapshot: HelpArticleDTO;
  edited_by: string;
  edited_at: string | null;
}

export interface HelpCoverageResponse {
  by_domain: Record<string, number>;
  total_published: number;
  total_drafts: number;
}

export interface HelpArticleCreatePayload {
  title: string;
  summary?: string;
  category?: string;
  audience?: 'users' | 'admin';
  feature_tags?: string[];
  steps?: HelpStep[];
  related_article_ids?: string[];
  display_order?: number;
  is_published?: boolean;
  content_domain?: string;
  workflow_slug?: string | null;
  slug?: string;
}

export type HelpArticleUpdatePayload = Partial<HelpArticleCreatePayload>;

export interface HelpListFilters {
  feature_tag?: string;
  audience?: 'users' | 'admin';
  content_domain?: string;
  limit?: number;
}

// ── List ─────────────────────────────────────────────────────────────
export async function listArticles(filters: HelpListFilters = {}): Promise<HelpArticleDTO[]> {
  const params = new URLSearchParams();
  if (filters.feature_tag) params.set('feature_tag', filters.feature_tag);
  if (filters.audience) params.set('audience', filters.audience);
  if (filters.content_domain) params.set('content_domain', filters.content_domain);
  if (filters.limit) params.set('limit', String(filters.limit));
  const qs = params.toString() ? `?${params.toString()}` : '';
  return http<HelpArticleDTO[]>(`/v1/help/articles${qs}`);
}

// ── Detail ───────────────────────────────────────────────────────────
export async function getArticle(id: string): Promise<HelpArticleDTO> {
  return http<HelpArticleDTO>(`/v1/help/articles/${id}`);
}

// ── Create (admin) ───────────────────────────────────────────────────
export async function createArticle(payload: HelpArticleCreatePayload): Promise<HelpArticleDTO> {
  return http<HelpArticleDTO>('/v1/help/articles', {
    method: 'POST',
    body: payload,
  });
}

// ── Update (admin; snapshots prior version) ─────────────────────────
export async function updateArticle(id: string, payload: HelpArticleUpdatePayload): Promise<HelpArticleDTO> {
  return http<HelpArticleDTO>(`/v1/help/articles/${id}`, {
    method: 'PATCH',
    body: payload,
  });
}

// ── Archive (admin) ─────────────────────────────────────────────────
export async function archiveArticle(id: string): Promise<HelpArticleDTO> {
  return http<HelpArticleDTO>(`/v1/help/articles/${id}/archive`, {
    method: 'PATCH',
  });
}

// ── Reorder (admin) ─────────────────────────────────────────────────
export async function reorderArticles(items: Array<{ id: string; display_order: number }>): Promise<{ updated: number }> {
  return http<{ updated: number }>('/v1/help/articles/reorder', {
    method: 'PATCH',
    body: { items },
  });
}

// ── Versions (admin) ────────────────────────────────────────────────
export async function listVersions(articleId: string): Promise<HelpArticleVersion[]> {
  return http<HelpArticleVersion[]>(`/v1/help/articles/${articleId}/versions`);
}

export async function getVersion(articleId: string, version: number): Promise<HelpArticleVersion> {
  return http<HelpArticleVersion>(`/v1/help/articles/${articleId}/versions/${version}`);
}

// ── Coverage (admin) ────────────────────────────────────────────────
export async function getCoverage(): Promise<HelpCoverageResponse> {
  return http<HelpCoverageResponse>('/v1/help/coverage');
}

// ── Search ──────────────────────────────────────────────────────────
export async function searchArticles(q: string, limit = 20): Promise<HelpArticleDTO[]> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return http<HelpArticleDTO[]>(`/v1/help/search?${params.toString()}`);
}

// ── Phase 4 admin actions ───────────────────────────────────────────

export interface BulkPublishSkippedRow {
  id: string;
  title: string;
  reason: string;
  wordsOk?: boolean;
  summaryOk?: boolean;
  stepsOk?: boolean;
  wordCount?: number;
  summaryLen?: number;
  stepCount?: number;
}

export interface BulkPublishResponse {
  total_attempted: number;
  published: number;
  published_ids: string[];
  skipped: BulkPublishSkippedRow[];
}

export interface EnqueueResponse {
  task_id: string;
  task: string;
  enqueued: boolean;
}

/** Inline (non-Celery) compliance-gated bulk publish of all drafts. */
export async function bulkPublishDrafts(): Promise<BulkPublishResponse> {
  return http<BulkPublishResponse>('/v1/help/admin/bulk-publish', { method: 'POST' });
}

/** Enqueue the fix_help_summaries Celery task. */
export async function fixSummaries(): Promise<EnqueueResponse> {
  return http<EnqueueResponse>('/v1/help/admin/fix-summaries', { method: 'POST' });
}

/** Enqueue the expand_help_steps Celery task. */
export async function expandSteps(): Promise<EnqueueResponse> {
  return http<EnqueueResponse>('/v1/help/admin/expand-steps', { method: 'POST' });
}

/** Enqueue the expand_faq_steps Celery task. */
export async function expandFaqs(): Promise<EnqueueResponse> {
  return http<EnqueueResponse>('/v1/help/admin/expand-faqs', { method: 'POST' });
}
