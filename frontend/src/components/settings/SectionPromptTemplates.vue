<script setup lang="ts">
/**
 * SectionPromptTemplates — Settings → Prompt templates.
 *
 * Phase 4 of the 2026-05-23 Settings BUILD remediation plan. Previously
 * rendered the @/fixtures/settings PROMPT_TEMPLATES array with warn-toast
 * no-op buttons; now hydrates from GET /v1/settings/templates and
 * persists Edit / Duplicate / Save / Delete via real CRUD endpoints
 * (migration 047 backs the prompt_templates table + seeds 8 system rows).
 *
 * Two kinds of templates share one table:
 *   processing — STT preset configs (filler, tone, terminology, etc.)
 *   ai_prompt  — Gemini system prompts (the literal prompt text)
 */
import { onMounted, ref, computed } from 'vue';
import FormRow from './FormRow.vue';
import TogglePill from './TogglePill.vue';
import {
  settingsApi,
  type PromptTemplate,
  type TemplateCreate,
  type TemplatePatch,
} from '@/services/api';
import { ApiError } from '@/services/http';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';

type View = 'catalog' | 'new' | 'edit';

const view = ref<View>('catalog');
const cats = ['Education', 'Technical', 'Conversational', 'Business', 'Custom'] as const;

const templates = ref<PromptTemplate[]>([]);
const loading = ref(true);
const saving = ref(false);

// Editing target: when view === 'edit', editingId names the row.
const editingId = ref<string | null>(null);

async function hydrate(): Promise<void> {
  loading.value = true;
  try {
    templates.value = await settingsApi.templatesList();
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Failed to load templates';
    toast.push(msg, { tone: 'error' });
  } finally {
    loading.value = false;
  }
}

onMounted(hydrate);

const processingTemplates = computed(() => templates.value.filter((t) => t.kind === 'processing'));
const aiPromptTemplates = computed(() => templates.value.filter((t) => t.kind === 'ai_prompt'));

function templatesInCategory(cat: string): PromptTemplate[] {
  return processingTemplates.value.filter((t) => t.category === cat);
}

function chipsFor(t: PromptTemplate): string[] {
  const c = t.config as { chips?: string[]; filler_policy?: string; tone?: string; terminology?: string };
  if (Array.isArray(c.chips) && c.chips.length > 0) return c.chips;
  // Fallback for templates created via the form that didn't pre-compute chips.
  const out: string[] = [];
  if (c.filler_policy) out.push(c.filler_policy.toLowerCase());
  if (c.tone) out.push(c.tone.toLowerCase());
  if (c.terminology) out.push(c.terminology.toLowerCase());
  return out;
}

function systemPromptFor(t: PromptTemplate): string {
  const c = t.config as { system_prompt?: string };
  return c.system_prompt ?? '';
}

function backToSettings(): void {
  // Lets the parent SettingsView restore its nav selection.
  history.back();
}

function goNew(): void {
  resetForm();
  view.value = 'new';
}

function backToCatalog(): void {
  editingId.value = null;
  view.value = 'catalog';
}

// ─── New / Edit form state ────────────────────────────────────────────
const ntype = ref<'processing' | 'ai_prompt'>('processing');
const nname = ref('');
const nicon = ref('📝');
const ndesc = ref('');
const ncat = ref<string>('Custom');
const nfiller = ref('Moderate');
const ntone = ref('Neutral');
const nterm = ref('Medium');
const nrewrite = ref('Minimal');
const nstructure = ref(true);
const nkeypoints = ref(true);
const nprompt = ref('');

function resetForm(): void {
  ntype.value = 'processing';
  nname.value = '';
  nicon.value = '📝';
  ndesc.value = '';
  ncat.value = 'Custom';
  nfiller.value = 'Moderate';
  ntone.value = 'Neutral';
  nterm.value = 'Medium';
  nrewrite.value = 'Minimal';
  nstructure.value = true;
  nkeypoints.value = true;
  nprompt.value = '';
}

