<script setup lang="ts">
/**
 * SOP workflow (IMPLEMENTATION.md §8).
 * Phase 8 part 3 — live state + advance against /v1/sessions/{id}/sop.
 */
import { ref, onMounted, computed } from 'vue';
import { sop as sopApi } from '@/services/api';
import { ApiError } from '@/services/http';
import { confirm } from '@/composables/useConfirm';
import { toast } from '@/composables/useToast';

const props = defineProps<{ id: string }>();

const STAGES = ['prep','copy_draft','medical','copy_final','cms','captions','qa','complete'] as const;
type Stage = typeof STAGES[number];

const state = ref<{ current_stage: string; is_blocked: boolean } | null>(null);
const error = ref<string | null>(null);
const isAdvancing = ref(false);

const currentIndex = computed(() => state.value ? STAGES.indexOf(state.value.current_stage as Stage) : -1);
const nextStage = computed<Stage | null>(() => {
  const i = currentIndex.value;
  return i >= 0 && i < STAGES.length - 1 ? STAGES[i + 1]! : null;
});

async function load(): Promise<void> {
  try {
    state.value = await sopApi.state(props.id) as { current_stage: string; is_blocked: boolean };
  } catch (e) {
    error.value = e instanceof ApiError ? `${e.status}` : (e instanceof Error ? e.message : 'Failed to load');
  }
}

async function advance(): Promise<void> {
  if (!nextStage.value) return;
  const ok = await confirm.open({
    title: `Advance to ${nextStage.value}?`,
    body: `This is an append-only transition and will write an audit event.`,
    confirmLabel: `Advance to ${nextStage.value}`,
  });
  if (!ok) return;
  isAdvancing.value = true;
  try {
    await sopApi.advance(props.id, nextStage.value);
    toast.push(`Advanced to ${nextStage.value}`, { tone: 'success' });
    await load();
  } catch (e) {
    toast.push(`Failed: ${e instanceof Error ? e.message : 'unknown'}`, { tone: 'error' });
  } finally {
    isAdvancing.value = false;
  }
}

function fmt(s: string): string {
  return s.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
}

onMounted(load);
</script>

<template>
  <div class="sop">
    <header>
      <RouterLink :to="`/s/${props.id}`" style="color: var(--fg2); font-size: var(--fs-xs); text-decoration: none;">
        ← Session
      </RouterLink>
      <h1 style="margin: var(--space-1) 0 0; font-size: var(--fs-xl); font-weight: var(--fw-extrabold);">
        SOP Workflow
      </h1>
    </header>

    <p v-if="error" style="color: var(--color-red);">{{ error }}</p>

    <section v-if="state" class="card">
      <p style="margin: 0 0 var(--space-4); color: var(--fg2); font-size: var(--fs-sm);">
        Current stage:
        <span class="chip" style="background: var(--color-warm-light); margin-left: var(--space-2);">
          {{ fmt(state.current_stage) }}
        </span>
        <span v-if="state.is_blocked" class="chip" style="background: rgba(197,70,68,0.15); color: var(--color-red); margin-left: var(--space-2);">BLOCKED</span>
      </p>

      <ol class="stage-list">
        <li
          v-for="(s, i) in STAGES"
          :key="s"
          :class="['stage', {
            'stage--done':    i < currentIndex,
            'stage--current': i === currentIndex,
          }]"
        >
          <span class="stage__num">{{ i + 1 }}</span>
          <span class="stage__name">{{ fmt(s) }}</span>
          <span v-if="i === currentIndex" class="chip" style="background: var(--color-warm-light);">CURRENT</span>
          <span v-else-if="i < currentIndex" class="chip" style="color: var(--color-green);">DONE</span>
        </li>
      </ol>

      <div v-if="nextStage" style="margin-top: var(--space-5); display: flex; gap: var(--space-2);">
        <button class="btn btn--primary" :disabled="isAdvancing || state.is_blocked" @click="advance">
          {{ isAdvancing ? 'Advancing…' : `Advance to ${fmt(nextStage)} →` }}
        </button>
      </div>
      <p v-else-if="state.current_stage === 'complete'" style="margin-top: var(--space-5); color: var(--color-green); font-size: var(--fs-sm);">
        ✓ Workflow complete.
      </p>
    </section>
  </div>
</template>

<style scoped>
.sop { padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-4); max-width: 760px; }
.stage-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.stage {
  display: grid; grid-template-columns: 32px 1fr auto; align-items: center;
  gap: var(--space-3); padding: var(--space-3); border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  background: var(--surface-card);
}
.stage--current { border-color: var(--color-navy); border-width: 2px; }
.stage--done { opacity: 0.65; }
.stage__num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 50%;
  background: var(--surface-muted); font-family: var(--font-mono); font-size: var(--fs-xs);
  color: var(--fg2);
}
.stage--current .stage__num { background: var(--color-navy); color: var(--fg-on-dark); }
.stage--done .stage__num { background: var(--color-green); color: var(--fg-on-dark); }
.stage__name { font-size: var(--fs-sm); }
</style>
