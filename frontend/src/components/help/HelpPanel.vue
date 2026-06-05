<script setup lang="ts">
/**
 * frontend/src/components/help/HelpPanel.vue
 *
 * Purpose:
 *     The rounds.vin inline Help Center panel. Pixel-perfect port of
 *     po.vin's src/components/HelpPanel.vue, adapted for rounds' Icon
 *     component (in place of lucide-vue-next) and rounds' Pinia stores.
 *
 *     Phase 1 surface (this file):
 *       - Three tabs: "This page" / "FAQ" / "Ask AI"
 *       - Search input with placeholder "Search help — semantic + lexical"
 *         backed by client-side substring + title-rank (Phase 2 adds
 *         backend semantic search)
 *       - "This page" tab: HELP_CONTENT[pageKey][role] entry render
 *       - "FAQ" tab: HELP_CONTENT.faq render
 *       - "Ask AI" tab: pixel-perfect placeholder with "coming soon" copy
 *         and an Ask button that toasts (real chat ships Phase 2)
 *       - Yellow "Still stuck?" callout
 *       - Footer keyboard hints
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §6
 */
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue';
import { useRoute } from 'vue-router';
import { useHelpStore } from '@/stores/help';
import { useAuthStore } from '@/stores/auth';
import HelpItem from '@/components/help/HelpItem.vue';
import HelpAskComposer from '@/components/help/HelpAskComposer.vue';
import Icon from '@/components/shared/Icon.vue';
import { resolvePageKey } from '@/utils/routeToPageKey';
import { LEGACY_ADMIN_EMAIL_CLIENT } from '@/constants/help-content';

const help = useHelpStore();
const auth = useAuthStore();
const route = useRoute();

type Tab = 'page' | 'faq' | 'ask';
const activeTab = ref<Tab>('page');
const searchInput = ref<HTMLInputElement | null>(null);

// Role resolution: rounds is single-tenant today; only the LEGACY_ADMIN_EMAIL
// admin gate exists (BR-001). Future phases will read auth_users.role.
const role = computed<'user' | 'admin'>(() =>
  (auth.email && auth.email === LEGACY_ADMIN_EMAIL_CLIENT) ? 'admin' : 'user'
);
const roleLabel = computed(() => role.value === 'admin' ? 'Admins' : 'everyone');

// Page resolution: watch the route and set pageKey on the store.
watch(
  () => route.name,
  (name) => help.setPageKey(resolvePageKey(name)),
  { immediate: true },
);

// Search via the store; debounce typing 250ms to keep results stable.
const query = ref('');
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
watch(query, (v) => {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    help.searchQuery = v;
  }, 250);
});

const pageContent = computed(() => help.resolved.pages[help.pageKey]);
const pageEntry = computed(() => {
  const p = pageContent.value;
  if (!p) return null;
  return p[role.value] ?? p.all ?? null;
});
const pageTitle = computed(() => pageContent.value?.title ?? 'Help');

const isSearching = computed(() => query.value.trim().length >= 2);

// Reset state on (re)open + auto-focus search.
watch(() => help.open, async (isOpen) => {
  if (isOpen) {
    query.value = '';
    activeTab.value = 'page';
    await nextTick();
    searchInput.value?.focus();
  }
});

// Esc closes.
function onKey(e: KeyboardEvent): void {
  if (e.key === 'Escape' && help.open) help.hide();
}
onMounted(() => window.addEventListener('keydown', onKey));
onUnmounted(() => {
  window.removeEventListener('keydown', onKey);
  if (debounceTimer) clearTimeout(debounceTimer);
});

// Ask AI is gated by the backend SSOT flag (`help.askEnabled`), set by
// AppHeader.vue on mount from /v1/version. When the flag is false the
// tab still renders so users see what's coming — with a coming-soon
// notice in place of the chat composer.
</script>

