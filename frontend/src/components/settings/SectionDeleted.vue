<script setup lang="ts">
/**
 * SectionDeleted — verbatim port of settings-pages.jsx::SectionDeleted (766-793).
 */
import SettingsHeader from './SettingsHeader.vue';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';

interface DeletedItem { code: string; title: string; deletedAt: string; by: string }
const items: DeletedItem[] = [
  { code: '050226_Cheng',       title: 'Equine Neonatal Resuscitation',                  deletedAt: '2026-05-15', by: 'Kate Schultz' },
  { code: '042026_Ramirez',     title: 'Avian Pediatric Wellness — A Hands-on Approach', deletedAt: '2026-04-28', by: 'Mendez M.' },
  { code: '041226_Forsythe-v1', title: 'Reproductive Imaging in the Bitch (v1 draft)',   deletedAt: '2026-04-20', by: 'Kate Schultz' },
];

function daysElapsed(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
}

// Phase 2 audit remediation: restore + purge previously toasted success
// with no backend call (the endpoints don't exist yet). Both demoted to
// honest "not persisted — Phase 3 dep" warnings until Phase 3 ships
// GET /v1/sessions/deleted + POST /restore + DELETE /permanent.
async function restore(it: DeletedItem): Promise<void> {
  const ok = await confirm.open({ title: `Restore ${it.code}?`, confirmLabel: 'Restore' });
  if (!ok) return;
  toast.push(
    'Session restore not yet wired — endpoint ships with Phase 3 session lifecycle.',
    { tone: 'warn' },
  );
}

async function purge(_it: DeletedItem): Promise<void> {
  const ok = await confirm.open({
    title: 'Purge permanently?',
    body: 'This cannot be undone. The audit-ledger entries persist.',
    danger: true,
    confirmLabel: 'Purge',
  });
  if (!ok) return;
  toast.push(
    'Permanent purge not yet wired — endpoint ships with Phase 3 session lifecycle.',
    { tone: 'warn' },
  );
}
</script>

<template>
  <SettingsHeader
    title="Deleted sessions"
    lead="Soft-deleted sessions are recoverable for 30 days. After that, only the append-only ledger entries persist."
  />
  <div class="set-pane" :style="{ padding: 0 }">
    <div class="set-pane__head">
      <span class="set-eyebrow">RECOVERY · 30-DAY WINDOW · {{ items.length }} sessions</span>
    </div>
    <div v-for="(it, i) in items" :key="i" class="set-row">
      <div>
        <div :style="{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '13px', color: 'var(--fg1)' }">{{ it.code }}</div>
        <div class="set-row__sub">{{ it.title }}</div>
        <div :style="{ fontSize: '11px', color: 'var(--fg2)', marginTop: '2px' }">
          Deleted {{ it.deletedAt }} by {{ it.by }} · {{ daysElapsed(it.deletedAt) }}/30 days elapsed
        </div>
      </div>
      <div class="set-row__actions">
        <button class="btn btn--secondary btn--sm" @click="restore(it)">Restore</button>
        <button class="set-link set-link--danger" @click="purge(it)">Purge now</button>
      </div>
    </div>
  </div>
</template>
