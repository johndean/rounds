<script setup lang="ts">
/**
 * Login route — /login
 * Pixel-by-pixel Vue port of tmp/port-source/login.jsx (87 lines).
 * Same class names, same data-test-ids, same DOM tree.
 * Mock signIn replaced with real authStore.login → POST /v1/auth/login.
 */
import { ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/composables/useToast';

// Bundle's bake-time SHA — same source as AppHeader. Injected by Dockerfile
// ARG RAILWAY_GIT_COMMIT_SHA → VITE_BUILD_SHA. 'dev' for local builds.
const bundleSha = ((import.meta as unknown as { env: { VITE_BUILD_SHA?: string } }).env.VITE_BUILD_SHA || 'dev');
const bundleShort = bundleSha === 'dev' ? 'dev' : bundleSha.slice(0, 7);

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const email = ref('');
const pw = ref('');
const busy = ref(false);

async function signIn(e?: Event): Promise<void> {
  e?.preventDefault();
  if (!email.value || !pw.value) {
    toast.push('Email and password required', { tone: 'warn' });
    return;
  }
  busy.value = true;
  const ok = await auth.login(email.value, pw.value);
  busy.value = false;
  if (!ok) {
    toast.push(auth.error ?? 'Sign in failed', { tone: 'error' });
    return;
  }
  toast.push(`Welcome back, ${email.value.split('@')[0]}`, { tone: 'success' });
  const target = (route.query.next as string) || '/dashboard';
  router.replace(target);
}

</script>

<template>
  <main class="login" data-screen-label="Login">
    <div class="login__bg" aria-hidden="true" />
    <form class="login__card" @submit="signIn">
      <div class="login__brand">
        <img src="/assets/VIN.svg" alt="VIN" />
        <div class="login__brand-text">
          <div class="login__brand-name">TRANSCRIPT<strong>.SOFTWARE</strong></div>
          <div class="login__brand-sub">VIN Transcript Operations Console</div>
        </div>
      </div>

      <h1 class="login__title">Sign in</h1>
      <span class="login__pill" :title="`Build ${bundleSha}`">{{ bundleShort }} · OPERATOR CONSOLE</span>
      <p class="login__lead">
        Audit-traceable transcription workflow for VIN continuing-education sessions · SOP-gated review · append-only correction lineage.
      </p>

      <label class="login__label">
        Email
        <input
          v-model="email"
          type="email"
          class="login__input"
          placeholder="you@vin.com"
          autofocus
          data-test-id="login-email"
        />
      </label>

      <label class="login__label">
        Password
        <input
          v-model="pw"
          type="password"
          class="login__input"
          placeholder="••••••••••••"
          data-test-id="login-password"
        />
      </label>

      <div class="login__row">
        <label class="login__remember">
          <input type="checkbox" checked /> Keep me signed in for 8 hours
        </label>
      </div>

      <button type="submit" class="login__submit" :disabled="busy" data-test-id="login-submit">
        {{ busy ? 'Signing in…' : 'Sign in' }}
      </button>

      <div class="login__foot">
        <span :title="`Bundle: ${bundleSha}`">Build <code>{{ bundleShort }}</code></span>
      </div>
    </form>
  </main>
</template>
