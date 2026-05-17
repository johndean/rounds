<script setup lang="ts">
/**
 * App header — faithful port of components.jsx::AppHeader.
 * Same class names (.app-header, __brand, __divider, __product, __build,
 * __nav, __tools, __icon-btn, __status, __user, __avatar) from app.css.
 * Mock Kate Schultz replaced with live auth.email; ⌘K wired through commandPalette.
 */
import { computed } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import Icon from '@/components/shared/Icon.vue';
import { commandPalette } from '@/composables/useCommandPalette';
import { toast } from '@/composables/useToast';
import { useAuthStore } from '@/stores/auth';
import { useUiStore } from '@/stores/ui';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

const build = 'v4.0.0-ssot-r2';

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
    <span class="app-header__build" :title="`Build ${build}`">{{ build }}</span>

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
      <span class="app-header__status" title="System status: nominal">
        <span class="dot" /> nominal
      </span>
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
