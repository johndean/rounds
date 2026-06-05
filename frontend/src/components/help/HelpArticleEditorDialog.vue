<script setup lang="ts">
/**
 * frontend/src/components/help/HelpArticleEditorDialog.vue
 *
 * Purpose:
 *     Modal for creating or editing a help article. Fields:
 *       title, summary, category, content_domain, audience (users/admin),
 *       feature_tags (multi-select chips), is_published toggle, steps[]
 *       (numbered cards with title+body, move-up/down reorder, X8),
 *       related_article_ids (multi-select picker, X7).
 *
 *     On save: emits `saved` with the returned article; parent closes
 *     the dialog. On error: surfaces a toast and keeps the dialog open
 *     so the admin can retry.
 *
 *     Field validation is client-side soft (Save disabled until title is
 *     non-empty) + backend-authoritative (Pydantic min_length=1 catches
 *     anything that slips through).
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §8.3
 */
import { computed, ref, watch } from 'vue';
import { createArticle, updateArticle, type HelpArticleDTO, type HelpStep } from '@/services/helpArticlesApi';
import { toast } from '@/composables/useToast';
import Icon from '@/components/shared/Icon.vue';

interface Props {
  open: boolean;
  article: HelpArticleDTO | null; // null = create mode; non-null = edit mode
  allArticles: HelpArticleDTO[];  // for the related-articles picker
}
const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'saved', article: HelpArticleDTO): void;
}>();

const KNOWN_DOMAINS = ['general', 'dashboard', 'sessions', 'editor', 'sop', 'processing', 'improvements', 'settings'];
const KNOWN_FEATURE_TAGS = ['dashboard', 'sessions', 'session-detail', 'editor', 'sop', 'upload', 'improvements', 'settings', 'audit', 'viewer', 'processing', 'help'];

// Local form state
const title = ref('');
const summary = ref('');
const category = ref('general');
const audience = ref<'users' | 'admin'>('users');
const featureTagInput = ref('');
const featureTags = ref<string[]>([]);
const contentDomain = ref('general');
const isPublished = ref(false);
const displayOrder = ref(0);
const workflowSlug = ref('');
const steps = ref<HelpStep[]>([]);
const relatedIds = ref<string[]>([]);
const saving = ref(false);

const isEdit = computed(() => props.article !== null);
const canSave = computed(() => title.value.trim().length > 0 && !saving.value);

function resetForm(): void {
  const a = props.article;
  title.value = a?.title ?? '';
  summary.value = a?.summary ?? '';
  category.value = a?.category ?? 'general';
  audience.value = a?.audience ?? 'users';
  featureTags.value = [...(a?.feature_tags ?? [])];
  featureTagInput.value = '';
  contentDomain.value = a?.content_domain ?? 'general';
  isPublished.value = a?.is_published ?? false;
  displayOrder.value = a?.display_order ?? 0;
  workflowSlug.value = a?.workflow_slug ?? '';
  steps.value = a?.steps ? a.steps.map((s) => ({ ...s })) : [];
  relatedIds.value = [...(a?.related_article_ids ?? [])];
}

watch(() => [props.open, props.article], () => {
  if (props.open) resetForm();
});

// ── Feature tags ─────────────────────────────────────────────────────
function addFeatureTag(tag: string): void {
  const t = tag.trim().toLowerCase();
  if (!t || featureTags.value.includes(t)) return;
  featureTags.value.push(t);
  featureTagInput.value = '';
}
function removeFeatureTag(t: string): void {
  featureTags.value = featureTags.value.filter((x) => x !== t);
}
function onTagKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault();
    addFeatureTag(featureTagInput.value);
  }
}

// ── Steps ────────────────────────────────────────────────────────────
function addStep(): void {
  steps.value.push({ title: '', body: '' });
}
function removeStep(i: number): void {
  steps.value.splice(i, 1);
}
function moveStep(i: number, dir: -1 | 1): void {
  const j = i + dir;
  if (j < 0 || j >= steps.value.length) return;
  const tmp = steps.value[i];
  steps.value[i] = steps.value[j];
  steps.value[j] = tmp;
}

