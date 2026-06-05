<script setup lang="ts">
/**
 * HelpCenterDrawer — context-sensitive help drawer (Phase 2).
 *
 * Right-side slide-in drawer. Opened from the "?" button in
 * AppHeader's tools cluster. Content is bundled markdown loaded via
 * Vite's `import.meta.glob`, keyed by the current Vue Router route
 * name. Falls back to `_default.md` when no route-specific file
 * exists.
 *
 * Search filters the loaded markdown corpus and shows a list of
 * matching pages. "Ask AI" is gated by VITE_HELP_ASK_AI_ENABLED env
 * flag (default OFF) and surfaces a "coming soon" placeholder when
 * disabled — no LLM call is made.
 *
 * The drawer uses its own z-index layer (840) — below TweaksPanel
 * (850, 800 FAB) so the tweaks panel can still appear on top if both
 * are open. ESC closes. Click outside closes. No mutex with
 * TweaksPanel — they can coexist on screen.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useHelpCenterStore } from '@/stores/helpCenter';

const help = useHelpCenterStore();
const route = useRoute();

// Eagerly load all help markdown bundles at build time. Vite returns
// a record of { './content/help/<name>.md': '...raw...' }.
const helpModules = import.meta.glob('/src/content/help/*.md', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>;

interface HelpEntry { key: string; title: string; raw: string }
const corpus = computed<HelpEntry[]>(() =>
  Object.entries(helpModules).map(([path, raw]) => {
    const key = path.split('/').pop()!.replace(/\.md$/, '');
    const m = raw.match(/^#\s+(.+)$/m);
    const title = m ? m[1]! : key;
    return { key, title, raw };
  }),
);

// Lookup table by file key for O(1) route-name → entry.
const corpusByKey = computed<Record<string, HelpEntry>>(() => {
  const out: Record<string, HelpEntry> = {};
  corpus.value.forEach((e) => { out[e.key] = e; });
  return out;
});

// Route → help entry. Try the route name first; common Rounds route
// names ('dashboard', 'sessions', 'session-detail', 'editor') align
// with content filenames. Fall back to `_default`.
const currentEntry = computed<HelpEntry>(() => {
  const name = typeof route.name === 'string' ? route.name : '';
  return corpusByKey.value[name] || corpusByKey.value._default!;
});

type Tab = 'page' | 'search' | 'ai';
const tab = ref<Tab>('page');
const query = ref('');

const askAiEnabled = (import.meta.env.VITE_HELP_ASK_AI_ENABLED ?? 'false') === 'true';

const searchResults = computed<HelpEntry[]>(() => {
  const q = query.value.trim().toLowerCase();
  if (!q) return [];
  return corpus.value.filter((e) =>
    e.title.toLowerCase().includes(q) || e.raw.toLowerCase().includes(q),
  );
});

// Minimal Markdown → HTML renderer. Supports the subset our help
// content uses: H1/H2/H3, paragraphs, bullets, inline `code`, **bold**,
// *italic*, fenced code blocks. Not a general MD renderer — sufficient
// for content authored under frontend/src/content/help/.
function renderMd(src: string): string {
  if (!src) return '';
  const escape = (s: string): string =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const lines = src.split(/\r?\n/);
  const out: string[] = [];
  let inUl = false;
  let inCode = false;
  let codeBuf: string[] = [];
  const inline = (s: string): string => {
    // Inline code first so backticks inside other markup don't get re-parsed.
    s = s.replace(/`([^`]+)`/g, (_m, c: string) => `<code>${escape(c)}</code>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
    return s;
  };
  const closeList = (): void => { if (inUl) { out.push('</ul>'); inUl = false; } };
  for (const raw of lines) {
    if (inCode) {
      if (/^```\s*$/.test(raw)) {
        out.push(`<pre><code>${escape(codeBuf.join('\n'))}</code></pre>`);
        codeBuf = [];
        inCode = false;
      } else { codeBuf.push(raw); }
      continue;
    }
    if (/^```/.test(raw)) { closeList(); inCode = true; continue; }
    if (/^#{1,3}\s+/.test(raw)) {
      closeList();
      const level = raw.match(/^(#{1,3})/)![1]!.length;
      const text = raw.replace(/^#{1,3}\s+/, '');
      out.push(`<h${level}>${inline(escape(text))}</h${level}>`);
      continue;
    }
    if (/^\s*[-*]\s+/.test(raw)) {
      if (!inUl) { out.push('<ul>'); inUl = true; }
      const item = raw.replace(/^\s*[-*]\s+/, '');
      out.push(`<li>${inline(escape(item))}</li>`);
      continue;
    }
    if (raw.trim().length === 0) { closeList(); out.push(''); continue; }
    closeList();
    out.push(`<p>${inline(escape(raw))}</p>`);
  }
  closeList();
  if (inCode) { out.push(`<pre><code>${escape(codeBuf.join('\n'))}</code></pre>`); }
  return out.filter((l, i, arr) => !(l === '' && arr[i - 1] === '')).join('\n');
}

const renderedPage = computed(() => renderMd(currentEntry.value.raw));

// Reset to "page" tab whenever the route changes — keep search input.
watch(() => route.name, () => { tab.value = 'page'; });

function onKey(e: KeyboardEvent): void {
  if (e.key === 'Escape' && help.isOpen) {
    e.stopPropagation();
    help.close();
  }
}
onMounted(() => window.addEventListener('keydown', onKey));
onUnmounted(() => window.removeEventListener('keydown', onKey));
</script>

<template>
  <Teleport to="body">
    <transition name="help-slide">
      <div
        v-if="help.isOpen"
        class="help-drawer"
        data-test-id="help-center-drawer"
        role="complementary"
        aria-label="Help center"
      >
        <div class="help-drawer__hd">
          <span class="help-drawer__title">Help</span>
          <button
            class="help-drawer__x"
            type="button"
            aria-label="Close help"
            data-test-id="help-center-close"
            @click="help.close"
          >✕</button>
        </div>
        <div class="help-drawer__search">
          <input
            v-model="query"
            class="help-drawer__search-input"
            type="search"
            placeholder="Search help…"
            data-test-id="help-center-search"
            @input="tab = query.trim() ? 'search' : 'page'"
          />
        </div>
        <div class="help-drawer__tabs">
          <button
            :class="['help-drawer__tab', { 'is-active': tab === 'page' }]"
            type="button"
            data-test-id="help-center-tab-page"
            @click="tab = 'page'"
          >This page</button>
          <button
            :class="['help-drawer__tab', { 'is-active': tab === 'search' }]"
            type="button"
            data-test-id="help-center-tab-search"
            @click="tab = 'search'"
          >Search ({{ searchResults.length }})</button>
          <button
            :class="['help-drawer__tab', { 'is-active': tab === 'ai' }]"
            type="button"
            data-test-id="help-center-tab-ai"
            @click="tab = 'ai'"
          >Ask AI</button>
        </div>
        <div class="help-drawer__body">
          <div v-if="tab === 'page'" class="help-md" v-html="renderedPage" />
          <div v-else-if="tab === 'search'">
            <p v-if="!query.trim()" class="help-drawer__hint">Type to search the help corpus.</p>
            <p v-else-if="searchResults.length === 0" class="help-drawer__hint">No matches for "{{ query }}".</p>
            <div
              v-for="entry in searchResults"
              :key="entry.key"
              class="help-drawer__result"
            >
              <h3>{{ entry.title }}</h3>
              <p class="help-drawer__result-meta">{{ entry.key }}.md</p>
            </div>
          </div>
          <div v-else>
            <p v-if="!askAiEnabled" class="help-drawer__hint">
              <strong>Ask AI is disabled.</strong> Set <code>VITE_HELP_ASK_AI_ENABLED=true</code>
              in <code>frontend/.env</code> to enable a chat-style help assistant. This will
              call an LLM with your question + the current page's help context; no session
              content is included.
            </p>
            <p v-else class="help-drawer__hint">Ask AI enabled — chat UI lands in a follow-up commit.</p>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<style>
.help-drawer {
  position: fixed; top: 0; right: 0; bottom: 0; z-index: 840;
  width: 360px; max-width: calc(100vw - 32px);
  display: flex; flex-direction: column;
  background: var(--surface-card, #ffffff);
  color: var(--fg1, #002855);
  border-left: 1px solid var(--border, #e5e7eb);
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.10);
  font-family: var(--font-family); font-size: 13px;
}
.help-drawer__hd {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border, #e5e7eb);
  background: var(--surface-bg, #f7f7f7);
}
.help-drawer__title {
  font-size: 14px; font-weight: 700; letter-spacing: 0.02em;
  color: var(--fg1, #002855);
}
.help-drawer__x {
  background: transparent; border: none; cursor: pointer;
  color: var(--fg2, #6b7280); font-size: 16px; line-height: 1;
  padding: 4px 8px; border-radius: 4px;
}
.help-drawer__x:hover { background: rgba(0, 0, 0, 0.06); color: var(--fg1, #002855); }
.help-drawer__search { padding: 10px 16px; border-bottom: 1px solid var(--border, #e5e7eb); }
.help-drawer__search-input {
  width: 100%; padding: 8px 10px;
  border: 1px solid var(--border, #e5e7eb); border-radius: 6px;
  background: var(--surface, #ffffff); color: var(--fg1, #002855);
  font-size: 13px; font-family: inherit;
}
.help-drawer__tabs {
  display: flex; gap: 4px; padding: 8px 12px;
  border-bottom: 1px solid var(--border, #e5e7eb);
}
.help-drawer__tab {
  flex: 1; padding: 6px 8px; font-size: 12px;
  background: transparent; border: 1px solid transparent;
  border-radius: 4px; cursor: pointer; color: var(--fg2, #6b7280);
  font-family: inherit;
}
.help-drawer__tab.is-active {
  background: rgba(8, 97, 206, 0.10);
  color: var(--color-blue, #0861CE);
  border-color: rgba(8, 97, 206, 0.20);
  font-weight: 600;
}
.help-drawer__tab:hover:not(.is-active) { background: rgba(0, 0, 0, 0.04); }
.help-drawer__body { flex: 1; overflow-y: auto; padding: 16px; }
.help-drawer__hint { color: var(--fg2, #6b7280); font-size: 12.5px; line-height: 1.5; }
.help-drawer__result { padding: 8px 0; border-bottom: 1px solid var(--border-subtle, #f0f0f0); }
.help-drawer__result h3 { font-size: 13px; margin: 0 0 2px; }
.help-drawer__result-meta { font-size: 11px; color: var(--fg2, #6b7280); margin: 0; font-family: var(--font-mono, monospace); }

.help-md h1 { font-size: 16px; margin: 0 0 12px; }
.help-md h2 { font-size: 14px; margin: 16px 0 6px; color: var(--fg1, #002855); }
.help-md h3 { font-size: 13px; margin: 12px 0 4px; color: var(--fg1, #002855); }
.help-md p  { margin: 6px 0; line-height: 1.55; }
.help-md ul { margin: 6px 0 6px 18px; padding: 0; }
.help-md li { margin: 3px 0; line-height: 1.5; }
.help-md code {
  background: rgba(0, 0, 0, 0.06); padding: 1px 4px; border-radius: 3px;
  font-family: var(--font-mono, monospace); font-size: 12px;
}
.help-md pre {
  background: rgba(0, 0, 0, 0.04); padding: 8px 10px;
  border-radius: 4px; overflow-x: auto; font-size: 12px;
}
.help-md pre code { background: transparent; padding: 0; }
.help-md strong { font-weight: 700; }
.help-md em { font-style: italic; }

.help-slide-enter-active, .help-slide-leave-active { transition: transform var(--duration-fast, 150ms) var(--easing-out, ease-out); }
.help-slide-enter-from, .help-slide-leave-to { transform: translateX(100%); }
</style>
