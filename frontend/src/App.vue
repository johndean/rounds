<script setup lang="ts">
/**
 * App root.
 *   AppHeader (sticky TopBar) on every internal route + <RouterView />
 *   + overlay hosts (toast / confirm / modal / palette).
 *   Login route renders its own full-screen shell (no chrome).
 *   IMPLEMENTATION.md §3 (TopBar), §12 (wiring infrastructure).
 */
import { onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import AppHeader from '@/components/AppHeader.vue';
import ToastHost from '@/components/overlays/ToastHost.vue';
import ConfirmHost from '@/components/overlays/ConfirmHost.vue';
import ModalHost from '@/components/overlays/ModalHost.vue';
import CommandPalette from '@/components/overlays/CommandPalette.vue';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const route = useRoute();

const showChrome = computed(() => route.name !== 'login');

onMounted(() => {
  // Rehydrate from stored JWT on first load
  auth.bootstrap();
});
</script>

<template>
  <AppHeader v-if="showChrome" />
  <main :class="['page', { 'page--bare': !showChrome }]">
    <RouterView v-slot="{ Component, route: r }">
      <component :is="Component" :key="r.fullPath" />
    </RouterView>
  </main>
  <ToastHost />
  <ConfirmHost />
  <ModalHost />
  <CommandPalette />
</template>

<style>
.page--bare { padding: 0; }
</style>