// ── Related articles picker ──────────────────────────────────────────
function toggleRelated(id: string): void {
  if (relatedIds.value.includes(id)) {
    relatedIds.value = relatedIds.value.filter((x) => x !== id);
  } else if (relatedIds.value.length < 5) {
    relatedIds.value.push(id);
  } else {
    toast.push('Max 5 related articles.', { tone: 'warn' });
  }
}
const otherArticles = computed(() =>
  props.allArticles.filter((a) => a.id !== props.article?.id),
);

// ── Save ─────────────────────────────────────────────────────────────
async function save(): Promise<void> {
  if (!canSave.value) return;
  saving.value = true;
  // Filter out empty steps before submit.
  const cleanedSteps = steps.value.filter((s) => s.title.trim() || s.body.trim());
  const payload = {
    title: title.value.trim(),
    summary: summary.value.trim(),
    category: category.value.trim() || 'general',
    audience: audience.value,
    feature_tags: featureTags.value,
    steps: cleanedSteps,
    related_article_ids: relatedIds.value,
    display_order: displayOrder.value,
    is_published: isPublished.value,
    content_domain: contentDomain.value,
    workflow_slug: workflowSlug.value.trim() || null,
  };
  try {
    const saved = isEdit.value
      ? await updateArticle(props.article!.id, payload)
      : await createArticle(payload);
    toast.push(isEdit.value ? 'Article saved.' : 'Article created.', { tone: 'success' });
    emit('saved', saved);
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Save failed', { tone: 'error' });
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="art-mask" role="dialog" aria-modal="true" @click.self="emit('close')">
      <div class="art-dialog">
        <div class="art-head">
          <h2 class="art-title">{{ isEdit ? 'Edit article' : 'New article' }}</h2>
          <button class="art-close" type="button" aria-label="Close" @click="emit('close')">
            <Icon name="x" :size="14" />
          </button>
        </div>

        <div class="art-body">
          <!-- Title -->
          <div class="art-field">
            <label class="art-label">Title</label>
            <input v-model="title" class="art-input" type="text" placeholder="How do I…" />
          </div>

          <!-- Summary -->
          <div class="art-field">
            <label class="art-label">Summary</label>
            <textarea v-model="summary" class="art-input" rows="3" placeholder="Plain-English answer in 2–4 sentences." />
          </div>

          <!-- Category + Content domain + Audience + Published -->
          <div class="art-grid">
            <div class="art-field">
              <label class="art-label">Category</label>
              <input v-model="category" class="art-input" type="text" placeholder="page:editor / faq:processing / general" />
            </div>
            <div class="art-field">
              <label class="art-label">Content domain</label>
              <select v-model="contentDomain" class="art-input">
                <option v-for="d in KNOWN_DOMAINS" :key="d" :value="d">{{ d }}</option>
              </select>
            </div>
            <div class="art-field">
              <label class="art-label">Audience</label>
              <select v-model="audience" class="art-input">
                <option value="users">users</option>
                <option value="admin">admin</option>
              </select>
            </div>
            <div class="art-field">
              <label class="art-label">Published</label>
              <label class="art-toggle">
                <input type="checkbox" v-model="isPublished" />
                <span>{{ isPublished ? 'Yes — visible to users' : 'No — draft only' }}</span>
              </label>
            </div>
          </div>

          <!-- Feature tags -->
          <div class="art-field">
            <label class="art-label">Feature tags (per-page filter)</label>
            <div class="art-chips">
              <span v-for="t in featureTags" :key="t" class="art-chip">
                {{ t }}
                <button type="button" class="art-chip__x" aria-label="Remove tag" @click="removeFeatureTag(t)">
                  <Icon name="x" :size="10" />
                </button>
              </span>
              <input
                v-model="featureTagInput"
                class="art-chips__input"
                type="text"
                placeholder="Type a tag + Enter (e.g. editor)"
                @keydown="onTagKeydown"
              />
            </div>
            <div class="art-hint">
              Suggested:
              <button
                v-for="s in KNOWN_FEATURE_TAGS.filter(s => !featureTags.includes(s))"
                :key="s"
                type="button"
                class="art-hint__chip"
                @click="addFeatureTag(s)"
              >+ {{ s }}</button>
            </div>
          </div>

          <!-- Numbered steps -->
          <div class="art-field">
            <label class="art-label">Steps (numbered)</label>
            <div v-if="steps.length === 0" class="art-empty-steps">
              No steps yet. Steps render as a numbered list under the summary.
            </div>
            <ol class="art-steps">
              <li v-for="(s, i) in steps" :key="i" class="art-step">
                <div class="art-step__head">
                  <span class="art-step__n">{{ i + 1 }}</span>
                  <input v-model="s.title" class="art-input" type="text" placeholder="Step title" />
                  <button type="button" class="art-step__btn" aria-label="Move up" :disabled="i === 0" @click="moveStep(i, -1)">
                    <Icon name="chevron-down" :size="10" :class="'rot-180'" /><span class="sr">Up</span>
                  </button>
                  <button type="button" class="art-step__btn" aria-label="Move down" :disabled="i === steps.length - 1" @click="moveStep(i, 1)">
                    <Icon name="chevron-down" :size="10" /><span class="sr">Down</span>
                  </button>
                  <button type="button" class="art-step__btn art-step__btn--danger" aria-label="Remove step" @click="removeStep(i)">
                    <Icon name="x" :size="10" />
                  </button>
                </div>
                <textarea v-model="s.body" class="art-input" rows="2" placeholder="What the user does." />
              </li>
            </ol>
            <button type="button" class="art-addstep" @click="addStep">+ Add step</button>
          </div>

          <!-- Related articles -->
          <div class="art-field">
            <label class="art-label">Related articles (cross-links, max 5)</label>
            <div v-if="otherArticles.length === 0" class="art-hint">No other articles yet.</div>
            <div v-else class="art-related-picker">
              <button
                v-for="a in otherArticles"
                :key="a.id"
                type="button"
                :class="['art-related-row', { 'is-selected': relatedIds.includes(a.id) }]"
                @click="toggleRelated(a.id)"
              >
                <span class="art-related-row__check">
                  <Icon v-if="relatedIds.includes(a.id)" name="check" :size="12" />
                </span>
                <span class="art-related-row__title">{{ a.title }}</span>
                <span class="art-related-row__meta">{{ a.content_domain }}</span>
              </button>
            </div>
          </div>

          <!-- Display order + workflow slug (advanced) -->
          <details class="art-advanced">
            <summary>Advanced</summary>
            <div class="art-grid">
              <div class="art-field">
                <label class="art-label">Display order</label>
                <input v-model.number="displayOrder" class="art-input" type="number" min="0" />
              </div>
              <div class="art-field">
                <label class="art-label">Workflow slug (SOP variant)</label>
                <input v-model="workflowSlug" class="art-input" type="text" placeholder="optional" />
              </div>
            </div>
          </details>
        </div>

        <div class="art-foot">
          <button class="art-btn" type="button" @click="emit('close')">Cancel</button>
          <button class="art-btn art-btn--primary" type="button" :disabled="!canSave" @click="save">
            {{ saving ? 'Saving…' : isEdit ? 'Save changes' : 'Create article' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.art-mask {
  position: fixed; inset: 0;
  background: rgba(0, 20, 50, 0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 900;
}
.art-dialog {
  width: min(800px, 94vw);
  max-height: 92vh;
  background: var(--color-white);
  border-radius: 12px;
  box-shadow: 0 24px 60px rgba(0, 40, 85, 0.25);
  display: flex; flex-direction: column;
}
.art-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-subtle);
}
.art-title { margin: 0; font-size: 16px; font-weight: 800; color: var(--color-navy); }
.art-close {
  width: 28px; height: 28px;
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
  background: transparent;
  color: var(--color-steel);
  cursor: pointer;
}
.art-body {
  flex: 1; overflow-y: auto;
  padding: 18px 20px;
  display: flex; flex-direction: column; gap: 14px;
}
.art-field { display: flex; flex-direction: column; gap: 6px; }
.art-label {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-steel);
}
.art-input {
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  font-family: inherit;
  color: var(--color-navy);
  width: 100%;
}
.art-input:focus {
  outline: none;
  border-color: var(--color-blue);
  background: var(--color-white);
}
.art-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.art-toggle {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px;
  color: var(--color-navy);
  padding-top: 6px;
}
.art-toggle input { width: 16px; height: 16px; }

.art-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 6px;
  min-height: 38px;
}
.art-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--color-navy);
  color: #fff;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 4px 3px 10px;
}
.art-chip__x {
  display: inline-flex;
  align-items: center; justify-content: center;
  background: rgba(255, 255, 255, 0.15);
  border: none;
  border-radius: 50%;
  width: 16px; height: 16px;
  color: #fff;
  cursor: pointer;
}
.art-chips__input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-size: 12px;
  color: var(--color-navy);
  min-width: 120px;
}
.art-hint {
  font-size: 11px;
  color: var(--color-steel);
  margin-top: 4px;
  display: flex; flex-wrap: wrap; gap: 4px; align-items: center;
}
.art-hint__chip {
  background: transparent;
  border: 1px dashed var(--border-subtle);
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 10px;
  color: var(--color-steel);
  cursor: pointer;
}
.art-hint__chip:hover { color: var(--color-navy); border-color: var(--color-blue); }

