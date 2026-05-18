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

export interface PipelineConfig {
  ai_pipeline: 'direct' | 'enhanced';
  ai_mode: string;
  ai_model: string;
  prompt_mode: string;
  custom_prompt?: string | null;
  stt_backend: string;
  template_id: string;
  iil_config: { enabled: boolean; tier1: boolean; tier2: boolean; tier3: boolean };
}

export interface SessionFailureReason {
  session_id: string;
  code: string;
  title: string;
  status: string;
  reason: string | null;
  category: string | null;
  ts: string | null;
  actor: string | null;
  log_tail: Array<Record<string, unknown>>;
}

export interface DeletedSessionRow {
  session_id: string;
  code: string;
  title: string;
  presenter: string | null;
  status: string;
  created_at: string | null;
  deleted_at: string | null;
}

export const sessions = {
  list: (filters: SessionFilters = {}) =>
    http<SessionSummary[]>(`/v1/sessions${_q({ ...filters })}`),
  get: (id: string) =>
    http<SessionSummary>(`/v1/sessions/${encodeURIComponent(id)}`),
  create: (payload: { code: string; title: string; presenter?: string; duration_sec?: number | null; attendee_count?: number | null; taxonomy?: string[]; pipeline_config?: PipelineConfig }) =>
    http<SessionSummary>('/v1/sessions', { body: payload, method: 'POST' }),
  remove: (id: string) =>
    http<{ session_id: string; deleted: boolean }>(`/v1/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  listDeleted: () =>
    http<DeletedSessionRow[]>('/v1/sessions/deleted'),
  restore: (id: string) =>
    http<{ session_id: string; restored: boolean }>(`/v1/sessions/${encodeURIComponent(id)}/restore`, { method: 'POST' }),
  permanentDelete: (id: string) =>
    http<{ session_id: string; permanently_deleted: boolean }>(`/v1/sessions/${encodeURIComponent(id)}/permanent`, { method: 'DELETE' }),
  failureReason: (id: string) =>
    http<SessionFailureReason>(`/v1/sessions/${encodeURIComponent(id)}/failure-reason`),
  pipelineConfig: (id: string) =>
    http<PipelineConfig & { auto_detected_template_id: string | null; auto_detected_confidence: number | null }>(
      `/v1/sessions/${encodeURIComponent(id)}/pipeline-config`,
    ),
  retry: (id: string) =>
    http<{ session_id: string; status_before: string; enqueued: boolean; detail?: string }>(
      `/v1/diag/reingest/${encodeURIComponent(id)}`,
      { method: 'POST' },
    ),
  // Session-files panel (MIC add_to_session.py port)
  missing: (id: string) =>
    http<{ has_slides: boolean; has_chat: boolean; has_manifest: boolean; has_bios: boolean }>(
      `/v1/sessions/${encodeURIComponent(id)}/missing`,
    ),
  addSignedUrl: (id: string, body: { filename: string; mime_type: string; type: 'slides' | 'chat' | 'manifest' }) =>
    http<{ signed_url: string; gcs_uri: string; blob_name: string; mime_type: string; expires_in: number }>(
      `/v1/sessions/${encodeURIComponent(id)}/add/signed-url`,
      { body, method: 'POST' },
    ),
  addSlides: (id: string, body: { gcs_uri: string; slide_numbers?: number[] }, mode?: 'replace' | 'append' | 'replace_selected') =>
    http(`/v1/sessions/${encodeURIComponent(id)}/add/slides${mode ? `?mode=${mode}` : ''}`, { body, method: 'POST' }),
  addChat: (id: string, body: { gcs_uri: string }, opts: { confirm?: boolean; start_time?: string } = {}) => {
    const qs = new URLSearchParams();
    if (opts.confirm) qs.set('confirm', 'true');
    if (opts.start_time) qs.set('start_time', opts.start_time);
    const q = qs.toString();
    return http(`/v1/sessions/${encodeURIComponent(id)}/add/chat${q ? `?${q}` : ''}`, { body, method: 'POST' });
  },
  addManifest: (id: string, body: { gcs_uri: string }, mode?: 'use_new' | 'keep_current') =>
    http(`/v1/sessions/${encodeURIComponent(id)}/add/manifest${mode ? `?mode=${mode}` : ''}`, { body, method: 'POST' }),
  // Phase 10.1 — caption burn-in to MP4
  burnCaptions: (id: string, styleConfig?: Record<string, unknown>) =>
    http<{ enqueued: boolean; session_id: string }>(
      `/v1/sessions/${encodeURIComponent(id)}/captions/burn`,
      { body: { style_config: styleConfig || null }, method: 'POST' },
    ),
  captionedVideo: (id: string) =>
    http<{
      artifact_id: string; gcs_uri: string; download_url: string | null;
      bytes: number | null; version: number; is_current: boolean;
      generated_at: string | null; style_config: Record<string, unknown> | null;
    } | null>(`/v1/sessions/${encodeURIComponent(id)}/captioned-video`),
};

// ─── Speakers (Phase 9 — per-session speaker CRUD + bulk segment reassign) ──
export interface SessionSpeaker {
  id: string;
  short: string | null;
  name: string | null;
  role: string | null;
  avatar_color?: string | null;
}

export const speakers = {
  list: (sessionId: string) =>
    http<SessionSpeaker[]>(`/v1/sessions/${encodeURIComponent(sessionId)}/speakers`),
  add: (sessionId: string, body: { name: string; role?: string; avatar_color?: string }) =>
    http<SessionSpeaker>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/speakers`,
      { body, method: 'POST' },
    ),
  edit: (sessionId: string, speakerId: string, body: { name?: string; role?: string; avatar_color?: string }) =>
    http<SessionSpeaker>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/speakers/${encodeURIComponent(speakerId)}`,
      { body, method: 'PATCH' },
    ),
  remove: (sessionId: string, speakerId: string) =>
    http<void>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/speakers/${encodeURIComponent(speakerId)}`,
      { method: 'DELETE' },
    ),
  reassignSegment: (sessionId: string, segmentId: string, speakerId: string) =>
    http<SessionSpeaker>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/segments/${encodeURIComponent(segmentId)}/speaker-reassign`,
      { body: { speaker_id: speakerId }, method: 'POST' },
    ),
};


// ─── Corrections (Phase 4 — append-only ledger with undo/redo pointer) ──
export interface CorrectionRow {
  correction_id: string;
  sequence_number: number;
  action_id: string;
  segment_id: string;
  correction_type:
    | 'slide_reassignment' | 'text_edit' | 'split' | 'merge' | 'mark_ok'
    | 'chat_insert' | 'chat_edit' | 'chat_remove'
    | 'poll_insert' | 'poll_remove'
    | 'speaker_reassignment';
  old_slide_id: string | null;
  new_slide_id: string | null;
  old_text: string | null;
  new_text: string | null;
  applied_at: string | null;
  applied_by: string;
  active: boolean;
}

export interface CorrectionApplied {
  correction_id: string;
  sequence_number: number;
  action_id: string;
  segment_id: string;
  correction_type: CorrectionRow['correction_type'];
  old_slide_id: string | null;
  new_slide_id: string | null;
  old_text: string | null;
  new_text: string | null;
  applied_at: string | null;
  applied_by: string;
  resolved_discrepancy_id: string | null;
}

export interface FindReplaceResult {
  session_id: string;
  find: string;
  replace: string;
  case_sensitive: boolean;
  matches: Array<{ segment_id: string; old_text: string; new_text: string; match_count: number }>;
  total_matches: number;
  segment_count: number;
  applied: boolean;
  action_id: string | null;
  corrections: CorrectionApplied[];
}

export const corrections = {
  apply: (
    sessionId: string,
    body: {
      segment_id: string;
      correction_type: CorrectionRow['correction_type'];
      old_slide_id?: string | null;
      new_slide_id?: string | null;
      old_text?: string | null;
      new_text?: string | null;
      action_id?: string | null;
    },
  ) =>
    http<CorrectionApplied>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/corrections`,
      { body, method: 'POST' },
    ),
  list: (sessionId: string) =>
    http<{ session_id: string; current_pointer: number; corrections: CorrectionRow[] }>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/corrections`,
    ),
  undo: (sessionId: string) =>
    http<{ session_id: string; pointer: number; action?: string }>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/corrections/undo`,
      { method: 'POST' },
    ),
  redo: (sessionId: string) =>
    http<{ session_id: string; pointer: number; action?: string }>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/corrections/redo`,
      { method: 'POST' },
    ),
  findReplace: (
    sessionId: string,
    body: { find: string; replace: string; case_sensitive?: boolean; dry_run?: boolean },
  ) =>
    http<FindReplaceResult>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/find-replace`,
      { body, method: 'POST' },
    ),
  reviewQueue: (sessionId: string) =>
    http<{
      session_id: string;
      count: number;
      items: Array<{
        segment_id: string; alignment_id: string; status: string;
        confidence: number | null; drift_flag: boolean; uncertain_flag: boolean;
        slide_id: string | null; priority_score: number;
      }>;
    }>(`/v1/sessions/${encodeURIComponent(sessionId)}/review-queue`),
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
  // Phase 6 — stage owner reassignment + annotations (note / override / blocker)
  assign: (sessionId: string, assignee: string, opts: { stage?: string; note?: string } = {}) =>
    http<{ session_id: string; stage: string; assignee: string; prev: unknown }>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/sop/assign`,
      { body: { assignee, stage: opts.stage, note: opts.note }, method: 'POST' },
    ),
  annotate: (sessionId: string, body: string, opts: { stage?: string; kind?: 'note' | 'override' | 'blocker' } = {}) =>
    http<{
      session_id: string; stage: string; kind: string;
      annotation: { stage: string; kind: string; body: string; actor_email: string; inserted_at: string };
      total_count: number;
    }>(
      `/v1/sessions/${encodeURIComponent(sessionId)}/sop/annotations`,
      { body: { body, stage: opts.stage, kind: opts.kind || 'note' }, method: 'PATCH' },
    ),
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
export interface SettingsPerson {
  id: string; email: string; name: string;
  role?: string | null; avatar_color?: string | null; is_active?: boolean;
}
export interface SettingsGroup {
  id: string; name: string; description?: string | null;
}
export interface SettingsType {
  id: string; code: string; label: string;
}

export const settingsApi = {
  list: () => http<Record<string, unknown>>('/v1/settings'),
  set: (key: string, value: unknown) =>
    http(`/v1/settings/${encodeURIComponent(key)}`, { body: { key, value }, method: 'PUT' }),
  people: () => http<SettingsPerson[]>('/v1/settings/people'),
  peopleAdd: (payload: { email: string; name: string; role?: string; avatar_color?: string }) =>
    http<SettingsPerson>('/v1/settings/people', { body: payload, method: 'POST' }),
  peopleRemove: (id: string) =>
    http(`/v1/settings/people/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  groups: () => http<SettingsGroup[]>('/v1/settings/groups'),
  groupsAdd: (payload: { name: string; description?: string }) =>
    http<SettingsGroup>('/v1/settings/groups', { body: payload, method: 'POST' }),
  types: () => http<SettingsType[]>('/v1/settings/types'),
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

