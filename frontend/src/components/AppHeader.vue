<script setup lang="ts">
/**
 * AppHeader — IMPLEMENTATION.md §3 TopBar.
 *   Navy (#002855) sticky band, 50px tall.
 *   Brand · build pill · 5 nav links · ⌘K search · A−/A+ font · status pill · avatar · Logout.
 *
 * SCAFFOLD: minimal layout to verify Phase 1 wiring. Pixel parity comes in Phase 2 / U8.
 */
import { computed } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { toast } from '@/composables/useToast';
import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const buildId = computed(() => 'v0.0.1-rounds');

const navLinks = [
  { to: '/dashboard',     label: 'Dashboard' },
  { to: '/sessions',      label: 'Sessions' },
  { to: '/upload',        label: 'Upload' },
  { to: '/improvements',  label: 'Improvements' },
  { to: '/settings',      label: 'Settings' },
];

const avatarInitials = computed(() => {
  if (!auth.email) return '?';
  return auth.email.slice(0, 2).toUpperCase();
});

function onSearch()   { toast.push('Command palette: not yet wired (Phase 2 / U9)', { tone: 'info' }); }
function onFontDown() { toast.push('Font down: not yet wired (Phase 2 / U8)', { tone: 'info' }); }
function onFontUp()   { toast.push('Font up: not yet wired (Phase 2 / U8)', { tone: 'info' }); }
function onLogout() {
  auth.logout();
  toast.push('Signed out', { tone: 'success' });
  router.push('/login');
}
</script>

<template>
  <header class="app-header" data-test-id="app-header">
    <div class="app-header__brand">
      <span>VIN</span>
      <span class="mono uppercase">ROUNDS</span>
      <span class="app-header__build-pill mono">{{ buildId }}</span>
    </div>

    <nav class="app-header__nav">
      <RouterLink
        v-for="link in navLinks"
        :key="link.to"
        :to="link.to"
        :class="{ 'is-active': route.path.startsWith(link.to) }"
      >{{ link.label }}</RouterLink>
    </nav>

    <div class="app-header__right">
      <button class="btn" data-test-id="topbar-search" @click="onSearch">⌘K Search</button>
      <button class="btn" data-test-id="topbar-font-down" @click="onFontDown" aria-label="Decrease font size">A−</button>
      <button class="btn" data-test-id="topbar-font-up"   @click="onFontUp"   aria-label="Increase font size">A+</button>
      <span class="chip mono">nominal</span>
      <span v-if="auth.email" class="app-header__avatar" :title="auth.email">{{ avatarInitials }}</span>
      <button v-if="auth.isAuthenticated" class="btn" data-test-id="topbar-logout" @click="onLogout">Logout</button>
    </div>
  </header>
</template>

<style scoped>
.app-header__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-gold);
  color: var(--color-navy);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: var(--fw-extrabold);
  text-transform: uppercase;
}
</style>