.art-empty-steps {
  font-size: 12px;
  color: var(--color-steel);
  background: var(--color-off-white);
  border: 1px dashed var(--border-subtle);
  border-radius: 6px;
  padding: 10px 12px;
}
.art-steps { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.art-step {
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 8px 10px;
  display: flex; flex-direction: column; gap: 6px;
}
.art-step__head {
  display: flex; align-items: center; gap: 6px;
}
.art-step__n {
  display: inline-flex;
  align-items: center; justify-content: center;
  width: 24px; height: 24px;
  background: var(--color-navy);
  color: #fff;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 800;
  flex-shrink: 0;
}
.art-step__btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 24px; height: 24px;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--color-steel);
  cursor: pointer;
}
.art-step__btn:hover { color: var(--color-navy); background: var(--color-light-steel); }
.art-step__btn:disabled { opacity: 0.4; cursor: not-allowed; }
.art-step__btn--danger:hover { color: #b91c1c; }
.rot-180 { transform: rotate(180deg); }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); }
.art-addstep {
  align-self: flex-start;
  background: transparent;
  border: 1px dashed var(--border-subtle);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--color-steel);
  font-weight: 700;
  cursor: pointer;
}
.art-addstep:hover { color: var(--color-navy); border-color: var(--color-blue); }