// ─── Email diagnostics (Phase 7 — admin-only SMTP probe + test send + log) ──
export interface SmtpConfigCheck {
  host:         { present: boolean; value: string | null };
  port:         { present: boolean; value: string | null };
  from_address: { present: boolean; value: string | null };
  username:     { present: boolean; value: null };
  password:     { present: boolean; value: null };
}

export interface SmtpConnectivityStep {
  ok: boolean | null;
  latency_ms: number | null;
  error: string | null;
}

export interface SmtpConnectivityResult {
  connect: SmtpConnectivityStep;
  starttls: SmtpConnectivityStep;
  login: SmtpConnectivityStep;
  noop: SmtpConnectivityStep;
  quit: SmtpConnectivityStep;
}

export interface SmtpSendResult {
  sent: boolean;
  to: string;
  subject: string;
  latency_ms: number;
  error: string | null;
  smtp_log: string;
}

export interface EmailAttemptRow {
  id: string;
  attempted_at: string | null;
  from_address: string;
  to_address: string;
  subject: string | null;
  trigger: string;
  sop_session_id: string | null;
  stage: string | null;
  result: 'sent' | 'failed';
  error_code: string | null;
  error_message: string | null;
  latency_ms: number | null;
  smtp_log: string | null;
  operator_email: string | null;
}