<template>
  <aside
    class="help-drawer"
    role="dialog"
    aria-label="Help center"
    :aria-hidden="!help.open"
  >
    <div class="help-drawer__inner">

      <!-- Header -->
      <div class="help-drawer__header">
        <div class="help-drawer__header-left">
          <span class="help-drawer__icon"><Icon name="help-circle" :size="18" /></span>
          <div>
            <div class="help-drawer__overline">Help Center</div>
            <h2 class="help-drawer__title">Need a hand?</h2>
          </div>
        </div>
        <button
          class="help-drawer__close"
          type="button"
          aria-label="Close help"
          data-test-id="help-close"
          @click="help.hide()"
        >
          <Icon name="x" :size="14" />
        </button>
      </div>

      <!-- Search -->
      <div class="help-drawer__search">
        <Icon name="search" :size="14" />
        <input
          ref="searchInput"
          v-model="query"
          type="text"
          aria-label="Search help"
          placeholder="Search help — semantic + lexical"
          data-test-id="help-search-input"
        />
        <span v-if="help.semanticLoading" class="help-drawer__search-spinner" aria-label="Searching">
          <Icon name="spinner" :size="12" />
        </span>
        <button
          v-if="query"
          class="help-drawer__search-clear"
          type="button"
          aria-label="Clear search"
          @click="query = ''"
        >
          <Icon name="x" :size="12" />
        </button>
      </div>

      <!-- Tabs (hidden during active search) -->
      <div v-if="!isSearching" class="help-drawer__tabs" role="tablist">
        <button
          role="tab"
          type="button"
          :aria-selected="activeTab === 'page'"
          :class="['help-drawer__tab', { 'is-active': activeTab === 'page' }]"
          data-test-id="help-tab-page"
          @click="activeTab = 'page'"
        >
          <Icon name="sparkles" :size="12" /> This page
        </button>
        <button
          role="tab"
          type="button"
          :aria-selected="activeTab === 'faq'"
          :class="['help-drawer__tab', { 'is-active': activeTab === 'faq' }]"
          data-test-id="help-tab-faq"
          @click="activeTab = 'faq'"
        >
          <Icon name="book-open" :size="12" /> FAQ
        </button>
        <button
          role="tab"
          type="button"
          :aria-selected="activeTab === 'ask'"
          :class="['help-drawer__tab', { 'is-active': activeTab === 'ask' }]"
          data-test-id="help-tab-ask"
          @click="activeTab = 'ask'"
        >
          <Icon name="sparkles" :size="12" /> Ask AI
        </button>
      </div>

      <!-- Body -->
      <div class="help-drawer__body" role="tabpanel">

        <!-- Search results -->
        <template v-if="isSearching">
          <p class="help-drawer__sectiondesc">
            {{ help.searchResults.length }} result(s) for "{{ help.searchQuery }}"
          </p>
          <template v-if="help.searchResults.length > 0">
            <div class="help-list">
              <HelpItem
                v-for="(t, i) in help.searchResults"
                :key="`s-${i}-${t.q.slice(0, 24)}`"
                :q="t.q"
                :a="t.a"
              />
            </div>
          </template>
          <div v-else class="help-empty">
            <Icon name="search" :size="32" />
            <h3>No matches</h3>
            <p>Try different words, or use the "Ask AI" tab to ask a question.</p>
            <button class="help-drawer__close" type="button" style="width:auto;padding:6px 10px;border-radius:8px;" @click="query = ''">
              Clear search
            </button>
          </div>
        </template>

        <!-- This page -->
        <template v-if="!isSearching && activeTab === 'page'">
          <div class="help-pagehead">
            <div class="help-pagehead__role">For {{ roleLabel }} · {{ pageTitle }}</div>
            <p class="help-pagehead__intro">
              {{ pageEntry?.intro ?? 'No specific tips for this page yet. Try the FAQ tab, search, or Ask AI.' }}
            </p>
          </div>
          <div v-if="pageEntry && pageEntry.topics.length" class="help-list">
            <HelpItem
              v-for="(t, i) in pageEntry.topics"
              :key="`p-${help.pageKey}-${i}`"
              :q="t.q"
              :a="t.a"
              :default-open="i === 0"
            />
          </div>

          <div class="help-cta">
            <strong>Still stuck?</strong>
            <p>
              Try the
              <button type="button" class="help-cta__inline" @click="activeTab = 'ask'">Ask AI</button>
              tab, drop a note in
              <code>{{ help.resolved.contact.slack }}</code>
              or email
              <a :href="`mailto:${help.resolved.contact.email}`">{{ help.resolved.contact.email }}</a>.
            </p>
          </div>
        </template>

        <!-- FAQ -->
        <template v-if="!isSearching && activeTab === 'faq'">
          <div class="help-pagehead">
            <div class="help-pagehead__role">Frequently asked</div>
            <p class="help-pagehead__intro">Top questions across all roles.</p>
          </div>
          <div class="help-list">
            <HelpItem
              v-for="(t, i) in help.resolved.faq"
              :key="`f-${i}`"
              :q="t.q"
              :a="t.a"
            />
          </div>
        </template>

        <!-- Ask AI — real backend wiring when help.askEnabled is true;
             coming-soon notice otherwise (the tab stays visible so users
             see what's on the way). -->
        <template v-if="!isSearching && activeTab === 'ask'">
          <HelpAskComposer v-if="help.askEnabled" />
          <div v-else class="help-ask">
            <div class="help-ask__head">
              <span class="help-ask__overline">
                <Icon name="sparkles" :size="12" /> Ask the Help Center AI
              </span>
            </div>
            <div class="help-ask__thread">
              <p class="help-ask__empty">
                Ask anything about rounds.vin transcript editing, sessions, SOP workflow, exports.
                Answers cite the help articles they came from.
                <br /><br />
                <strong>Coming soon</strong> — for now, use the search bar above or browse the tabs.
              </p>
            </div>
          </div>
        </template>
      </div>

      <!-- Footer -->
      <div class="help-drawer__footer">
        <span>
          Press <span class="kbd">?</span> to open · <span class="kbd">Esc</span> to close
        </span>
        <a
          :href="`https://${help.resolved.contact.docs}`"
          class="help-drawer__doclink"
          target="_blank"
          rel="noopener"
        >
          Full docs <Icon name="external" :size="11" />
        </a>
      </div>
    </div>
  </aside>
</template>
