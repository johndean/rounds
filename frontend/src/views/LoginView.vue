<script setup lang="ts">
/**
 * Login screen. Per memory feedback_cevin_internal_design.md:
 *   "internal app pages follow MIC's dark-topbar + sans-serif pattern,
 *    not Login's Instrument Serif aesthetic"
 * So Login uses Instrument Serif (--font-display), internal pages use ProximaNova.
 */
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const router = useRouter();

const email = ref('');
const password = ref('');

async function submit(): Promise<void> {
  const ok = await auth.login(email.value, password.value);
  if (ok) {
    const target = (router.currentRoute.value.query.next as string) || '/dashboard';
    router.replace(target);
  }
}
</script>

<template>
  <div class="login-shell">
    <form class="login-card" @submit.prevent="submit" data-test-id="login-form">
      <h1 class="login-title">Rounds</h1>
      <p class="login-lead">Sign in to continue</p>

      <label class="login-field">
        <span>Email</span>
        <input
          v-model.trim="email"
          type="email"
          autocomplete="username"
          required
          autofocus
          data-test-id="login-email"
        />
      </label>

      <label class="login-field">
        <span>Password</span>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          data-test-id="login-password"
        />
      </label>

      <p v-if="auth.error" class="login-error" data-test-id="login-error">{{ auth.error }}</p>

      <button
        type="submit"
        class="btn btn--primary login-submit"
        :disabled="auth.isLoading || !email || !password"
        data-test-id="login-submit"
      >
        {{ auth.isLoading ? 'Signing in…' : 'Sign in' }}
      </button>

      <p class="login-foot">
        <span class="mono">rounds.vin</span> · <span>v0.0.1</span>
      </p>
    </form>
  </div>
</template>

<style scoped>
.login-shell {
  min-height: calc(100vh - 50px);
  display: grid;
  place-items: center;
  background: linear-gradient(180deg, var(--surface-bg) 0%, var(--surface-muted) 100%);
  padding: var(--space-5);
}
.login-card {
  background: var(--surface-card);
  padding: var(--space-7) var(--space-7);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  width: 100%;
  max-width: 420px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.login-title {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 400;
  font-size: var(--fs-3xl);
  color: var(--color-navy);
  letter-spacing: 0.01em;
}
.login-lead { margin: 0 0 var(--space-4); color: var(--fg2); font-size: var(--fs-md); }
.login-field { display: flex; flex-direction: column; gap: var(--space-1); }
.login-field span {
  font-size: var(--fs-xs);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
  color: var(--fg2);
}
.login-field input {
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  font-family: var(--font-family);
  font-size: var(--fs-sm);
  background: var(--surface-card);
  color: var(--fg1);
}
.login-field input:focus {
  outline: none;
  border-color: var(--color-blue);
  box-shadow: 0 0 0 3px rgba(8, 97, 206, 0.18);
}
.login-error {
  margin: 0;
  padding: var(--space-3);
  background: rgba(197, 70, 68, 0.08);
  border-left: 3px solid var(--color-red);
  color: var(--color-red);
  font-size: var(--fs-xs);
  border-radius: var(--radius-sm);
}
.login-submit { padding: var(--space-3); font-size: var(--fs-md); justify-content: center; }
.login-submit:disabled { opacity: 0.55; cursor: not-allowed; }
.login-foot {
  margin: 0;
  text-align: center;
  color: var(--fg2);
  font-size: var(--fs-2xs);
  opacity: 0.7;
}
</style>
