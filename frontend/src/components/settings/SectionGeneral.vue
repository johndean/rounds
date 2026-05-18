<script setup lang="ts">
/**
 * SectionGeneral — persists `org_name`, `default_locale`, `default_timezone`
 * to org_settings via /v1/settings.
 */
import { onMounted, ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import FormRow from './FormRow.vue';
import { settingsApi } from '@/services/api';
import { toast } from '@/composables/useToast';

const name = ref('VIN VIN Transcript Software');
const tz = ref('America/Chicago');
const locale = ref('en-US');
const loading = ref(true);
const saving = ref(false);

onMounted(async () => {
  try {
    const s = (await settingsApi.list()) as Record<string, unknown>;
    if (typeof s.org_name === 'string') name.value = s.org_name;
    if (typeof s.default_locale === 'string') locale.value = s.default_locale;
    if (typeof s.default_timezone === 'string') tz.value = s.default_timezone;
  } catch {
    /* keep defaults */
  } finally {
    loading.value = false;
  }
});

async function save(): Promise<void> {
  saving.value = true;
  try {
    await Promise.all([
      settingsApi.set('org_name', name.value),
      settingsApi.set('default_locale', locale.value),
      settingsApi.set('default_timezone', tz.value),
    ]);
    toast.push('General saved', { tone: 'success' });
  } catch {
    toast.push('Failed to save General settings', { tone: 'error' });
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <SettingsHeader title="General" lead="Workspace identity, default locale, and time zone." />
  <div class="set-form">
    <FormRow label="Organisation name">
      <input class="set-input" :value="name" :disabled="loading" @change="(e) => (name = (e.target as HTMLInputElement).value)" />
    </FormRow>
    <FormRow label="Default locale">
      <select class="set-input" :value="locale" :disabled="loading" @change="(e) => (locale = (e.target as HTMLSelectElement).value)">
        <option value="en-US">English (US)</option>
        <option value="en-GB">English (UK)</option>
        <option value="es-ES">Spanish</option>
      </select>
    </FormRow>
    <FormRow label="Time zone">
      <select class="set-input" :value="tz" :disabled="loading" @change="(e) => (tz = (e.target as HTMLSelectElement).value)">
        <option value="America/Chicago">America/Chicago (CT)</option>
        <option value="America/Los_Angeles">America/Los_Angeles (PT)</option>
        <option value="America/New_York">America/New_York (ET)</option>
        <option value="Europe/London">Europe/London (GMT)</option>
      </select>
    </FormRow>
    <div class="set-form__actions">
      <button class="btn btn--primary" :disabled="saving" @click="save">{{ saving ? 'Saving…' : 'Save' }}</button>
    </div>
  </div>
</template>
