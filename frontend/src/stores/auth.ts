/**
 * Auth store — current user + login/logout.
 * JWT is persisted via services/http.ts setToken/getToken (localStorage).
 * Email is also persisted so the route guard passes synchronously on refresh
 * (no flash of /login while bootstrap awaits /v1/auth/me).
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { auth as authApi } from '@/services/api';
import { ApiError, getToken, setToken } from '@/services/http';

const EMAIL_KEY = 'rounds_user_email_v1';
function readPersistedEmail(): string | null {
  try { return localStorage.getItem(EMAIL_KEY); } catch { return null; }
}
function writePersistedEmail(v: string | null): void {
  try {
    if (v) localStorage.setItem(EMAIL_KEY, v);
    else localStorage.removeItem(EMAIL_KEY);
  } catch { /* private mode */ }
}

/** Read the `sub` (email) claim from a JWT without verifying. The server just
 * issued the token on a successful POST /login, so the login path can take the
 * email from here instead of a second GET /me round-trip — one less request to
 * hang on during a backend restart. bootstrap() still validates persisted
 * tokens via /me on app start. */
function jwtSub(token: string): string | null {
  try {
    const part = token.split('.')[1];
    if (!part) return null;
    const payload = JSON.parse(atob(part.replace(/-/g, '+').replace(/_/g, '/'))) as { sub?: string };
    return typeof payload.sub === 'string' ? payload.sub : null;
  } catch { return null; }
}

export const useAuthStore = defineStore('auth', () => {
  const email = ref<string | null>(readPersistedEmail());
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  const isAuthenticated = computed(() => Boolean(email.value && getToken()));

  async function bootstrap(): Promise<void> {
    if (!getToken()) return;
    try {
      const me = await authApi.me();
      email.value = me.email;
      writePersistedEmail(me.email);
    } catch (e) {
      // Token bad — clear it
      setToken(null);
      email.value = null;
      writePersistedEmail(null);
    }
  }

  async function login(emailInput: string, password: string): Promise<boolean> {
    isLoading.value = true;
    error.value = null;
    try {
      const resp = await authApi.login(emailInput.trim().toLowerCase(), password);
      setToken(resp.access_token);
      // Take the email from the JWT the server just issued — no redundant
      // GET /me on the login hot path (removes a request that could hang
      // during a backend restart and freeze the post-login redirect).
      const who = jwtSub(resp.access_token) ?? emailInput.trim().toLowerCase();
      email.value = who;
      writePersistedEmail(who);
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        error.value = 'Incorrect email or password';
      } else {
        error.value = e instanceof Error ? e.message : 'Login failed';
      }
      return false;
    } finally {
      isLoading.value = false;
    }
  }

  function logout(): void {
    setToken(null);
    email.value = null;
    writePersistedEmail(null);
  }

  return { email, isLoading, error, isAuthenticated, bootstrap, login, logout };
});
