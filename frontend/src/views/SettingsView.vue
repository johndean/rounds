<script setup lang="ts">
/**
 * SettingsView — verbatim port of improvements.jsx::SettingsRoute (376-410)
 * + settings-pages.jsx::SettingsRouterPane (827-843).
 *
 * Matches the React SSOT DOM structure exactly:
 *   <main class="settings-page">
 *     <aside class="settings-nav">
 *       <h2 class="page-title">Settings</h2>
 *       <ul><li><button class="settings-nav__item is-active?">…</button></li></ul>
 *     </aside>
 *     <section class="settings-content"><SectionX/></section>
 *   </main>
 *
 * Route param /settings/:section drives `active` so URLs stay deep-linkable —
 * additive over the React version (which used component-local state).
 */
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import SectionGeneral from '@/components/settings/SectionGeneral.vue';
import SectionTeam from '@/components/settings/SectionTeam.vue';
import SectionTypes from '@/components/settings/SectionTypes.vue';
import SectionAIModels from '@/components/settings/SectionAIModels.vue';
import SectionUpload from '@/components/settings/SectionUpload.vue';
import SectionDiscrepancy from '@/components/settings/SectionDiscrepancy.vue';
import SectionExport from '@/components/settings/SectionExport.vue';
import SectionPromptTemplates from '@/components/settings/SectionPromptTemplates.vue';
import SectionManifest from '@/components/settings/SectionManifest.vue';
import SectionEmail from '@/components/settings/SectionEmail.vue';
import SectionAuthUsers from '@/components/settings/SectionAuthUsers.vue';
import SectionDiagnostics from '@/components/settings/SectionDiagnostics.vue';
import SectionDeleted from '@/components/settings/SectionDeleted.vue';

const props = defineProps<{ section?: string }>();
const router = useRouter();

interface SectionItem { id: string; label: string }
const sections: readonly SectionItem[] = Object.freeze([
  { id: 'general',     label: 'General' },
  { id: 'team',        label: 'Team & roles' },
  { id: 'types',       label: 'Types & stage defaults' },
  { id: 'ai-models',   label: 'AI models' },
  { id: 'upload',      label: 'Upload & storage' },
  { id: 'discrepancy', label: 'Discrepancy classification' },
  { id: 'export',      label: 'Export' },
  { id: 'prompts',     label: 'Prompt templates' },
  { id: 'manifest',    label: 'Session manifest' },
  { id: 'email',       label: 'Email' },
  { id: 'auth-users',  label: 'Auth & logins' },
  { id: 'diagnostics', label: 'Diagnostics' },
  { id: 'deleted',     label: 'Deleted sessions' },
]);

const active = computed(() => props.section ?? 'general');

function pick(id: string): void {
  router.push(`/settings/${id}`);
}
</script>

<template>
  <main class="settings-page" data-screen-label="Settings">
    <aside class="settings-nav" aria-label="Settings sections">
      <h2 class="page-title" :style="{ fontSize: '22px', marginBottom: '18px' }">Settings</h2>
      <ul>
        <li v-for="s in sections" :key="s.id">
          <button
            :class="['settings-nav__item', active === s.id ? 'is-active' : '']"
            @click="pick(s.id)"
          >{{ s.label }}</button>
        </li>
      </ul>
    </aside>
    <section class="settings-content">
      <SectionGeneral v-if="active === 'general'" />
      <SectionTeam v-else-if="active === 'team'" />
      <SectionTypes v-else-if="active === 'types'" />
      <SectionAIModels v-else-if="active === 'ai-models'" />
      <SectionUpload v-else-if="active === 'upload'" />
      <SectionDiscrepancy v-else-if="active === 'discrepancy'" />
      <SectionExport v-else-if="active === 'export'" />
      <SectionPromptTemplates v-else-if="active === 'prompts'" />
      <SectionManifest v-else-if="active === 'manifest'" />
      <SectionEmail v-else-if="active === 'email'" />
      <SectionAuthUsers v-else-if="active === 'auth-users'" />
      <SectionDiagnostics v-else-if="active === 'diagnostics'" />
      <SectionDeleted v-else-if="active === 'deleted'" />
      <SectionGeneral v-else />
    </section>
  </main>
</template>
