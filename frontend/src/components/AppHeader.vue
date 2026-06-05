<script setup lang="ts">
/**
 * App header — faithful port of components.jsx::AppHeader.
 * Same class names (.app-header, __brand, __divider, __product, __build,
 * __nav, __tools, __icon-btn, __status, __user, __avatar) from app.css.
 * Mock Kate Schultz replaced with live auth.email; ⌘K wired through commandPalette.
 */
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import Icon from '@/components/shared/Icon.vue';
import { commandPalette } from '@/composables/useCommandPalette';
import { toast } from '@/composables/useToast';
import { useAuthStore } from '@/stores/auth';
import { useHelpCenterStore } from '@/stores/helpCenter';
import { useUiStore } from '@/stores/ui';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const help = useHelpCenterStore();
const ui = useUiStore();

// Bundle's bake-time SHA — injected by Dockerfile ARG RAILWAY_GIT_COMMIT_SHA
// → VITE_BUILD_SHA in the frontend-build stage. 'dev' for local builds without
// Railway env. Stays constant for the life of this bundle in the browser.
const bundleSha = ((import.meta as unknown as { env: { VITE_BUILD_SHA?: string } }).env.VITE_BUILD_SHA || 'dev');
const bundleShort = bundleSha === 'dev' ? 'dev' : bundleSha.slice(0, 7);

// Api's runtime SHA — fetched on mount from /v1/version (the unauthenticated
// build-identity endpoint added at the same time as this chip). When the api
// commit differs from the bundle, the user is looking at a cached frontend
// older than the live deploy → show an amber refresh prompt.
const apiSha = ref<string>('');
const apiShaShort = computed(() => apiSha.value.slice(0, 7));
const versionMismatch = computed(() =>
  apiSha.value !== '' && bundleSha !== 'dev' && apiShaShort.value !== bundleShort,
);

onMounted(async () => {
  try {
    // Plain fetch — /v1/version is unauthenticated, no need for the http() wrapper.
    const r = await fetch('/v1/version');
    if (!r.ok) return;
    const data = await r.json().catch(() => null) as { commit?: string } | null;
    apiSha.value = data?.commit || '';
  } catch {
    /* silent — version chip is non-essential */
  }
});

async function copyBuildInfo(): Promise<void> {
  const info = `bundle=${bundleShort} api=${apiShaShort.value || 'unknown'}`;
  try {
    await navigator.clipboard.writeText(info);
    toast.push(`Copied: ${info}`, { tone: 'info' });
  } catch {
    toast.push(info, { tone: 'info' });
  }
}

async function reloadForLatest(): Promise<void> {
  // Force-bust the cache so the new index.html + bundle SHA come through.
  window.location.reload();
}

function isActive(prefixes: string[]): boolean {
  return prefixes.some(p => route.path.startsWith(p));
}

const userName = computed(() => {
  if (!auth.email) return 'Guest';
  // Convert kate.schultz@vin.com → Kate Schultz
  const handle = auth.email.split('@')[0] ?? '';
  return handle.split(/[._-]/).map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' ');
});
const userInitials = computed(() => {
  if (!auth.email) return '?';
  const handle = auth.email.split('@')[0] ?? '';
  const parts = handle.split(/[._-]/);
  if (parts.length >= 2) return (parts[0]!.charAt(0) + parts[1]!.charAt(0)).toUpperCase();
  return handle.slice(0, 2).toUpperCase();
});

function onSearch(): void { commandPalette.open(); }
function fontDelta(delta: number): void {
  const root = document.documentElement;
  const current = parseFloat(getComputedStyle(root).fontSize) || 16;
  root.style.fontSize = Math.max(12, Math.min(20, current + delta)) + 'px';
  toast.push(`Font size ${delta > 0 ? '+' : ''}${delta}`, { tone: 'info' });
}
function onLogout(): void {
  auth.logout();
  toast.push('Signed out', { tone: 'success' });
  router.push('/login');
}

void ui;  // silence unused
</script>

<template>
  <header class="app-header" data-screen-label="App Header">
    <RouterLink to="/sessions" class="app-header__brand" aria-label="transcript.software home">
      <img src="/assets/VIN-light.svg" alt="VIN" />
      <span class="app-header__divider" />
      <span class="app-header__product">transcript<strong>.software</strong></span>
    </RouterLink>
    <span
      class="app-header__build"
      :title="`Bundle: ${bundleSha}\nApi: ${apiSha || 'unknown'}\nClick to copy`"
      :style="{ cursor: 'pointer', fontFamily: 'var(--font-mono)' }"
      @click="copyBuildInfo"
    >{{ bundleShort }}</span>
    <button
      v-if="versionMismatch"
      class="app-header__build"
      :style="{
        background: 'rgba(217, 119, 6, 0.18)',
        color: 'var(--color-amber)',
        border: '1px solid rgba(217, 119, 6, 0.55)',
        borderRadius: '999px',
        padding: '2px 10px',
        marginLeft: '6px',
        cursor: 'pointer',
        fontFamily: 'var(--font-mono)',
        fontSize: '11px',
        fontWeight: 700,
      }"
      :title="`API is on ${apiSha} but your bundle is ${bundleSha}. Click to hard-reload.`"
      @click="reloadForLatest"
    >⟳ reload for {{ apiShaShort }}</button>

    <nav class="app-header__nav" aria-label="Primary">
      <RouterLink to="/dashboard"     :class="{ 'is-active': isActive(['/dashboard']) }">Dashboard</RouterLink>
      <RouterLink to="/sessions"      :class="{ 'is-active': isActive(['/sessions', '/s/', '/v/', '/e/', '/p/']) }">Sessions</RouterLink>
      <RouterLink to="/upload"        :class="{ 'is-active': isActive(['/upload']) }">Upload</RouterLink>
      <RouterLink to="/improvements"  :class="{ 'is-active': isActive(['/improvements']) }">Improvements</RouterLink>
      <RouterLink to="/settings"      :class="{ 'is-active': isActive(['/settings', '/audit', '/gcs']) }">Settings</RouterLink>
    </nav>

    <div class="app-header__tools" aria-label="Quick tools">
      <button class="app-header__icon-btn" title="Search routes (⌘K)" aria-label="Search" data-test-id="topbar-search" @click="onSearch">
        <Icon name="search" :size="14" />
      </button>
      <span class="app-header__divider" />
      <button class="app-header__icon-btn app-header__icon-btn--mono" title="Decrease font size" aria-label="Decrease font size" data-test-id="topbar-font-decrease" @click="fontDelta(-1)">A−</button>
      <button class="app-header__icon-btn app-header__icon-btn--mono" title="Increase font size" aria-label="Increase font size" data-test-id="topbar-font-increase" @click="fontDelta(1)">A+</button>
      <span class="app-header__divider" />
      <button class="app-header__icon-btn app-header__icon-btn--mono" title="Open Help" aria-label="Open help center" data-test-id="topbar-help" @click="help.toggle">?</button>
    </div>

    <div class="app-header__user" :title="auth.email ? `Logged in as ${userName}` : 'Not signed in'">
      <span class="app-header__avatar">{{ userInitials }}</span>
      <span style="margin-right: 4px;">{{ userName }}</span>
      <button
        v-if="auth.isAuthenticated"
        class="app-header__icon-btn app-header__icon-btn--mono"
        title="Logout"
        data-test-id="topbar-logout"
        style="margin-left: 8px;"
        @click="onLogout"
      >Logout</button>
    </div>
  </header>
</template>
