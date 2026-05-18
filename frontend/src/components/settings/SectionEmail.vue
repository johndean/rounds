<script setup lang="ts">
/**
 * SectionEmail — verbatim port of settings-pages.jsx::SectionEmail (440-460).
 * Home view + drill-into EmailBuilder.
 */
import { ref } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import EmailBuilder from './EmailBuilder.vue';

const view = ref<'home' | 'builder'>('home');
</script>

<template>
  <EmailBuilder v-if="view === 'builder'" @back="view = 'home'" />
  <template v-else>
    <SettingsHeader
      title="Email templates"
      lead="Per-Type × per-Stage stage-notification HTML templates. Edit in the dedicated builder."
      :header-cta="{ label: 'Open builder', onClick: () => (view = 'builder') }"
    />
    <div class="set-card-block">
      <div class="set-eyebrow">STAGE ASSIGNEES + NOTIFY-ON-ENTRY CHECKBOXES</div>
      <h4 :style="{ margin: '6px 0 6px', fontSize: '16px', fontWeight: 700 }">Stage triggers via Types matrix</h4>
      <p :style="{ fontSize: '13px', color: 'var(--fg2)', lineHeight: 1.6, margin: 0 }">
        Stage-level email triggers live in the <strong>Types & stage defaults</strong> matrix per Type. Each stage has a default assignee (person or group) and an optional <em>Email</em> toggle that fires the stage-notification template on entry.
      </p>
    </div>
    <div class="set-card-block">
      <div class="set-eyebrow">ADMIN · TEST EMAIL</div>
      <h4 :style="{ margin: '6px 0 6px', fontSize: '16px', fontWeight: 700 }">Email send diagnostics</h4>
      <p :style="{ fontSize: '13px', color: 'var(--fg2)', lineHeight: 1.6, margin: 0 }">
        Check SMTP config, test connectivity, and send a test email. Copyable diagnostic bundle for support tickets.
      </p>
    </div>
  </template>
</template>
