/**
 * Help Center store — drawer open/close state + current route context.
 *
 * Phase 2 of the 2026-06-04 stakeholder remediation. The Help Center is
 * a right-side drawer (HelpCenterDrawer.vue) that surfaces context-
 * sensitive help content keyed by the current Vue Router route name.
 * Content lives in frontend/src/content/help/*.md as bundled markdown.
 *
 * The drawer is opened from a "?" button in the AppHeader topbar tools
 * cluster. ESC closes. The store is minimal — just open/close — because
 * the route context is read directly from useRoute() inside the drawer
 * component, so the store doesn't need to mirror it.
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useHelpCenterStore = defineStore('helpCenter', () => {
  const isOpen = ref(false);

  function open(): void { isOpen.value = true; }
  function close(): void { isOpen.value = false; }
  function toggle(): void { isOpen.value = !isOpen.value; }

  return { isOpen, open, close, toggle };
});
