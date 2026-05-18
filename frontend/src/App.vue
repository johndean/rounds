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
import TweaksPanel from '@/components/TweaksPanel.vue';
import { useAuthStore } from '@/stores/auth';
import { useUiStore } from '@/stores/ui';
import { useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

const QUICK_NAV = [
  { label: 'Dashboard',                to: '/dashboard' },
  { label: 'Sessions list',            to: '/sessions' },
  { label: 'Upload',                   to: '/upload' },
  { label: 'Session detail',           to: '/s/se_001' },
  { label: 'Editor (Copy edit draft)', to: '/e/se_001' },
  { label: 'SOP workflow',             to: '/e/se_001/sop' },
  { label: 'Word Track Changes',       to: '/e/se_001/audit' },
  { label: 'Viewer',                   to: '/v/se_004' },
  { label: 'Processing',               to: '/p/se_007' },
  { label: 'Improvements',             to: '/improvements' },
  { label: 'GCS QA',                   to: '/gcs' },
];

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

    <TweaksPanel title="Tweaks">
      <div class="twk-sect">Appearance</div>
      <div class="twk-radio">
        <div class="twk-radio__lbl">Theme</div>
        <div class="twk-radio__row">
          <button :class="['twk-radio__opt', { 'is-active': ui.theme === 'light' }]" @click="ui.setTheme('light')">Light</button>
          <button :class="['twk-radio__opt', { 'is-active': ui.theme === 'dark' }]" @click="ui.setTheme('dark')">Dark</button>
        </div>
      </div>
      <div class="twk-radio">
        <div class="twk-radio__lbl">Brand</div>
        <div class="twk-radio__row">
          <button :class="['twk-radio__opt', { 'is-active': ui.brand === 'vin' }]" @click="ui.setBrand('vin')">VIN</button>
          <button :class="['twk-radio__opt', { 'is-active': ui.brand === 'vspn' }]" @click="ui.setBrand('vspn')">VSPN</button>
        </div>
      </div>
      <div class="twk-radio">
        <div class="twk-radio__lbl">Density</div>
        <div class="twk-radio__row">
          <button :class="['twk-radio__opt', { 'is-active': ui.density === 'comfortable' }]" @click="ui.setDensity('comfortable')">Comfort</button>
          <button :class="['twk-radio__opt', { 'is-active': ui.density === 'compact' }]" @click="ui.setDensity('compact')">Compact</button>
        </div>
      </div>

      <div class="twk-sect">Editor</div>
      <div class="twk-radio">
        <div class="twk-radio__lbl">Slide-rail mode</div>
        <div class="twk-radio__row">
          <button :class="['twk-radio__opt', { 'is-active': ui.slideRailMode === 'focus' }]" @click="ui.slideRailMode = 'focus'">Focus</button>
          <button :class="['twk-radio__opt', { 'is-active': ui.slideRailMode === 'filter' }]" @click="ui.slideRailMode = 'filter'">Filter</button>
        </div>
      </div>
      <div class="twk-toggle" @click="ui.aiFlagOverlays = !ui.aiFlagOverlays">
        <span class="twk-toggle__lbl">AI flag overlays</span>
        <button :class="['twk-toggle__sw', { 'is-on': ui.aiFlagOverlays }]" @click.stop="ui.aiFlagOverlays = !ui.aiFlagOverlays">
          <span class="twk-toggle__knob" />
        </button>
      </div>
      <div class="twk-toggle" @click="ui.statusBarVisible = !ui.statusBarVisible">
        <span class="twk-toggle__lbl">Debug status bar</span>
        <button :class="['twk-toggle__sw', { 'is-on': ui.statusBarVisible }]" @click.stop="ui.statusBarVisible = !ui.statusBarVisible">
          <span class="twk-toggle__knob" />
        </button>
      </div>

      <div class="twk-sect">Quick navigate</div>
      <button
        v-for="n in QUICK_NAV"
        :key="n.to"
        class="twk-btn"
        @click="router.push(n.to)"
      >{{ n.label }}</button>
    </TweaksPanel>
  </div>
</template>
