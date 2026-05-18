<script setup lang="ts">
/**
 * SectionGeneral — verbatim port of settings-pages.jsx::SectionGeneral (61-78).
 */
import { ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import FormRow from './FormRow.vue';
import { toast } from '@/composables/useToast';

const name = ref('VIN VIN Transcript Software');
const tz = ref('America/Chicago');
const locale = ref('en-US');

function save(): void {
  toast.push('General saved', { tone: 'success' });
}
</script>

<template>
  <SettingsHeader title="General" lead="Workspace identity, default locale, and time zone." />
  <div class="set-form">
    <FormRow label="Organisation name">
      <input class="set-input" :value="name" @change="(e) => (name = (e.target as HTMLInputElement).value)" />
    </FormRow>
    <FormRow label="Default locale">
      <select class="set-input" :value="locale" @change="(e) => (locale = (e.target as HTMLSelectElement).value)">
        <option value="en-US">English (US)</option>
        <option value="en-GB">English (UK)</option>
        <option value="es-ES">Spanish</option>
      </select>
    </FormRow>
    <FormRow label="Time zone">
      <select class="set-input" :value="tz" @change="(e) => (tz = (e.target as HTMLSelectElement).value)">
        <option value="America/Chicago">America/Chicago (CT)</option>
        <option value="America/Los_Angeles">America/Los_Angeles (PT)</option>
        <option value="America/New_York">America/New_York (ET)</option>
        <option value="Europe/London">Europe/London (GMT)</option>
      </select>
    </FormRow>
    <div class="set-form__actions">
      <button class="btn btn--primary" @click="save">Save</button>
    </div>
  </div>
</template>
