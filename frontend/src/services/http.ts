/**
 * Thin fetch wrapper with JWT injection + error normalization.
 *
 * In production the Vue app is served by the FastAPI image at the same origin
 * as /v1/*, so the API base is the empty string (relative URLs).
 * In `npm run dev` Vite's proxy forwards /v1 to http://localhost:8000.
 * VITE_API_MODE=mock can short-circuit to mock fixtures (see services/api.ts).
 */

const API_BASE = ''; // same-origin in dev (Vite proxy) and prod (FastAPI mount)

export class ApiError extends Error {
  constructor(public status: number, public body: unknown, message?: string) {
    super(message ?? `API ${status}`);
    this.name = 'ApiError';
  }
}

const TOKEN_KEY = 'rounds_jwt_v1';

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

interface RequestOpts {
  method?: string;
  body?: unknown;
  formBody?: Record<string, string>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  /** When true, omit the Authorization header even if a token is stored. */
  anonymous?: boolean;
  /**
   * Per-request timeout in ms. Defaults to DEFAULT_TIMEOUT_MS. Pass 0 to
   * disable (e.g. long-running exports). On timeout the request is aborted
   * and the call rejects with ApiError(0, {code:'TIMEOUT'}).
   */
  timeoutMs?: number;
}

// Time-box every request. Without this, a hung backend — a Railway api
// restart / cold-start window, a dropped connection — leaves fetch pending
// forever, freezing any view that awaits it on a spinner until the user
// manually refreshes (the "login lands on a blank dashboard" report). A
// timeout converts an infinite hang into a normal rejection the caller's
// catch can handle (e.g. DashboardView renders empty instead of spinning).
const DEFAULT_TIMEOUT_MS = 20000;

export async function http<T = unknown>(path: string, opts: RequestOpts = {}): Promise<T> {
  const headers: Record<string, string> = { ...opts.headers };
  const token = opts.anonymous ? null : getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (opts.formBody) {
    body = new URLSearchParams(opts.formBody);
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
  } else if (opts.body !== undefined) {
    body = JSON.stringify(opts.body);
    headers['Content-Type'] = 'application/json';
  }

  // Abort on timeout; also chain the caller's signal so either can cancel.
  const controller = new AbortController();
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timer = timeoutMs > 0 ? setTimeout(() => controller.abort(), timeoutMs) : null;
  if (opts.signal) {
    if (opts.signal.aborted) controller.abort();
    else opts.signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      method: opts.method ?? (body ? 'POST' : 'GET'),
      headers,
      body,
      signal: controller.signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      // Caller-initiated abort → propagate as-is; our timeout → typed ApiError.
      if (opts.signal?.aborted) throw e;
      throw new ApiError(0, { code: 'TIMEOUT' }, `Request to ${path} timed out after ${timeoutMs}ms`);
    }
    // Network error: offline, DNS failure, connection refused/reset.
    throw new ApiError(0, { code: 'NETWORK_ERROR' }, e instanceof Error ? e.message : 'Network error');
  } finally {
    if (timer) clearTimeout(timer);
  }

  const isJson = resp.headers.get('content-type')?.includes('application/json');
  const payload = isJson ? await resp.json().catch(() => undefined) : await resp.text().catch(() => '');

  // Auto-unwrap MIC §9.1 envelope. Backend wraps every JSON response in
  // {success, data, error, meta} — frontend callers expect the raw `data`
  // payload as before parity-3. Detect the envelope by checking the exact
  // 4-key shape so we don't unwrap a response that legitimately happens to
  // contain a `data` field.
  const unwrapped = unwrapEnvelope(payload);

  if (!resp.ok) {
    if (resp.status === 401 && !opts.anonymous) {
      // JWT expired or revoked. Clear it so the next request prompts login.
      setToken(null);
      // Also redirect the CURRENT page to /login so the user doesn't sit on a
      // broken view watching toasts pile up. Hash-routed app → navigate via
      // location.hash. Guarded so the login form's own 401 (wrong password)
      // doesn't trigger a redirect loop.
      if (!window.location.hash.startsWith('#/login')) {
        window.location.replace('/#/login');
      }
    }
    throw new ApiError(resp.status, unwrapped);
  }
  return unwrapped as T;
}


function unwrapEnvelope(payload: unknown): unknown {
  if (
    payload &&
    typeof payload === 'object' &&
    !Array.isArray(payload) &&
    'success' in payload &&
    'data' in payload &&
    'error' in payload &&
    'meta' in payload
  ) {
    const env = payload as { success: boolean; data: unknown; error: unknown };
    // On error: surface the error.code/message via ApiError thrown above; but
    // here we still return the envelope's data field (null on error) so the
    // caller can inspect it if it gets through. The non-2xx path already
    // throws ApiError so most callers never see a null-data envelope.
    if (env.success === false && env.error) {
      // Propagate the error shape via the throw path (caller's response was
      // not ok). For 2xx-with-success=false (unusual), return null data.
      return env.data;
    }
    return env.data;
  }
  return payload;
}
