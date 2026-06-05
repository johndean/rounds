<script setup lang="ts">
/**
 * frontend/src/components/help/HelpAskComposer.vue
 *
 * Purpose:
 *     Ask AI chat composer + answer thread. Pixel-port of po.vin's
 *     HelpAskComposer with rounds wiring:
 *       - rounds Icon component in place of lucide-vue-next
 *       - rounds helpApi.askHelp() in place of po.vin's SSE streaming
 *         (Phase 2 ships request/response only; simulated streaming is a
 *         Phase 3+ polish item per plan ยง11)
 *
 * UX:
 *     - Cmd/Ctrl+Enter submits.
 *     - Empty/short questions disable the Ask button.
 *     - Each turn renders the user question in a light-steel bubble + the
 *       AI answer in an off-white bubble. Sources render as a numbered
 *       list at the bottom of the answer.
 *     - Errors render inline with a red AlertTriangle (using existing
 *       `alert` icon).
 *     - Cancel is wired but the underlying fetch isn't aborted via signal
 *       in Phase 2; the in-flight thread sets a soft flag the user can
 *       see and lifecycle is naturally bounded by the backend's 1024-tok
 *       output cap.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md ยง7.2
 */
import { computed, nextTick, ref, watch } from 'vue';
import { useHelpStore } from '@/stores/help';
import Icon from '@/components/shared/Icon.vue';

const help = useHelpStore();

const question = ref('');
const composer = ref<HTMLTextAreaElement | null>(null);
const threadEl = ref<HTMLElement | null>(null);

const canSubmit = computed(
  () => question.value.trim().length >= 2 && !help.isStreaming,
);

async function onSubmit(): Promise<void> {
  const q = question.value.trim();
  if (!q || help.isStreaming) return;
  question.value = '';
  await help.startAsk(q);
}

function onKey(e: KeyboardEvent): void {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    void onSubmit();
  }
}

function abort(): void {
  help.abortAsk();
}

function clearAll(): void {
  help.clearAskThread();
  question.value = '';
  void nextTick(() => composer.value?.focus());
}

// Auto-scroll the thread when content updates.
watch(
  () => help.askThread.map((t) => t.answer.length).join(','),
  () => {
    void nextTick(() => {
      const el = threadEl.value;
      if (el) el.scrollTop = el.scrollHeight;
    });
  },
);
</script>

<template>
  <div class="help-ask">
    <div class="help-ask__head">
      <span class="help-ask__overline">
        <Icon name="sparkles" :size="12" /> Ask the Help Center AI
      </span>
      <button
        v-if="help.askThread.length > 0"
        class="help-ask__clearbtn"
        type="button"
        @click="clearAll"
      >Clear thread</button>
    </div>

    <div ref="threadEl" class="help-ask__thread" role="log" aria-live="polite">
      <p v-if="help.askThread.length === 0" class="help-ask__empty">
        Ask anything about rounds.vin transcript editing, sessions, SOP workflow, exports.
        Answers cite the help articles they came from.
      </p>

      <article
        v-for="t in help.askThread"
        :key="t.id"
        class="help-ask__turn"
      >
        <div class="help-ask__q">
          <span class="help-ask__q-label">You</span>
          {{ t.question }}
        </div>
        <div class="help-ask__a">
          <span class="help-ask__a-label"><Icon name="sparkles" :size="11" /> Answer</span>
          <div class="help-ask__a-body">
            <template v-if="t.answer">{{ t.answer }}</template>
            <span v-if="t.streaming" class="help-ask__cursor" aria-hidden="true" />
            <span
              v-if="!t.streaming && !t.answer && !t.errorCode"
              class="help-ask__placeholder"
            >…</span>
          </div>
          <div v-if="t.errorCode" class="help-ask__err" role="alert">
            <Icon name="alert" :size="12" />
            <span>{{ t.errorMessage ?? 'Answer failed' }}</span>
          </div>
          <ol v-if="t.citations.length > 0" class="help-ask__cites">
            <li v-for="(c, i) in t.citations" :key="c.id">
              <span class="help-ask__cite-n">[{{ i + 1 }}]</span>
              <span class="help-ask__cite-title">{{ c.title }}</span>
            </li>
          </ol>
        </div>
      </article>
    </div>

    <form class="help-ask__composer" @submit.prevent="onSubmit">
      <textarea
        ref="composer"
        v-model="question"
        class="help-ask__input"
        placeholder="Ask a question… (⌘/Ctrl + Enter to send)"
        aria-label="Ask AI question"
        rows="2"
        :disabled="help.isStreaming"
        data-test-id="help-ask-input"
        @keydown="onKey"
      />
      <div class="help-ask__composer-actions">
        <button
          v-if="help.isStreaming"
          type="button"
          class="help-ask__send"
          aria-label="Cancel current question"
          @click="abort"
        >
          <Icon name="x" :size="12" /> Cancel
        </button>
        <button
          v-else
          type="submit"
          class="help-ask__send"
          :disabled="!canSubmit"
          aria-label="Send question"
          data-test-id="help-ask-submit"
        >
          <Icon name="send" :size="12" /> Ask
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
/* Pixel-port additions over help.css (citation list styling lives only
   inside the composer, not the global help.css). */
.help-ask__cites {
  list-style: none;
  margin: 10px 0 0;
  padding: 8px 0 0;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.help-ask__cites li {
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-navy);
}
.help-ask__cite-n {
  font-family: var(--font-mono);
  color: var(--color-steel);
  margin-right: 4px;
}
.help-ask__cite-title { flex: 1; }

.help-ask__clearbtn {
  background: transparent;
  border: none;
  font-size: 11px;
  color: var(--color-steel);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.help-ask__clearbtn:hover { color: var(--color-navy); background: var(--color-light-steel); }

.help-ask__q-label {
  display: inline-block;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-steel);
  margin-right: 8px;
}
.help-ask__a-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-blue);
  margin-bottom: 6px;
}
.help-ask__a-body {
  font-size: 13px;
  color: var(--color-navy);
  line-height: 1.55;
  white-space: pre-wrap;
}
.help-ask__cursor {
  display: inline-block;
  width: 7px;
  height: 14px;
  vertical-align: middle;
  background: var(--color-blue);
  margin-left: 2px;
  animation: help-cursor 1s steps(2, end) infinite;
}
@keyframes help-cursor { to { opacity: 0; } }
.help-ask__placeholder {
  color: var(--color-steel);
  font-style: italic;
}
.help-ask__err {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  margin-top: 8px;
  padding: 6px 10px;
  background: rgba(192, 36, 36, 0.06);
  color: #b91c1c;
  border-radius: 6px;
  font-size: 12px;
}
.help-ask__turn {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.help-ask__q {
  background: var(--color-light-steel);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--color-navy);
  line-height: 1.4;
}
.help-ask__a {
  background: var(--color-off-white);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 10px 12px;
}
</style>
