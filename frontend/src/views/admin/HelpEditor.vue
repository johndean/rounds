<script setup lang="ts">
/**
 * frontend/src/views/admin/HelpEditor.vue
 *
 * Purpose:
 *     Admin Help Center CMS — the page operators use to author, edit,
 *     publish, archive, and version help articles. Lives at /admin/help
 *     and is gated by both a router beforeEach guard AND the v-if check
 *     inside the page (defense in depth).
 *
 *     Phase 3 ships:
 *       - Full article list with filter chips (audience + content_domain)
 *       - Coverage report at the top
 *       - New / Edit / Archive / Version history actions per row
 *       - Article editor dialog (HelpArticleEditorDialog.vue)
 *       - Version history dialog (HelpVersionHistoryDialog.vue)
 *
 *     Phase 4 will add the bulk-AI toolbar buttons (Fix CC-Rounds, etc.).
 *     Phase 5 will add the AI-generated FAQ corpus seed action.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §8.3
 */
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useIsAdmin } from '@/composables/useIsAdmin';
import { listArticles, archiveArticle, type HelpArticleDTO } from '@/services/helpArticlesApi';
import { toast } from '@/composables/useToast';
import Icon from '@/components/shared/Icon.vue';
import HelpAdminToolbar from '@/components/help/HelpAdminToolbar.vue';
import HelpCoverageReport from '@/components/help/HelpCoverageReport.vue';
import HelpArticleEditorDialog from '@/components/help/HelpArticleEditorDialog.vue';
import HelpVersionHistoryDialog from '@/components/help/HelpVersionHistoryDialog.vue';

const router = useRouter();
const isAdmin = useIsAdmin();

const articles = ref<HelpArticleDTO[]>([]);
const loading = ref(false);
const err = ref<string | null>(null);

const filterAudience = ref<'all' | 'users' | 'admin'>('all');
const filterDomain = ref<string>('');
const filterStatus = ref<'all' | 'published' | 'drafts'>('all');
const search = ref('');

const editorOpen = ref(false);
const editorTarget = ref<HelpArticleDTO | null>(null);
const historyOpen = ref(false);
const historyTarget = ref<HelpArticleDTO | null>(null);

const coverageRef = ref<{ refresh: () => Promise<void> } | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  err.value = null;
  try {
    // Admins see everything; pass audience filter only when narrowing.
    articles.value = await listArticles({
      audience: filterAudience.value === 'all' ? undefined : filterAudience.value,
      content_domain: filterDomain.value || undefined,
      limit: 500,
    });
  } catch (e) {
    err.value = e instanceof Error ? e.message : 'Failed to load articles';
  } finally {
    loading.value = false;
  }
}

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase();
  return articles.value.filter((a) => {
    if (filterStatus.value === 'published' && !a.is_published) return false;
    if (filterStatus.value === 'drafts' && a.is_published) return false;
    if (!q) return true;
    return (
      a.title.toLowerCase().includes(q) ||
      a.summary.toLowerCase().includes(q) ||
      a.slug.toLowerCase().includes(q)
    );
  });
});

const domains = computed(() => {
  const set = new Set<string>();
  for (const a of articles.value) set.add(a.content_domain);
  return Array.from(set).sort();
});

function openNew(): void {
  editorTarget.value = null;
  editorOpen.value = true;
}
function openEdit(a: HelpArticleDTO): void {
  editorTarget.value = a;
  editorOpen.value = true;
}
function openHistory(a: HelpArticleDTO): void {
  historyTarget.value = a;
  historyOpen.value = true;
}

function onSaved(saved: HelpArticleDTO): void {
  // Upsert into the local list.
  const i = articles.value.findIndex((a) => a.id === saved.id);
  if (i >= 0) articles.value[i] = saved;
  else articles.value = [saved, ...articles.value];
  editorOpen.value = false;
  void coverageRef.value?.refresh();
}

