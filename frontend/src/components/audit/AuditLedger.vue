<script setup lang="ts">
/**
 * AuditLedger — verbatim port of audit.jsx::AuditLedger (290-337).
 * Accepts a corrections array as a prop so callers can hand it data from
 * either the backend (live) or fixtures (legacy). Empty array → empty ledger.
 */
import { computed } from 'vue';

export interface Correction {
  id: string;
  t: string;
  seg: string;
  type: string;
  actor: string;
  prior?: string | null;
  next?: string | null;
  note?: string | null;
}

const props = withDefaults(defineProps<{
  filter?: string;
  corrections?: readonly Correction[];
}>(), { filter: 'all', corrections: () => [] });

interface TypeMeta { label: string; chip: string; note: string }
const correctionTypeLabel: Record<string, TypeMeta> = {
  text_edit:            { label: 'text_edit',            chip: 'red',    note: 'dirties text · flips has_user_override' },
  chat_insert:          { label: 'chat_insert',          chip: 'blue',   note: 'NON-dirty · preserves flags' },
  chat_edit:            { label: 'chat_edit',            chip: 'blue',   note: 'NON-dirty · preserves flags' },
  chat_remove:          { label: 'chat_remove',          chip: 'blue',   note: 'NON-dirty · preserves flags' },
  poll_insert:          { label: 'poll_insert',          chip: 'gold',   note: 'NON-dirty · preserves flags' },
  poll_remove:          { label: 'poll_remove',          chip: 'gold',   note: 'NON-dirty · preserves flags' },
  slide_reassignment:   { label: 'slide_reassignment',   chip: 'amber',  note: 'NON-dirty · preserves flags' },
  speaker_reassignment: { label: 'speaker_reassignment', chip: 'amber',  note: 'NON-dirty · preserves flags' },
  mark_reviewed:        { label: 'mark_reviewed',        chip: 'green',  note: 'NON-dirty · preserves flags' },
  unmark_reviewed:      { label: 'unmark_reviewed',      chip: 'green',  note: 'NON-dirty · preserves flags' },
  annotation_add:       { label: 'annotation_add',       chip: 'blue',   note: 'NON-dirty · preserves flags' },
  annotation_remove:    { label: 'annotation_remove',    chip: 'blue',   note: 'NON-dirty · preserves flags' },
};

const rows = computed<Correction[]>(() => {
  const all = [...props.corrections].reverse();
  return props.filter === 'all' ? all : all.filter(r => r.type === props.filter);
});

function meta(type: string): TypeMeta {
  return correctionTypeLabel[type] ?? { label: type, chip: 'ghost', note: '' };
}
function fmtT(t: string): string {
  try { return new Date(t).toISOString().replace('T', ' ').replace(/\..*$/, ''); }
  catch { return t; }
}
</script>

<template>
  <div class="audit-ledger">
    <div class="audit-row audit-row--head">
      <div>Time (UTC)</div>
      <div>Type</div>
      <div>Segment</div>
      <div>Actor</div>
      <div>Delta</div>
      <div>Note</div>
    </div>
    <div v-for="c in rows" :key="c.id" class="audit-row">
      <div class="t">{{ fmtT(c.t) }}</div>
      <div>
        <span :class="`chip chip--${meta(c.type).chip}`">
          <span class="chip__dot" /> {{ meta(c.type).label }}
        </span>
      </div>
      <div class="seg" :style="{ cursor: 'pointer' }">{{ c.seg }}</div>
      <div class="actor">{{ c.actor }}</div>
      <div class="delta">
        <s v-if="c.prior">{{ c.prior }}</s>
        <b v-if="c.next">{{ c.next }}</b>
        <span v-if="!c.prior && !c.next" :style="{ color: 'var(--fg2)' }">—</span>
      </div>
      <div class="note">{{ c.note || meta(c.type).note }}</div>
    </div>
  </div>
</template>
