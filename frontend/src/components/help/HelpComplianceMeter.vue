<script setup lang="ts">
/**
 * frontend/src/components/help/HelpComplianceMeter.vue
 *
 * Purpose:
 *     Inline CC-Rounds compliance indicator. Three dots (words / summary
 *     / steps) plus an overall percent. Renders next to each row in
 *     HelpEditor and inside the article editor dialog so the admin can
 *     see at a glance which articles will publish via "Publish all
 *     drafts" and which need a Fix-CC-Rounds rewrite.
 *
 *     Reads from the shared CC-Rounds SSOT (frontend/src/utils/helpCompliance.ts).
 *     The same thresholds live in app/utils/help_compliance.py — drift
 *     is pinned by a backend test.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §9.4
 */
import { computed } from 'vue';
import { computeCompliance, type ComplianceInput } from '@/utils/helpCompliance';

const props = withDefaults(defineProps<{
  article: ComplianceInput;
  /** When true, expand the meter into a labelled grid; default is the compact 3-dot strip. */
  detailed?: boolean;
}>(), { detailed: false });

const cc = computed(() => computeCompliance(props.article));
</script>

<template>
  <span v-if="!detailed" :class="['ccm', { 'is-pass': cc.allPass }]" :title="`Words ${cc.wordsOk ? 'OK' : 'low'} · Summary ${cc.summaryOk ? 'OK' : 'off'} · Steps ${cc.stepsOk ? 'OK' : 'short'} · ${cc.pct}%`">
    <span :class="['ccm__dot', { 'is-ok': cc.wordsOk }]" aria-label="words">W</span>
    <span :class="['ccm__dot', { 'is-ok': cc.summaryOk }]" aria-label="summary">S</span>
    <span :class="['ccm__dot', { 'is-ok': cc.stepsOk }]" aria-label="steps">S</span>
    <span class="ccm__pct">{{ cc.pct }}%</span>
  </span>

  <div v-else class="ccmd">
    <div class="ccmd__head">
      <span class="ccmd__title">CC-Rounds compliance</span>
      <span :class="['ccmd__badge', cc.allPass ? 'is-pass' : 'is-fail']">
        {{ cc.allPass ? 'passes' : 'needs work' }}
      </span>
    </div>
    <div class="ccmd__grid">
      <div :class="['ccmd__row', { 'is-ok': cc.wordsOk }]">
        <span class="ccmd__label">Words</span>
        <span class="ccmd__val">{{ cc.wordCount }}</span>
      </div>
      <div :class="['ccmd__row', { 'is-ok': cc.summaryOk }]">
        <span class="ccmd__label">Summary chars</span>
        <span class="ccmd__val">{{ cc.summaryLen }}</span>
      </div>
      <div :class="['ccmd__row', { 'is-ok': cc.stepsOk }]">
        <span class="ccmd__label">Steps</span>
        <span class="ccmd__val">{{ cc.stepCount }}</span>
      </div>
    </div>
    <div class="ccmd__bar">
      <div class="ccmd__bar-fill" :style="{ width: `${cc.pct}%` }" />
    </div>
  </div>
</template>

<style scoped>
.ccm {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(185, 28, 28, 0.08);
  color: #b91c1c;
  font-size: 10px;
  font-weight: 800;
  font-family: var(--font-mono);
}
.ccm.is-pass {
  background: rgba(16, 122, 87, 0.1);
  color: #107a57;
}
.ccm__dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: rgba(185, 28, 28, 0.15);
  color: #b91c1c;
  font-size: 8px;
  font-weight: 800;
}
.ccm__dot.is-ok {
  background: rgba(16, 122, 87, 0.15);
  color: #107a57;
}
.ccm__pct {
  margin-left: 4px;
  font-size: 10px;
}

/* Detailed grid */
.ccmd {
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ccmd__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.ccmd__title {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-steel);
}
.ccmd__badge {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.ccmd__badge.is-pass { background: rgba(16, 122, 87, 0.1); color: #107a57; }
.ccmd__badge.is-fail { background: rgba(185, 28, 28, 0.1); color: #b91c1c; }

.ccmd__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.ccmd__row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  background: var(--color-white);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
}
.ccmd__row.is-ok { border-color: #4ade80; }
.ccmd__label {
  font-size: 10px;
  color: var(--color-steel);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 700;
}
.ccmd__val {
  font-size: 14px;
  font-family: var(--font-mono);
  font-weight: 800;
  color: var(--color-navy);
}
.ccmd__row.is-ok .ccmd__val { color: #107a57; }

.ccmd__bar {
  height: 4px;
  background: var(--color-light-steel);
  border-radius: 999px;
  overflow: hidden;
}
.ccmd__bar-fill {
  height: 100%;
  background: var(--color-blue);
  transition: width 200ms ease-out;
}
</style>