async function onArchive(a: HelpArticleDTO): Promise<void> {
  if (!confirm(`Archive "${a.title}"? Sets is_published=false; the article + its version history are preserved.`)) return;
  try {
    const updated = await archiveArticle(a.id);
    const i = articles.value.findIndex((x) => x.id === updated.id);
    if (i >= 0) articles.value[i] = updated;
    toast.push('Archived.', { tone: 'success' });
    void coverageRef.value?.refresh();
  } catch (e) {
    toast.push(e instanceof Error ? e.message : 'Archive failed', { tone: 'error' });
  }
}

function onRestored(restored: HelpArticleDTO): void {
  const i = articles.value.findIndex((a) => a.id === restored.id);
  if (i >= 0) articles.value[i] = restored;
  void coverageRef.value?.refresh();
}

onMounted(() => {
  if (!isAdmin.value) {
    // Defense in depth — the router guard should have redirected, but
    // catch the case where it didn't.
    void router.replace('/dashboard');
    return;
  }
  void load();
});
</script>

<template>
  <div class="hed">
    <div v-if="!isAdmin" class="hed__forbidden">Admin only.</div>
    <template v-else>
      <header class="hed__head">
        <div>
          <div class="hed__overline">Admin</div>
          <h1 class="hed__title">Help Editor</h1>
          <p class="hed__desc">
            Author, edit, and publish the help articles end users see in the in-app Help Center.
            Edits are versioned automatically — every save snapshots the prior state.
          </p>
        </div>
      </header>

      <HelpAdminToolbar @new="openNew" @refresh="load" />

      <HelpCoverageReport ref="coverageRef" />

      <!-- Filters -->
      <div class="hed__filters">
        <div class="hed__filter">
          <label class="hed__filter-label">Audience</label>
          <select v-model="filterAudience" class="hed__select" @change="load">
            <option value="all">All</option>
            <option value="users">users</option>
            <option value="admin">admin</option>
          </select>
        </div>
        <div class="hed__filter">
          <label class="hed__filter-label">Domain</label>
          <select v-model="filterDomain" class="hed__select" @change="load">
            <option value="">All</option>
            <option v-for="d in domains" :key="d" :value="d">{{ d }}</option>
          </select>
        </div>
        <div class="hed__filter">
          <label class="hed__filter-label">Status</label>
          <select v-model="filterStatus" class="hed__select">
            <option value="all">All</option>
            <option value="published">Published</option>
            <option value="drafts">Drafts</option>
          </select>
        </div>
        <div class="hed__filter hed__filter--grow">
          <label class="hed__filter-label">Search</label>
          <input
            v-model="search"
            class="hed__select"
            type="text"
            placeholder="Filter by title, summary, or slug"
          />
        </div>
      </div>

      <!-- List -->
      <div v-if="err" class="hed__err">{{ err }}</div>
      <div v-else-if="loading && articles.length === 0" class="hed__loading">Loading…</div>
      <div v-else-if="filtered.length === 0" class="hed__empty">
        No articles match the current filters.
      </div>
      <ul v-else class="hed__list">
        <li v-for="a in filtered" :key="a.id" class="hed__row">
          <div class="hed__row-main">
            <div class="hed__row-head">
              <h3 class="hed__row-title">{{ a.title }}</h3>
              <span :class="['hed__pill', a.is_published ? 'is-published' : 'is-draft']">
                {{ a.is_published ? 'Published' : 'Draft' }}
              </span>
              <span class="hed__pill hed__pill--ghost">{{ a.audience }}</span>
              <span class="hed__pill hed__pill--ghost">{{ a.content_domain }}</span>
              <span class="hed__pill hed__pill--ghost">v{{ a.version }}</span>
            </div>
            <p v-if="a.summary" class="hed__row-summary">{{ a.summary }}</p>
            <div class="hed__row-meta">
              <span class="hed__slug">{{ a.slug }}</span>
              <span v-if="a.last_edited_by">· edited by {{ a.last_edited_by }}</span>
              <span v-if="a.updated_at">· {{ new Date(a.updated_at).toLocaleString() }}</span>
            </div>
          </div>
          <div class="hed__row-actions">
            <button class="hed__act" type="button" @click="openEdit(a)">
              <Icon name="edit" :size="12" /> Edit
            </button>
            <button class="hed__act" type="button" @click="openHistory(a)">
              <Icon name="history" :size="12" /> History
            </button>
            <button v-if="a.is_published" class="hed__act hed__act--danger" type="button" @click="onArchive(a)">
              <Icon name="x" :size="12" /> Archive
            </button>
          </div>
        </li>
      </ul>

      <HelpArticleEditorDialog
        :open="editorOpen"
        :article="editorTarget"
        :all-articles="articles"
        @close="editorOpen = false"
        @saved="onSaved"
      />
      <HelpVersionHistoryDialog
        v-if="historyTarget"
        :open="historyOpen"
        :article-id="historyTarget.id"
        @close="historyOpen = false"
        @restored="onRestored"
      />
    </template>
  </div>
