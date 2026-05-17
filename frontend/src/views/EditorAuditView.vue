<script setup lang="ts">
/**
 * Audit / Word Track Changes (per-session) — /e/:id/audit
 * Same surface as the standalone AuditRoute; receives an id prop that adds
 * a session breadcrumb hop. Delegates to AuditView so the body is shared.
 */
import AuditView from './AuditView.vue';

defineProps<{ id: string }>();
</script>

<template>
  <AuditView :id="id" />
</template>
