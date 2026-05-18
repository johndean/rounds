<script setup lang="ts">
/**
 * SettingsView — verbatim port of settings-pages.jsx::SettingsRouterPane (827-843).
 * Sidebar + 12 dispatched sections. Sub-page drill-ins live inside their
 * respective section component (Email→Builder, Diagnostics→GCS/Email Debug,
 * Prompt Templates→New).
 */
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
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
import SectionDiagnostics from '@/components/settings/SectionDiagnostics.vue';
import SectionDeleted from '@/components/settings/SectionDeleted.vue';

const props = defineProps<{ section?: string }>();

interface SectionItem { id: string; label: string }
const SECTIONS: readonly SectionItem[] = Object.freeze([
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
  { id: 'diagnostics', label: 'Diagnostics' },
  { id: 'deleted',     label: 'Deleted sessions' },
]);

const active = computed(() => props.section ?? 'general');
</script>

<template>
  <div class="settings">
    <aside class="settings__sidebar">
      <RouterLink
        v-for="s in SECTIONS"
        :key="s.id"
        :to="`/settings/${s.id}`"
        :class="{ 'is-active': active === s.id }"
      >{{ s.label }}</RouterLink>
    </aside>

    <main class="settings__content">
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
      <SectionDiagnostics v-else-if="active === 'diagnostics'" />
      <SectionDeleted v-else-if="active === 'deleted'" />
      <SectionGeneral v-else />
    </main>
  </div>
</template>
