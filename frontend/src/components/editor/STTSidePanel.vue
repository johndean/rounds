<script setup lang="ts">
/**
 * STTSidePanel — verbatim port of editor.jsx::STTSidePanel (888-935).
 * Right-rail body for the STT tab: engine info, token distribution, legend,
 * invariants. Always renders (replaces the Active Slide right rail on STT tab).
 */
import { computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import type { Segment } from '@/fixtures/transcript';
import { DISCREPANCIES } from '@/fixtures/audit';
import { fmtTime } from '@/utils/editorHelpers';

const props = defineProps<{
  time: number;
  totalDuration: number;
  segments: readonly Segment[];
}>();

const driftCount    = computed(() => DISCREPANCIES.filter((d) => d.kind === 'drift').length);
const punctCount    = computed(() => DISCREPANCIES.filter((d) => d.kind === 'punctuation').length);
const fillerCount   = computed(() => DISCREPANCIES.filter((d) => d.kind === 'filler').length);
const lowConfCount  = computed(() => DISCREPANCIES.filter((d) => d.kind === 'low_confidence').length);
</script>

<template>
  <aside class="stt-side" aria-label="STT debug panel" data-screen-label="STT Debug Panel">
    <h4>STT Stream</h4>
    <div class="stt-side__row"><span>Engine</span><span>Google STT v3</span></div>
    <div class="stt-side__row"><span>Model</span><span>latest_long</span></div>
    <div class="stt-side__row"><span>Sample rate</span><span>48 kHz</span></div>
    <div class="stt-side__row"><span>Channels</span><span>mono</span></div>
    <div class="stt-side__row"><span>Stream depth</span><span>{{ props.segments.length }} segs</span></div>
    <div class="stt-side__row"><span>Cursor</span><span>{{ fmtTime(props.time) }} / {{ fmtTime(props.totalDuration) }}</span></div>

    <h4>Token Distribution</h4>
    <div class="stt-side__row"><span>drift</span><span :style="{ color: 'var(--color-red)' }">{{ driftCount }}</span></div>
    <div class="stt-side__row"><span>punctuation</span><span>{{ punctCount }}</span></div>
    <div class="stt-side__row"><span>filler</span><span :style="{ color: 'var(--color-amber)' }">{{ fillerCount }}</span></div>
    <div class="stt-side__row"><span>low_confidence</span><span :style="{ color: '#6FA9F0' }">{{ lowConfCount }}</span></div>

    <h4>Legend</h4>
    <div class="stt-side__legend">
      <div><code class="stt-token stt-token--drift">fifty</code><span>drift vs base_text</span></div>
      <div><code class="stt-token stt-token--filler">[um]</code><span>recognised filler</span></div>
      <div><code :style="{ background: 'var(--color-gold)', color: 'var(--color-navy)', padding: '1px 6px', borderRadius: '3px' }">word</code><span>current playback word</span></div>
      <div><code>word<sup :style="{ fontSize: '8px', opacity: 0.5 }">12.4</sup></code><span>token start time (s)</span></div>
    </div>

    <h4>Invariants</h4>
    <div :style="{ fontSize: '11px', fontFamily: 'var(--font-family)', lineHeight: 1.55, color: 'var(--color-light-steel)' }">
      <p :style="{ margin: '0 0 8px' }">
        <span class="chip chip--green" :style="{ marginRight: '4px' }"><Icon name="check" :size="10" /> L2</span>
        STT tokens never participate in correction lineage.
      </p>
      <p :style="{ margin: '0 0 8px' }">
        <span class="chip chip--green" :style="{ marginRight: '4px' }"><Icon name="check" :size="10" /> §9</span>
        Pipeline isolation test verifies separate stores; no cross-references.
      </p>
      <p :style="{ margin: 0 }">
        <span class="chip chip--green" :style="{ marginRight: '4px' }"><Icon name="check" :size="10" /> §15.1</span>
        STT tab is reference-only — no edit controls rendered.
      </p>
    </div>
  </aside>
</template>
