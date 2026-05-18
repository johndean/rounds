<script setup lang="ts">
/**
 * ImprovDetail — 5-step Action Plan Builder.
 * Faithful 1:1 port of docs/port-source/improvements.jsx::ImprovDetail (132-372).
 */
import { computed, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { toast } from '@/composables/useToast';
import type { ImprovementFixture } from '@/fixtures/improvements';

const props = defineProps<{ item: ImprovementFixture }>();
defineEmits<{ close: [] }>();

const step = ref(0);
const model = ref('Gemini 2.5 Pro (recommended)');
const adminStatus = ref(props.item.status === 'rolled-out' ? 'Rolled out' : 'Approved');
const adminRisk = ref((props.item.risk || 'low').toUpperCase());
const adminVersion = ref('');
const adminNotes = ref(
  `AI Transcript Karaoke + Click-to-Seek — Phase 2-Mega Plan v2 (post-adversarial-review)\n\n> **Scope.** Make AI Transcript pane karaoke + click-to-seek work end-to-end during playback. Frontend-only. No migrations.`,
);
const expandAll = ref(false);
const openSections = ref<Record<string, boolean>>({ requirements: true, implementation: false, testing: false });

const steps = [
  { id: 0, label: 'Overview',       sub: 'Summary' },
  { id: 1, label: 'Requirements',   sub: 'Criteria' },
  { id: 2, label: 'Implementation', sub: 'Dev prompt' },
  { id: 3, label: 'Testing',        sub: 'Validation' },
  { id: 4, label: 'Review',         sub: 'Approve' },
];

const riskUp = computed(() => (props.item.risk || 'low').toUpperCase());
const impId = computed(() => props.item.id.startsWith('IMP-')
  ? props.item.id
  : `IMP-${String(parseInt(props.item.id.replace(/\D/g, ''), 10) + 999).padStart(4, '0')}`);
const typeLabel = computed(() => props.item.area || 'Bug Fix');
const priorityLabel = computed(() =>
  props.item.priority === 'crit' ? 'Critical' :
  props.item.priority === 'high' ? 'High' :
  props.item.priority === 'med'  ? 'Medium' : 'Low');

const reqDoc = computed(() => `## Requirements: ${props.item.title}

### Objective
${typeLabel.value} · ${props.item.description ? props.item.description.slice(0, 80) : `reported at ${props.item.surface || '/admin/improvements/'}`}

### Scope
- **Affected Area:** ${props.item.surface || 'General'}
- **Risk Classification:** ${riskUp.value}
- **Improvement Type:** ${typeLabel.value}
- **Priority:** ${priorityLabel.value}
- **Impact Scope:** Single Page
- **Plan Steps:** 5

### Acceptance Criteria
- [ ] **Step 1 — Root Cause Analysis:** Investigate and identify the root cause of the reported bug. Document reproduction steps and affected components.
- [ ] **Step 2 — Implementation Scope:** Define the technical implementation plan, affected components, and estimated effort.
- [ ] **Step 3 — Fix Verification:** Verify the fix resolves the original issue without introducing regressions. Confirm reproduction steps no longer trigger the bug.
- [ ] **Step 4 — Testing & Validation:** Create test cases covering happy paths, edge cases, and regression scenarios.
- [ ] **Step 5 — Rollout & Documentation:** Plan staged rollout, update Help Center articles, and notify affected users.`);

const implDoc = computed(() => `## Implementation Prompt: ${props.item.title}

### Context
${typeLabel.value} · ${props.item.description ? props.item.description.slice(0, 80) : `reported at ${props.item.surface || '/admin/improvements/'}`}

**Affected Area:** ${props.item.surface || 'General'}
**Risk Level:** ${riskUp.value}
**Type:** ${typeLabel.value}
**Impact Scope:** Single Page

### Requirements Summary
- [ ] **Step 1 — Root Cause Analysis:** Investigate and identify the root cause of the reported bug. Document reproduction steps and affected components.
- [ ] **Step 2 — Implementation Scope:** Define the technical implementation plan, affected components, and estimated effort.
- [ ] **Step 3 — Fix Verification:** Verify the fix resolves the original issue without introducing regressions. Confirm reproduction steps no longer trigger the bug.
- [ ] **Step 4 — Testing & Validation:** Create test cases covering happy paths, edge cases, and regression scenarios.
- [ ] **Step 5 — Rollout & Documentation:** Plan staged rollout, update Help Center articles, and notify affected users.

### Affected Components
- \`To be determined based on scope analysis\``);

const testDoc = computed(() => `## Test Plan: ${props.item.title}

### Test Objectives
Validate that the implementation of "${props.item.title}" meets all acceptance criteria, handles edge cases gracefully, and does not introduce regressions.

### Happy Path Scenarios
**Scenario 1: Root Cause Analysis**
- Given: The system is in its current production state
- When: Investigate and identify the root cause of the reported bug. Document reproduction steps and affected components.
- Then: The step completes successfully without errors

**Scenario 2: Implementation Scope**
- Given: The system is in its current production state
- When: Define the technical implementation plan, affected components, and estimated effort.
- Then: The step completes successfully without errors

**Scenario 3: Fix Verification**
- Given: The system is in its current production state
- When: Verify the fix resolves the original issue without introducing regressions.
- Then: The step completes successfully without errors

**Scenario 4: Testing & Validation**`);

function linesOf(txt: string): number { return txt.split('\n').length; }

async function copyText(text: string, label: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    toast.push(`${label} copied`, { tone: 'success' });
  } catch {
    toast.push('Clipboard blocked', { tone: 'warn' });
  }
}

