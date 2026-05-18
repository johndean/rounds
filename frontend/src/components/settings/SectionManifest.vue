<script setup lang="ts">
/**
 * SectionManifest — verbatim port of settings-pages.jsx::SectionManifest (409-438).
 */
import SettingsHeader from './SettingsHeader.vue';

interface ManifestField { f: string; desc: string }
const fields: ManifestField[] = [
  { f: 'session code = …',                                                desc: 'filename prefix + session code badge' },
  { f: 'long title = / short title = …',                                  desc: 'session header titles' },
  { f: '*Moderator = … + Bio',                                            desc: 'speaker records (moderator = primary)' },
  { f: 'CE Broker / VIN# fields',                                         desc: 'CE metadata badges' },
  { f: 'Zoom = …, Session pg = …, Podbean, VINcast, MB',                  desc: 'publishing links' },
  { f: '@N blocks with URLs',                                             desc: 'per-slide resource icons in Editor slide rail' },
  { f: 'Tags: …',                                                         desc: 'category chips' },
  { f: 'Polls section',                                                   desc: 'parsed by polls regex into polls_parsed JSONB' },
];
</script>

<template>
  <SettingsHeader
    title="Session manifest (extras2)"
    lead="Upload a producer-prepared extras2.txt alongside the video/audio to auto-populate speaker labels, per-slide resources, and publishing links in the exported .docx. Optional — sessions without it still export cleanly."
  />
  <div class="set-eyebrow" :style="{ marginBottom: '12px' }">
    EXPECTED FIELDS <span :style="{ color: 'var(--fg2)', marginLeft: '6px', textTransform: 'none', letterSpacing: 0, fontWeight: 500 }">· pure regex parsing, no AI</span>
  </div>
  <div class="set-manifest">
    <div v-for="(f, i) in fields" :key="i" class="set-manifest__row">
      <code>{{ f.f }}</code>
      <span>{{ f.desc }}</span>
    </div>
  </div>
  <div class="set-eyebrow" :style="{ marginTop: '22px', marginBottom: '8px' }">FILENAME CONVENTIONS</div>
  <p :style="{ fontSize: '13px', color: 'var(--fg1)', lineHeight: 1.6, margin: 0 }">
    Any <code>.txt</code> whose name matches <code>*extras2*</code>, <code>*_manifest*</code>, or starts with <code>manifest_</code> is auto-routed to the manifest slot on upload. Otherwise drop any <code>.txt</code> in the upload dropzone and re-tag it.
  </p>
</template>
