<script setup lang="ts">
/**
 * SectionDeleted — verbatim port of settings-pages.jsx::SectionDeleted (766-793).
 *
 * Phase 3 (audit remediation): hydrates from real backend
 * (GET /v1/sessions/deleted), wires restore/purge to the new admin-gated
 * endpoints. Admin-only — non-admin users see a 403 banner with no rows.
 */
import { onMounted, ref, computed } from 'vue';
import SettingsHeader from './SettingsHeader.vue';
import { sessions as sessionsApi, type DeletedSessionRow } from '@/services/api';
import { ApiError } from '@/services/http';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';

const items = ref<DeletedSessionRow[]>([]);
const loading = ref(true);
const forbidden = ref(false);
const errorMsg = ref<string | null>(null);
const acting = ref<string | null>(null);   // session_id of the row currently in-flight

async function hydrate(): Promise<void> {
  loading.value = true;
  errorMsg.value = null;
  forbidden.value = false;
  try {
    items.value = await sessionsApi.listDeleted();
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) {
      forbidden.value = true;
      items.value = [];
    } else {
      errorMsg.value = e instanceof ApiError ? `${e.status} — ${e.message}` : (e instanceof Error ? e.message : 'Failed to load');
    }
  } finally {
    loading.value = false;
  }
}
onMounted(hydrate);

function daysElapsed(iso: string | null): number {
  if (!iso) return 0;
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
}

function err(e: unknown): string {
  if (e instanceof ApiError) return `${e.status} — ${e.message}`;
  return e instanceof Error ? e.message : 'Request failed';
}

async function restore(it: DeletedSessionRow): Promise<void> {
  if (acting.value) return;
  const ok = await confirm.open({ title: `Restore ${it.code}?`, confirmLabel: 'Restore' });
  if (!ok) return;
  acting.value = it.session_id;
  try {
    await sessionsApi.restore(it.session_id);
    items.value = items.value.filter((x) => x.session_id !== it.session_id);
    toast.push(`${it.code} restored`, { tone: 'success' });
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  } finally {
    acting.value = null;
  }
}

async function purge(it: DeletedSessionRow): Promise<void> {
  if (acting.value) return;
  const ok = await confirm.open({
    title: `Purge ${it.code} permanently?`,
    body: 'This cannot be undone. All segments, slides, sources, and audit rows for this session are deleted from the database.',
    danger: true,
    confirmLabel: 'Purge permanently',
  });
  if (!ok) return;
  acting.value = it.session_id;
  try {
    await sessionsApi.permanentDelete(it.session_id);
    items.value = items.value.filter((x) => x.session_id !== it.session_id);
    toast.push(`${it.code} purged`, { tone: 'success' });
  } catch (e) {
    toast.push(err(e), { tone: 'error' });
  } finally {
    acting.value = null;
  }
}

const summary = computed(() => {
  if (loading.value) return 'Loading…';
  if (forbidden.value) return 'Admin-only view';
  if (errorMsg.value)  return `Error: ${errorMsg.value}`;
  return `${items.value.length} session${items.value.length === 1 ? '' : 's'} · 30-day window`;
});
</script>

<template>
  <SettingsHeader
    title="Deleted sessions"
    lead="Soft-deleted sessions are recoverable for 30 days. After that, only the append-only ledger entries persist."
  />

  <div
    v-if="forbidden"
    role="status"
    :style="{
      padding: '14px 16px',
      background: 'rgba(217,119,6,0.08)',
      border: '1px solid rgba(217,119,6,0.35)',
      borderRadius: 'var(--radius-sm)',
      color: '#b45309',
      fontSize: '13px', lineHeight: 1.55,
      marginBottom: '16px',
    }"
  >
    <strong>Admin-only.</strong>
    Only the org admin can view, restore, or permanently purge deleted sessions.
    Contact your admin if you need a session recovered.
  </div>

  <div class="set-pane" :style="{ padding: 0 }">
    <div class="set-pane__head">
      <span class="set-eyebrow">RECOVERY · {{ summary }}</span>
    </div>

    <div v-if="loading" :style="{ padding: '24px', color: 'var(--fg2)', fontSize: '13px' }">
      Loading deleted sessions…
    </div>

    <div v-else-if="errorMsg" :style="{ padding: '24px', color: 'var(--color-red)', fontSize: '13px' }">
      {{ errorMsg }}
    </div>

    <div
      v-else-if="!forbidden && items.length === 0"
      :style="{ padding: '24px', color: 'var(--fg2)', fontSize: '13px' }"
    >
      No deleted sessions in the 30-day window.
    </div>

    <div v-for="it in items" :key="it.session_id" class="set-row">
      <div>
        <div :style="{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '13px', color: 'var(--fg1)' }">
          {{ it.code }}
        </div>
        <div class="set-row__sub">{{ it.title }}</div>
        <div :style="{ fontSize: '11px', color: 'var(--fg2)', marginTop: '2px' }">
          Deleted {{ it.deleted_at ? it.deleted_at.slice(0, 10) : '—' }} ·
          {{ daysElapsed(it.deleted_at) }}/30 days elapsed ·
          status: {{ it.status }}
        </div>
      </div>
      <div class="set-row__actions">
        <button
          class="btn btn--secondary btn--sm"
          :disabled="acting === it.session_id"
          @click="restore(it)"
        >
          {{ acting === it.session_id ? 'Working…' : 'Restore' }}
        </button>
        <button
          class="set-link set-link--danger"
          :disabled="acting === it.session_id"
          @click="purge(it)"
        >Purge now</button>
      </div>
    </div>
  </div>
</template>