function loadIntoForm(t: PromptTemplate): void {
  ntype.value = t.kind;
  nname.value = t.name;
  nicon.value = t.icon;
  ndesc.value = t.description ?? '';
  ncat.value = t.category;
  const c = t.config as Record<string, unknown>;
  nfiller.value = (c.filler_policy as string) ?? 'Moderate';
  ntone.value = (c.tone as string) ?? 'Neutral';
  nterm.value = (c.terminology as string) ?? 'Medium';
  nrewrite.value = (c.rewrite_level as string) ?? 'Minimal';
  nstructure.value = c.structure !== false;
  nkeypoints.value = c.keypoints !== false;
  nprompt.value = (c.system_prompt as string) ?? '';
}

function buildConfig(): Record<string, unknown> {
  if (ntype.value === 'ai_prompt') {
    return { system_prompt: nprompt.value };
  }
  return {
    filler_policy: nfiller.value,
    tone:          ntone.value,
    terminology:   nterm.value,
    rewrite_level: nrewrite.value,
    structure:     nstructure.value,
    keypoints:     nkeypoints.value,
    // Display chips computed from the choices the operator just made so the
    // catalog card matches what they configured.
    chips: [
      nfiller.value.toLowerCase(),
      ntone.value.toLowerCase(),
      nterm.value.toLowerCase(),
      ...(nstructure.value ? ['structure'] : []),
      ...(nkeypoints.value ? ['key points'] : []),
    ],
  };
}

async function saveNew(): Promise<void> {
  if (!nname.value.trim()) {
    toast.push('Template name is required', { tone: 'warn' });
    return;
  }
  if (saving.value) return;
  saving.value = true;
  try {
    const payload: TemplateCreate = {
      kind:        ntype.value,
      name:        nname.value.trim(),
      icon:        nicon.value || '📝',
      description: ndesc.value || undefined,
      category:    ncat.value,
      config:      buildConfig(),
    };
    const created = await settingsApi.templatesAdd(payload);
    templates.value = [created, ...templates.value];
    toast.push(`Created ${created.name}`, { tone: 'success' });
    resetForm();
    view.value = 'catalog';
  } catch (e) {
    surfaceError(e, 'Failed to create template');
  } finally {
    saving.value = false;
  }
}

async function saveEdit(): Promise<void> {
  if (!editingId.value) return;
  if (!nname.value.trim()) {
    toast.push('Template name is required', { tone: 'warn' });
    return;
  }
  if (saving.value) return;
  saving.value = true;
  try {
    const patch: TemplatePatch = {
      name:        nname.value.trim(),
      icon:        nicon.value || '📝',
      description: ndesc.value || undefined,
      category:    ncat.value,
      config:      buildConfig(),
    };
    const updated = await settingsApi.templatesUpdate(editingId.value, patch);
    templates.value = templates.value.map((t) => (t.id === updated.id ? updated : t));
    toast.push(`Saved ${updated.name}`, { tone: 'success' });
    editingId.value = null;
    view.value = 'catalog';
  } catch (e) {
    surfaceError(e, 'Failed to save template');
  } finally {
    saving.value = false;
  }
}

function editTemplate(t: PromptTemplate): void {
  loadIntoForm(t);
  editingId.value = t.id;
  view.value = 'edit';
}

async function duplicateTemplate(t: PromptTemplate): Promise<void> {
  if (saving.value) return;
  saving.value = true;
  try {
    const payload: TemplateCreate = {
      kind:        t.kind,
      name:        `${t.name} (copy)`,
      icon:        t.icon,
      description: t.description ?? undefined,
      category:    t.category,
      config:      { ...t.config },
    };
    const created = await settingsApi.templatesAdd(payload);
    templates.value = [created, ...templates.value];
    toast.push(`Duplicated ${t.name}`, { tone: 'success' });
  } catch (e) {
    surfaceError(e, 'Failed to duplicate template');
  } finally {
    saving.value = false;
  }
}

async function removeTemplate(t: PromptTemplate): Promise<void> {
  if (t.is_system) {
    toast.push('System templates cannot be deleted. Duplicate to make an editable copy.', { tone: 'warn' });
    return;
  }
  const ok = await confirm.open({
    title:        `Delete ${t.name}?`,
    body:         'This soft-deletes the template; its history stays in the audit log.',
    danger:       true,
    confirmLabel: 'Delete',
  });
  if (!ok) return;
  try {
    await settingsApi.templatesRemove(t.id);
    templates.value = templates.value.filter((x) => x.id !== t.id);
    toast.push(`Deleted ${t.name}`, { tone: 'success' });
  } catch (e) {
    surfaceError(e, 'Failed to delete template');
  }
}