.art-related-picker {
  display: flex; flex-direction: column; gap: 4px;
  max-height: 220px; overflow-y: auto;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 6px;
  background: var(--color-off-white);
}
.art-related-row {
  display: flex; align-items: center; gap: 8px;
  text-align: left;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 6px 8px;
  font-size: 12px;
  color: var(--color-navy);
  cursor: pointer;
}
.art-related-row:hover { background: var(--color-white); }
.art-related-row.is-selected {
  background: var(--color-white);
  border-color: var(--color-blue);
}
.art-related-row__check {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  color: var(--color-blue);
  flex-shrink: 0;
}
.art-related-row.is-selected .art-related-row__check {
  background: var(--color-blue);
  border-color: var(--color-blue);
  color: #fff;
}
.art-related-row__title { flex: 1; font-weight: 700; }
.art-related-row__meta { font-size: 11px; color: var(--color-steel); font-family: var(--font-mono); }

.art-advanced > summary {
  cursor: pointer;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-steel);
  padding: 4px 0;
}

.art-foot {
  border-top: 1px solid var(--border-subtle);
  padding: 12px 20px;
  display: flex; justify-content: flex-end; gap: 8px;
}
.art-btn {
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 700;
  color: var(--color-navy);
  cursor: pointer;
}
.art-btn:hover { background: var(--color-white); }
.art-btn--primary {
  background: var(--color-navy);
  color: #fff;
  border-color: var(--color-navy);
}
.art-btn--primary:hover { background: var(--color-navy-deep); }
.art-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