</template>

<style scoped>
.hed {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 24px 48px;
}
.hed__forbidden {
  padding: 80px 24px;
  text-align: center;
  font-size: 14px;
  color: var(--color-steel);
}
.hed__head { margin-bottom: 16px; }
.hed__overline {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-gold);
}
.hed__title {
  margin: 4px 0 6px;
  font-size: 22px;
  font-weight: 800;
  color: var(--color-navy);
}
.hed__desc {
  margin: 0;
  font-size: 13px;
  color: var(--color-steel);
  line-height: 1.5;
  max-width: 720px;
}

.hed__filters {
  display: grid;
  grid-template-columns: repeat(3, 160px) 1fr;
  gap: 10px;
  margin: 14px 0;
}
.hed__filter { display: flex; flex-direction: column; gap: 4px; }
.hed__filter--grow { min-width: 0; }
.hed__filter-label {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-steel);
}
.hed__select {
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 7px 10px;
  font-size: 12px;
  color: var(--color-navy);
  font-family: inherit;
  width: 100%;
}
.hed__err { color: #b91c1c; font-size: 13px; padding: 12px 0; }
.hed__loading, .hed__empty { color: var(--color-steel); font-size: 13px; padding: 18px 0; }

.hed__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.hed__row {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  background: var(--color-white);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  align-items: flex-start;
}
.hed__row-main { flex: 1; min-width: 0; }
.hed__row-head {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-bottom: 4px;
}
.hed__row-title {
  margin: 0;
  font-size: 14px;
  font-weight: 800;
  color: var(--color-navy);
}
.hed__pill {
  display: inline-flex; align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.hed__pill.is-published { background: rgba(16, 122, 87, 0.1); color: #107a57; }
.hed__pill.is-draft { background: rgba(185, 28, 28, 0.08); color: #b91c1c; }
.hed__pill--ghost {
  background: var(--color-light-steel);
  color: var(--color-navy);
}
.hed__row-summary {
  margin: 4px 0 6px;
  font-size: 12px;
  color: var(--color-steel);
  line-height: 1.5;
}
.hed__row-meta {
  font-size: 11px;
  color: var(--color-steel);
  font-family: var(--font-mono);
}
.hed__slug { font-weight: 700; color: var(--color-navy); }

.hed__row-actions {
  display: flex; flex-direction: column; gap: 4px; flex-shrink: 0;
}
.hed__act {
  display: inline-flex; align-items: center; gap: 4px;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 11px;
  font-weight: 700;
  color: var(--color-navy);
  cursor: pointer;
}
.hed__act:hover { background: var(--color-light-steel); }
.hed__act--danger:hover { color: #b91c1c; border-color: #fca5a5; }
</style>