function surfaceError(e: unknown, fallback: string): void {
  if (e instanceof ApiError) {
    const body = e.body as { detail?: { message?: string; code?: string } | string } | undefined;
    const detail = body?.detail;
    if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
      toast.push(detail.message, { tone: 'error' });
      return;
    }
    if (typeof detail === 'string') {
      toast.push(`${e.status} — ${detail}`, { tone: 'error' });
      return;
    }
    toast.push(`${e.status} — ${e.message}`, { tone: 'error' });
    return;
  }
  toast.push(fallback, { tone: 'error' });
}
</script>

<template>
  <template v-if="view === 'catalog'">
    <div class="set-subnav">
      <button class="set-link" @click="backToSettings">← Settings</button>
      <h2 :style="{ margin: 0, fontSize: '24px', fontWeight: 800 }">Templates</h2>
      <em v-if="loading" :style="{ marginLeft: '12px', fontSize: '12px', color: 'var(--fg2)' }">loading…</em>
      <button
        class="btn sugg-modal__submit"
        :style="{ marginLeft: 'auto' }"
        data-test-id="template-new"
        @click="goNew"
      >+ New Template</button>
    </div>

    <h3 class="set-section-title" :style="{ marginTop: '12px' }">Processing Templates (STT Pipeline)</h3>
    <p :style="{ color: 'var(--fg2)', fontSize: '13px', margin: '0 0 18px' }">
      Control filler removal, tone, terminology for standard speech-to-text processing
    </p>
    <template v-for="cat in cats" :key="cat">
      <div v-if="templatesInCategory(cat).length" :style="{ marginBottom: '18px' }">
        <div class="set-eyebrow" :style="{ marginBottom: '8px' }">{{ cat.toUpperCase() }}</div>
        <div
          v-for="t in templatesInCategory(cat)"
          :key="t.id"
          class="set-tpl-card"
        >
          <div :style="{ fontSize: '22px' }">{{ t.icon }}</div>
          <div :style="{ flex: 1, minWidth: 0 }">
            <div class="set-tpl-card__name">{{ t.name }}</div>
            <div class="set-tpl-card__desc">{{ t.description }}</div>
            <div class="set-tpl-card__chips">
              <code v-for="c in chipsFor(t)" :key="c">{{ c }}</code>
            </div>
          </div>
          <span class="set-tpl-card__tag set-tpl-card__tag--iil">IIL</span>
          <span v-if="t.is_system" class="set-tpl-card__tag">System</span>
          <button class="set-link" @click="editTemplate(t)">Edit</button>
          <button class="set-link" @click="duplicateTemplate(t)">Duplicate</button>
          <button
            v-if="!t.is_system"
            class="set-link set-link--danger"
            @click="removeTemplate(t)"
          >Delete</button>
        </div>
      </div>
    </template>

    <h3 class="set-section-title" :style="{ marginTop: '28px' }">AI Prompt Templates (Gemini)</h3>
    <p :style="{ color: 'var(--fg2)', fontSize: '13px', margin: '0 0 18px' }">
      Define the system prompt sent to Gemini for AI MODE processing
    </p>
    <div
      v-for="t in aiPromptTemplates"
      :key="t.id"
      class="set-tpl-card"
    >
      <div :style="{ fontSize: '22px' }">{{ t.icon }}</div>
      <div :style="{ flex: 1 }">
        <div class="set-tpl-card__name">{{ t.name }}</div>
        <div class="set-tpl-card__desc">{{ t.description }}</div>
        <pre v-if="systemPromptFor(t)" class="set-tpl-card__code">{{ systemPromptFor(t) }}</pre>
      </div>
      <span class="set-tpl-card__tag set-tpl-card__tag--iil">Prompt</span>
      <span v-if="t.is_system" class="set-tpl-card__tag">System</span>
      <button class="set-link" @click="editTemplate(t)">Edit</button>
      <button class="set-link" @click="duplicateTemplate(t)">Duplicate</button>
      <button
        v-if="!t.is_system"
        class="set-link set-link--danger"
        @click="removeTemplate(t)"
      >Delete</button>
    </div>
  </template>

  <template v-else>
    <div class="set-subnav">
      <button class="set-link" @click="backToCatalog">← Templates</button>
      <h2 :style="{ margin: 0, fontSize: '24px', fontWeight: 800 }">
        {{ view === 'edit' ? 'Edit Template' : 'New Template' }}
      </h2>
    </div>
    <div class="set-pane" :style="{ padding: '22px' }">
      <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }">
        <h3 :style="{ margin: 0, fontSize: '18px', fontWeight: 700 }">
          {{ view === 'edit' ? nname : 'New Template' }}
        </h3>
        <div :style="{ display: 'flex', gap: '8px' }">
          <button class="btn btn--secondary" @click="backToCatalog">Cancel</button>
          <button
            class="btn sugg-modal__submit"
            :disabled="saving"
            data-test-id="template-save"
            @click="view === 'edit' ? saveEdit() : saveNew()"
          >{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </div>
      <FormRow label="Type">
        <select v-model="ntype" class="set-input" :disabled="view === 'edit'">
          <option value="processing">Processing Template (STT/IIL)</option>
          <option value="ai_prompt">AI Prompt Template (Gemini)</option>
        </select>
      </FormRow>
      <FormRow label="Name"><input v-model="nname" class="set-input" placeholder="Template name" /></FormRow>
      <FormRow label="Icon"><input v-model="nicon" class="set-input" :style="{ maxWidth: '80px' }" /></FormRow>
      <FormRow label="Description"><input v-model="ndesc" class="set-input" placeholder="Brief description" /></FormRow>
      <FormRow label="Category">
        <select v-model="ncat" class="set-input">
          <option>Education</option><option>Technical</option><option>Conversational</option><option>Business</option><option>Custom</option>
        </select>
      </FormRow>

      <template v-if="ntype === 'processing'">
        <div class="set-eyebrow" :style="{ marginTop: '24px', marginBottom: '14px', color: 'var(--text-accent)' }">IIL CONFIGURATION</div>
        <FormRow label="Filler policy">
          <select v-model="nfiller" class="set-input"><option>Strict</option><option>Moderate</option><option>Light</option></select>
        </FormRow>
        <FormRow label="Tone">
          <select v-model="ntone" class="set-input"><option>Neutral</option><option>Conversational</option><option>Formal</option><option>Persuasive</option></select>
        </FormRow>
        <FormRow label="Terminology">
          <select v-model="nterm" class="set-input"><option>Strict</option><option>Medium</option><option>Loose</option></select>
        </FormRow>
        <FormRow label="Rewrite level">
          <select v-model="nrewrite" class="set-input"><option>Minimal</option><option>Moderate</option><option>Aggressive</option></select>
        </FormRow>
        <FormRow label="Structure extraction">
          <template #control>
            <TogglePill :on="nstructure" @update:on="(v) => (nstructure = v)" />
          </template>
        </FormRow>
        <FormRow label="Key points">
          <template #control>
            <TogglePill :on="nkeypoints" @update:on="(v) => (nkeypoints = v)" />
          </template>
        </FormRow>
      </template>

      <template v-else>
        <div class="set-eyebrow" :style="{ marginTop: '24px', marginBottom: '6px' }">SYSTEM PROMPT</div>
        <div :style="{ fontSize: '12px', color: 'var(--fg2)', marginBottom: '8px' }">
          The prompt sent to Gemini for AI MODE processing. Leave empty to use the default.
        </div>
        <textarea
          v-model="nprompt"
          class="set-input"
          :rows="12"
          placeholder="Enter system prompt."
          :style="{ fontFamily: 'var(--font-mono)', fontSize: '12.5px', lineHeight: 1.6, resize: 'vertical' }"
        />
        <div :style="{ textAlign: 'right', fontSize: '11px', color: 'var(--fg2)', marginTop: '4px' }">
          {{ nprompt.length }} characters
        </div>
      </template>
    </div>
  </template>
</template>
