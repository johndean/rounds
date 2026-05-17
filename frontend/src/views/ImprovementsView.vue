<script setup lang="ts">
/**
 * Improvements (master/detail, C pattern) + 5-step wizard. IMPLEMENTATION.md §13.
 * Phase 8 part 2: master list hydrated from /v1/improvements + Suggest modal.
 * Full wizard ships in a follow-up commit.
 */
import { onMounted, ref } from 'vue';
import { useImprovementsStore } from '@/stores/improvements';
import { toast } from '@/composables/useToast';

const store = useImprovementsStore();

const showSuggest = ref(false);
const suggestForm = ref({ title: '', description: '', priority: 'medium', area: '', is_security: false });
const submitting = ref(false);

const TABS = ['all', 'pending', 'under_review', 'approved', 'in_progress', 'rolled_out', 'declined', 'archived'] as const;

function tabLabel(t: string): string {
  return t.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
}

async function submitSuggest(): Promise<void> {
  if (!suggestForm.value.title.trim()) return;
  submitting.value = true;
  const ok = await store.suggest({
    title: suggestForm.value.title.trim(),
    description: suggestForm.value.description.trim() || undefined,
    priority: suggestForm.value.priority,
    area: suggestForm.value.area.trim() || undefined,
    is_security: suggestForm.value.is_security,
  });
  submitting.value = false;
  if (ok) {
    toast.push(`Suggested: ${ok.title}`, { tone: 'success' });
    showSuggest.value = false;
    suggestForm.value = { title: '', description: '', priority: 'medium', area: '', is_security: false };
  } else {
    toast.push('Failed to submit', { tone: 'error' });
  }
}

onMounted(() => store.fetch('all'));
</script>

<template>
  <div class="improvements">
    <header class="improvements__header">
      <div>
        <h1 style="margin: 0; font-size: var(--fs-xl); font-weight: var(--fw-extrabold);">Improvements</h1>
        <p style="margin: var(--space-1) 0 0; color: var(--fg2); font-size: var(--fs-sm);">
          {{ store.filteredCount }} improvement{{ store.filteredCount === 1 ? '' : 's' }} ·
          {{ store.activeStatus === 'all' ? 'all statuses' : tabLabel(store.activeStatus) }}
        </p>
      </div>
      <button class="btn btn--primary" data-test-id="suggest-improvement" @click="showSuggest = true">
        + Suggest Improvement
      </button>
    </header>

    <nav class="improvements__tabs">
      <button
        v-for="t in TABS"
        :key="t"
        :class="['chip', { 'is-active': store.activeStatus === t }]"
        :style="store.activeStatus === t ? 'background: var(--color-navy); color: var(--fg-on-dark); border-color: var(--color-navy);' : ''"
        @click="store.fetch(t)"
      >{{ tabLabel(t) }}<span v-if="t !== 'all' && store.countsByStatus[t]" style="margin-left: var(--space-1); opacity: 0.7;">{{ store.countsByStatus[t] }}</span></button>
    </nav>

    <section class="card">
      <p v-if="store.isLoading" style="margin: 0; color: var(--fg2);">Loading…</p>
      <p v-else-if="store.error" style="margin: 0; color: var(--color-red);">{{ store.error }}</p>
      <p v-else-if="store.filteredCount === 0" style="margin: 0; color: var(--fg2);">
        No improvements{{ store.activeStatus !== 'all' ? ` with status ${tabLabel(store.activeStatus)}` : '' }}.
      </p>
      <table v-else class="impr__table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Risk</th>
            <th>Priority</th>
            <th>Submitted</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="i in store.list" :key="i.id">
            <td>
              <span :title="i.is_security ? 'security-tagged' : ''">{{ i.title }}</span>
              <span v-if="i.is_security" class="chip" style="margin-left: var(--space-2); background: rgba(197,70,68,0.1); border-color: var(--color-red); color: var(--color-red);">SEC</span>
            </td>
            <td><span class="chip">{{ tabLabel(i.status) }}</span></td>
            <td><span class="chip">{{ i.risk }}</span></td>
            <td>{{ i.priority }}</td>
            <td>{{ new Date(i.submitted_at).toLocaleDateString() }} · <span class="mono">{{ i.submitted_by }}</span></td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Inline Suggest modal (full overlay system lands in Phase 2 / U9) -->
    <div v-if="showSuggest" class="suggest-scrim" @click.self="showSuggest = false">
      <form class="suggest-card" @submit.prevent="submitSuggest" data-test-id="suggest-form">
        <h2 style="margin: 0 0 var(--space-4); font-size: var(--fs-lg); font-weight: var(--fw-extrabold);">
          Suggest Improvement
        </h2>
        <label class="suggest-field"><span>Title</span><input v-model="suggestForm.title" type="text" required autofocus /></label>
        <label class="suggest-field"><span>Description</span><textarea v-model="suggestForm.description" rows="4" /></label>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3);">
          <label class="suggest-field"><span>Priority</span>
            <select v-model="suggestForm.priority">
              <option value="low">Low</option><option value="medium">Medium</option>
              <option value="high">High</option><option value="critical">Critical</option>
            </select>
          </label>
          <label class="suggest-field"><span>Area</span><input v-model="suggestForm.area" type="text" placeholder="editor, sessions, …" /></label>
        </div>
        <label style="display: flex; align-items: center; gap: var(--space-2); font-size: var(--fs-sm); color: var(--fg2);">
          <input v-model="suggestForm.is_security" type="checkbox" /> Security-related
        </label>
        <div style="display: flex; gap: var(--space-2); justify-content: flex-end; margin-top: var(--space-3);">
          <button type="button" class="btn" @click="showSuggest = false">Cancel</button>
          <button type="submit" class="btn btn--primary" :disabled="submitting || !suggestForm.title.trim()">
            {{ submitting ? 'Submitting…' : 'Submit' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.improvements { padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-4); }
.improvements__header { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); }
.improvements__tabs { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.improvements__tabs .chip { cursor: pointer; }
.impr__table { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
.impr__table th, .impr__table td { padding: var(--space-3); border-bottom: 1px solid var(--border-subtle); text-align: left; }
.impr__table th { color: var(--fg2); font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: var(--tracking-wide); font-weight: var(--fw-medium); }
.suggest-scrim {
  position: fixed; inset: 0; background: rgba(11,26,46,0.4);
  display: flex; align-items: center; justify-content: center; z-index: 900;
}
.suggest-card {
  background: var(--surface-card); padding: var(--space-6); border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl); width: 100%; max-width: 560px;
  display: flex; flex-direction: column; gap: var(--space-3);
}
.suggest-field { display: flex; flex-direction: column; gap: var(--space-1); }
.suggest-field > span { font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--fg2); }
.suggest-field input, .suggest-field select, .suggest-field textarea {
  padding: var(--space-3); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm);
  font-family: var(--font-family); font-size: var(--fs-sm); background: var(--surface-card); color: var(--fg1);
}
</style>