export const emailDebug = {
  config: () => http<SmtpConfigCheck>('/v1/admin/email-debug/config'),
  connectivity: () => http<SmtpConnectivityResult>('/v1/admin/email-debug/connectivity', { method: 'POST' }),
  send: (body: { to: string; subject?: string; text_body?: string; html_body?: string }) =>
    http<SmtpSendResult>('/v1/admin/email-debug/send', { body, method: 'POST' }),
  attempts: (params: { limit?: number; to?: string; result?: 'sent' | 'failed'; since_hours?: number } = {}) =>
    http<EmailAttemptRow[]>(`/v1/admin/email-debug/attempts${_q(params as Record<string, string | number | undefined>)}`),
};


// ─── Diagnostics ─────────────────────────────────────────────────────────
export interface ClearSlotsResult {
  email: string;
  removed_count: number;
  removed_session_ids: string[];
  cap: number;
  remaining: number;
}

export const diag = {
  gcs: () => http('/v1/diag/gcs'),
  classifyRoute: () => http('/v1/diag/classify-route'),
  health: () => http<{ status: string; version: string; env: string }>('/v1/health'),
  clearRateLimitSlots: () =>
    http<ClearSlotsResult>('/v1/diag/clear-rate-limit-slots', { method: 'POST' }),
};

export type Api = typeof auth & typeof sessions; // ergonomic export
