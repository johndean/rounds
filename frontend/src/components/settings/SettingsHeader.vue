<script setup lang="ts">
/**
 * SettingsHeader — verbatim port of settings-pages.jsx::SettingsHeader (796-805).
 */
defineProps<{
  title: string;
  lead: string;
  headerCta?: { label: string; onClick: () => void };
}>();
</script>

<template>
  <div class="settings-row">
    <div>
      <h3>{{ title }}</h3>
      <p>{{ lead }}</p>
    </div>
    <button v-if="headerCta" class="btn btn--tertiary" @click="headerCta.onClick">{{ headerCta.label }}</button>
  </div>
</template>
