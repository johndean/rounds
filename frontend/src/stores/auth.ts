/**
 * Auth store — current user + login/logout.
 * JWT is persisted via services/http.ts setToken/getToken (localStorage).
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { auth as authApi } from '@/services/api';
import { ApiError, getToken, setToken } from '@/services/http';

export const useAuthStore = defineStore('auth', () => {
  const email = ref<string | null>(null);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  const isAuthenticated = computed(() => Boolean(email.value && getToken()));

  async function bootstrap(): Promise<void> {
    if (!getToken()) return;
    try {
      const me = await authApi.me();
      email.value = me.email;
    } catch (e) {
      // Token bad — clear it
      setToken(null);
      email.value = null;
    }
  }

  async function login(emailInput: string, password: string): Promise<boolean> {
    isLoading.value = true;
    error.value = null;
    try {
      const resp = await authApi.login(emailInput.trim().toLowerCase(), password);
      setToken(resp.access_token);
      const me = await authApi.me();
      email.value = me.email;
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
  }

  return { email, isLoading, error, isAuthenticated, bootstrap, login, logout };
});
