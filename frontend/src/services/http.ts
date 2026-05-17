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
}

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

  const resp = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? (body ? 'POST' : 'GET'),
    headers,
    body,
    signal: opts.signal,
  });

  const isJson = resp.headers.get('content-type')?.includes('application/json');
  const payload = isJson ? await resp.json().catch(() => undefined) : await resp.text().catch(() => '');

  if (!resp.ok) {
    if (resp.status === 401 && !opts.anonymous) {
      // JWT expired or revoked. Clear it so the next request prompts login.
      setToken(null);
    }
    throw new ApiError(resp.status, payload);
  }
  return payload as T;
}
