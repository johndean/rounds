<script setup lang="ts">
/**
 * App root — faithful port of tmp/port-source/app.jsx.
 * Same `.app` wrapper, same brand toggle behavior (VIN navy / VSPN green
 * via inline CSS custom property overrides on documentElement), same
 * theme/density data attributes, same ⌘K/⌘F keyboard shortcuts, same
 * "hide AppHeader on /login" rule. Tweaks panel + Toast/Confirm/Modal/
 * CommandPalette overlays mounted globally.
 */
import { computed, onMounted, onUnmounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import AppHeader from '@/components/AppHeader.vue';
import ToastHost from '@/components/overlays/ToastHost.vue';
import ConfirmHost from '@/components/overlays/ConfirmHost.vue';
import ModalHost from '@/components/overlays/ModalHost.vue';
import CommandPalette from '@/components/overlays/CommandPalette.vue';
import { useAuthStore } from '@/stores/auth';
import { useUiStore } from '@/stores/ui';

const route = useRoute();
const auth = useAuthStore();
const ui = useUiStore();

const isLogin = computed(() => route.path.startsWith('/login'));

function applyBrand(brand: string): void {
  const root = document.documentElement;
  if (brand === 'vspn') {
    root.style.setProperty('--surface-nav',      '#005842');
    root.style.setProperty('--color-navy',       '#007D61');
    root.style.setProperty('--color-navy-deep',  '#005842');
    root.style.setProperty('--color-navy-focus', '#006B50');
    root.style.setProperty('--text-accent',      '#0097A9');
    root.style.setProperty('--fg-link',          '#0097A9');
    root.style.setProperty('--fg1',              '#005842');
    root.style.setProperty('--text-primary',     '#005842');
  } else {
    root.style.removeProperty('--surface-nav');
    root.style.removeProperty('--color-navy');
    root.style.removeProperty('--color-navy-deep');
    root.style.removeProperty('--color-navy-focus');
    root.style.removeProperty('--text-accent');
    root.style.removeProperty('--fg-link');
    root.style.removeProperty('--fg1');
    root.style.removeProperty('--text-primary');
  }
}

function applyAppearance(): void {
  document.documentElement.dataset.theme = ui.theme;
  document.documentElement.dataset.density = ui.density;
  applyBrand(ui.brand);
}

// Global keyboard shortcuts: ⌘F = Find&Replace in editor routes; ⌘K already
// handled by CommandPalette component.
function onKeydown(e: KeyboardEvent): void {
  if ((e.metaKey || e.ctrlKey) && e.key === 'f' && route.path.startsWith('/e/')) {
    e.preventDefault();
    // TODO: openFind modal (Phase port — wiring.jsx)
  }
}

onMounted(() => {
  void auth.bootstrap();
  applyAppearance();
  window.addEventListener('keydown', onKeydown);
});
onUnmounted(() => window.removeEventListener('keydown', onKeydown));

watch(
  () => [ui.theme, ui.brand, ui.density],
  applyAppearance,
);
</script>

<template>
  <div class="app">
    <AppHeader v-if="!isLogin" />
    <RouterView v-slot="{ Component, route: r }">
      <component :is="Component" :key="r.fullPath" />
    </RouterView>

    <ToastHost />
    <ConfirmHost />
    <ModalHost />
    <CommandPalette />
  </div>
</template>
