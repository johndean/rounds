/**
 * Real API client — talks to the FastAPI backend at /v1/*.
 *
 * Typed thin wrappers around http(). Endpoint shapes mirror the backend
 * routers in app/api/*.
 */
import { http } from './http';

// ─── Auth ────────────────────────────────────────────────────────────────
export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export const auth = {
  login: (email: string, password: string) =>
    http<TokenResponse>('/v1/auth/login', {
      formBody: { username: email, password },
      anonymous: true,
    }),
  me: () => http<{ email: string }>('/v1/auth/me'),
};

// ─── Sessions ────────────────────────────────────────────────────────────
export interface SessionSummary {
  id: string;
  code: string;
  title: string;
  presenter: string | null;
  status: string;
  duration_sec: number | null;
  word_count: number | null;
  segment_count: number | null;
  attendee_count: number | null;
  taxonomy: string[];
}

export interface SessionFilters {
  stage?: string;
  ai?: string;
  f?: string;
  limit?: number;
  offset?: number;
}

function _q(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : '';
}

export const sessions = {
  list: (filters: SessionFilters = {}) =>
    http<SessionSummary[]>(`/v1/sessions${_q({ ...filters })}`),
  get: (id: string) =>
    http<SessionSummary>(`/v1/sessions/${encodeURIComponent(id)}`),
  create: (payload: { code: string; title: string; presenter?: string; duration_sec?: number; attendee_count?: number; taxonomy?: string[] }) =>
    http<SessionSummary>('/v1/sessions', { body: payload, method: 'POST' }),
};

// ─── Segments ────────────────────────────────────────────────────────────
export interface SegmentRow {
  id: string;
  seq: number;
  start_ms: number;
  end_ms: number;
  text: string;
  confidence: number | null;
  flags: string[];
  is_anchor: boolean;
  anchor_kind: string | null;
  slide_id: string | null;
  speaker_id: string | null;
}

export const segments = {
  list: (sessionId: string) =>
    http<SegmentRow[]>(`/v1/sessions/${encodeURIComponent(sessionId)}/segments`),
  edit: (sessionId: string, segmentId: string, patch: Partial<Pick<SegmentRow, 'text' | 'slide_id' | 'speaker_id' | 'flags'>>) =>
    http<SegmentRow>(`/v1/sessions/${sessionId}/segments/${segmentId}`, { body: patch, method: 'PATCH' }),
  reassign: (sessionId: string, segmentId: string, slideId: string) =>
    http<SegmentRow>(`/v1/sessions/${sessionId}/segments/${segmentId}/reassign`, { body: { slide_id: slideId }, method: 'POST' }),
};

// ─── SOP ─────────────────────────────────────────────────────────────────
export const sop = {
  state: (sessionId: string) =>
    http<{ current_stage: string; is_blocked: boolean; blockers: unknown[]; assignees: unknown; sla_target_hours: unknown }>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/sop`,
    ),
  advance: (sessionId: string, toStage: string, note?: string) =>
    http(`/v1/sessions/${sessionId}/sop/advance`, { body: { to_stage: toStage, note }, method: 'POST' }),
  resolveCheck: (sessionId: string, checkId: string, label: string) =>
    http(`/v1/sessions/${sessionId}/sop/checks/resolve`, { body: { check_id: checkId, label }, method: 'POST' }),
};

// ─── Improvements ────────────────────────────────────────────────────────
export interface ImprovementSummary {
  id: string;
  title: string;
  status: string;
  risk: string;
  priority: string;
  submitted_at: string;
  submitted_by: string;
  is_security: boolean;
}

export const improvements = {
  list: (statusFilter?: string) =>
    http<ImprovementSummary[]>(`/v1/improvements${_q({ status_filter: statusFilter })}`),
  get: (id: string) =>
    http(`/v1/improvements/${encodeURIComponent(id)}`),
  suggest: (payload: { title: string; description?: string; type?: string; priority?: string; area?: string; is_security?: boolean }) =>
    http<ImprovementSummary>('/v1/improvements', { body: payload, method: 'POST' }),
  saveStep: (id: string, step: string, body_md: string) =>
    http(`/v1/improvements/${id}/wizard/${step}`, { body: { body_md }, method: 'PUT' }),
  admin: (id: string, patch: { status?: string; risk?: string; target_version?: string; admin_notes?: string }) =>
    http(`/v1/improvements/${id}`, { body: patch, method: 'PATCH' }),
  remove: (id: string) =>
    http(`/v1/improvements/${id}`, { method: 'DELETE' }),
};

// ─── Settings ────────────────────────────────────────────────────────────
export const settingsApi = {
  list: () => http<Record<string, unknown>>('/v1/settings'),
  set: (key: string, value: unknown) =>
    http(`/v1/settings/${encodeURIComponent(key)}`, { body: { key, value }, method: 'PUT' }),
  people: () => http<unknown[]>('/v1/settings/people'),
  groups: () => http<unknown[]>('/v1/settings/groups'),
  types: () => http<unknown[]>('/v1/settings/types'),
  emailTemplates: () => http<unknown[]>('/v1/settings/email-templates'),
};

// ─── Audit ───────────────────────────────────────────────────────────────
export const audit = {
  list: (params: { session_id?: string; actor?: string; kind?: string; limit?: number } = {}) =>
    http<unknown[]>(`/v1/audit${_q(params as Record<string, string | number | undefined>)}`),
  corrections: (sessionId: string) =>
    http<unknown[]>(`/v1/audit/sessions/${encodeURIComponent(sessionId)}/corrections`),
};

// ─── GCS upload ──────────────────────────────────────────────────────────
export const gcs = {
  signedUrl: (sessionId: string, filename: string, role?: string) =>
    http<{ signed_url: string; gcs_uri: string; blob_name: string }>(
      '/v1/gcs/upload-url',
      { body: { session_id: sessionId, filename, role }, method: 'POST' },
    ),
  uploadComplete: (sessionId: string, files: Array<{ gcs_uri: string; role?: string; filename?: string; content_type?: string; size_bytes?: number; duration_sec?: number }>) =>
    http<{ session_id: string; accepted: string[] }>(
      '/v1/gcs/upload-complete',
      { body: { session_id: sessionId, files }, method: 'POST' },
    ),
};

// ─── Diagnostics ─────────────────────────────────────────────────────────
export const diag = {
  gcs: () => http('/v1/diag/gcs'),
  classifyRoute: () => http('/v1/diag/classify-route'),
  health: () => http<{ status: string; version: string; env: string }>('/v1/health'),
};

export type Api = typeof auth & typeof sessions; // ergonomic export
