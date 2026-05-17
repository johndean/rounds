<script setup lang="ts">
/**
 * App root.
 *   AppHeader (sticky TopBar) + <RouterView /> + overlay hosts (toast / confirm / modal / palette).
 *   IMPLEMENTATION.md §3 (TopBar), §12 (wiring infrastructure).
 */
import AppHeader from '@/components/AppHeader.vue';
import ToastHost from '@/components/overlays/ToastHost.vue';
</script>

<template>
  <AppHeader />
  <main class="page">
    <RouterView v-slot="{ Component, route }">
      <component :is="Component" :key="route.fullPath" />
    </RouterView>
  </main>
  <ToastHost />
  <!-- TODO Phase 2 / U9: ConfirmHost, ModalHost, CommandPalette, FindReplaceModal -->
</template>