function exportMd(): void {
  const merged = `# ${props.item.title}\n\n${reqDoc.value}\n\n---\n\n${implDoc.value}\n\n---\n\n${testDoc.value}\n`;
  const blob = new Blob([merged], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${impId.value}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  toast.push('.md exported', { tone: 'success' });
}

// Phase 2 audit remediation: both regenerate (fake setTimeout success)
// and save (no API call) demoted to honest warn. Real wiring uses
// improvementsApi.admin / improvementsApi.saveStep — full Action Plan
// Builder integration ships with Phase 8 prompt-template port + the
// matching backend handlers.
function regenerate(): void {
  toast.push(
    'AI prompt regeneration not yet wired — ships with Phase 8 templates port.',
    { tone: 'warn' },
  );
}

function save(): void {
  toast.push(
    'Improvement detail save not yet wired — ships with Phase 8 admin patch endpoints.',
    { tone: 'warn' },
  );
}

const reviewSections = computed(() => [
  { k: 'requirements',   label: 'REQUIREMENTS',          doc: reqDoc.value },
  { k: 'implementation', label: 'IMPLEMENTATION PROMPT', doc: implDoc.value },
  { k: 'testing',        label: 'TESTING & VALIDATION',  doc: testDoc.value },
]);
function isSectionOpen(k: string): boolean { return expandAll.value || !!openSections.value[k]; }
</script>

<template>
  <div class="impv-head">
    <div>
      <h2 class="impv-title">{{ item.title }}</h2>
      <p class="impv-sub">Action Plan Builder · {{ impId }}</p>
    </div>
    <div :style="{ display: 'flex', gap: '8px', alignItems: 'center' }">
      <span :class="`risk-pill risk-pill--${item.risk || 'low'}`">{{ riskUp }}</span>
      <button class="btn btn--ghost btn--icon btn--sm" title="Close" @click="$emit('close')"><Icon name="x" :size="12" /></button>
    </div>
  </div>

  <div class="impv-stepper">
    <button
      v-for="s in steps"
      :key="s.id"
      :class="['impv-step', { 'is-active': step === s.id, 'is-done': step > s.id }]"
      @click="step = s.id"
    >
      <span class="impv-step__circle">
        <Icon v-if="step > s.id" name="check" :size="12" />
        <template v-else>{{ s.id + 1 }}</template>
      </span>
      <div class="impv-step__label">{{ s.label }}</div>
      <div class="impv-step__sub">{{ s.sub }}</div>
    </button>
  </div>

  <div class="impv-modelbar">
    <span class="impv-modelbar__lbl">AI Model:</span>
    <select v-model="model" class="impv-modelbar__select">
      <option>Gemini 2.5 Pro (recommended)</option>
      <option>Gemini 2.5 Flash</option>
      <option>GPT-5</option>
      <option>Claude Opus 4.5</option>
    </select>
    <Icon name="chevron-right" :size="12" class="impv-modelbar__chev" />
  </div>

  <div class="impv-body">
    <!-- Step 0: Overview -->
    <div v-if="step === 0" class="impv-overview">
      <div class="impv-grid-2">
        <div><div class="impv-lbl">Submitted by</div><div class="impv-val">{{ item.author }}</div></div>
        <div><div class="impv-lbl">Area</div><div class="impv-val">{{ item.surface || item.area }}</div></div>
        <div><div class="impv-lbl">Created</div><div class="impv-val">{{ new Date(item.created).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true }) }}</div></div>
        <div>
          <div class="impv-lbl">Current Status</div>
          <div class="impv-val">
            <span v-if="item.status === 'rolled-out'" class="status-pill status-pill--rolled" :style="{ display: 'block', textAlign: 'center', padding: '5px 0' }">ROLLED OUT</span>
            <span v-if="item.status === 'pending'" class="status-pill status-pill--pending" :style="{ display: 'block', textAlign: 'center', padding: '5px 0' }">PENDING</span>
          </div>
        </div>
        <div><div class="impv-lbl">Type</div><div class="impv-val">{{ typeLabel }}</div></div>
        <div><div class="impv-lbl">Priority</div><div class="impv-val">{{ priorityLabel }}</div></div>
        <div><div class="impv-lbl">Impact Scope</div><div class="impv-val">Single Page</div></div>
        <div><div class="impv-lbl">Affected Roles</div><div class="impv-val" :style="{ color: 'var(--fg2)' }">—</div></div>
      </div>
      <div class="impv-section">
        <div class="impv-lbl">Description</div>
        <p :style="{ margin: '8px 0 0', fontSize: '13px', color: 'var(--fg1)', lineHeight: 1.6 }">{{ item.description }}</p>
      </div>
    </div>

    <!-- Steps 1-3: prompt blocks -->
    <template v-if="step === 1">
      <div class="impv-prompt-head">
        <span class="impv-prompt-eyebrow">REQUIREMENTS DOCUMENT</span>
        <button class="btn btn--secondary btn--sm" @click="regenerate"><Icon name="history" :size="11" /> Regenerate</button>
      </div>
      <pre class="impv-mdcode">{{ reqDoc }}</pre>
    </template>
    <template v-if="step === 2">
      <div class="impv-prompt-head">
        <span class="impv-prompt-eyebrow">IMPLEMENTATION PROMPT</span>
        <button class="btn btn--secondary btn--sm" @click="regenerate"><Icon name="history" :size="11" /> Regenerate</button>
      </div>
      <pre class="impv-mdcode">{{ implDoc }}</pre>
    </template>
    <template v-if="step === 3">
      <div class="impv-prompt-head">
        <span class="impv-prompt-eyebrow">TESTING &amp; VALIDATION PROMPT</span>
        <button class="btn btn--secondary btn--sm" @click="regenerate"><Icon name="history" :size="11" /> Regenerate</button>
      </div>
      <pre class="impv-mdcode">{{ testDoc }}</pre>
    </template>

    <!-- Step 4: Review -->
    <div v-if="step === 4" class="impv-review">
      <div class="impv-review__toolbar">
        <button class="btn btn--secondary btn--sm" @click="() => { expandAll = true; openSections = { requirements: true, implementation: true, testing: true }; }">+ Expand All</button>
        <span :style="{ marginLeft: 'auto', display: 'inline-flex', gap: '6px' }">
          <button class="btn btn--ghost btn--sm" @click="copyText(`${reqDoc}\n\n${implDoc}\n\n${testDoc}`, 'Action plan')">
            <Icon name="doc" :size="11" /> Copy to Clipboard
          </button>
          <button class="btn btn--ghost btn--sm" @click="exportMd">
            <Icon name="download" :size="11" /> Export (.md)
          </button>
        </span>
      </div>
      <div
        v-for="s in reviewSections"
        :key="s.k"
        :class="['impv-accord', { 'is-open': isSectionOpen(s.k) }]"
      >
        <div class="impv-accord__head" @click="openSections[s.k] = !openSections[s.k]">
          <Icon :name="isSectionOpen(s.k) ? 'chevron-down' : 'chevron-right'" :size="12" />
          <span class="impv-accord__title">{{ s.label }}</span>
          <span class="impv-accord__meta">{{ linesOf(s.doc) }} lines · generated 2m ago</span>
          <button class="btn btn--ghost btn--sm" @click.stop="copyText(s.doc, s.label)">
            <Icon name="doc" :size="11" /> Copy
          </button>
        </div>
        <pre v-if="isSectionOpen(s.k)" class="impv-mdcode impv-mdcode--inset">{{ s.doc }}</pre>
      </div>

      <div class="impv-admin">
        <div class="impv-admin__head">ADMIN CONTROLS</div>
        <div class="impv-admin__grid">
          <label>
            <span class="impv-lbl">Status</span>
            <select v-model="adminStatus" class="impv-input">
              <option>Pending</option><option>Under Review</option><option>Approved</option>
              <option>In Progress</option><option>Rolled out</option><option>Declined</option>
            </select>
          </label>
          <label>
            <span class="impv-lbl">Risk Level</span>
            <select v-model="adminRisk" class="impv-input">
              <option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option>
            </select>
          </label>
          <label :style="{ gridColumn: '1 / -1' }">
            <span class="impv-lbl">Target Version</span>
            <input v-model="adminVersion" placeholder="e.g. 3.12" class="impv-input" />
          </label>
          <label :style="{ gridColumn: '1 / -1' }">
            <span class="impv-lbl">Admin Notes</span>
            <textarea v-model="adminNotes" :rows="4" class="impv-input" :style="{ fontFamily: 'var(--font-mono)', fontSize: '12px', lineHeight: 1.55, resize: 'vertical' }" />
          </label>
        </div>
      </div>
    </div>
  </div>

  <div class="impv-nav">
    <button class="btn btn--secondary" :disabled="step === 0" @click="step = Math.max(0, step - 1)">‹ Back</button>
    <button
      v-if="step < 4"
      class="btn btn--primary"
      :style="{ background: 'var(--color-green)' }"
      @click="step = step + 1"
    >Next ›</button>
    <button
      v-else
      class="btn btn--primary"
      :style="{ background: 'var(--color-green)' }"
      @click="save"
    >Save Changes</button>
  </div>
</template>
