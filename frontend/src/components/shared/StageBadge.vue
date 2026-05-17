<script setup lang="ts">
/**
 * StageBadge — faithful port of components.jsx::StageBadge.
 * Renders ".stage-badge stage-badge--<id>" with "<order>. <name>".
 */
import { computed } from 'vue';
import { SOP_STAGE_BY_ID } from '@/fixtures/sop_stages';

const props = defineProps<{ id: string }>();
const stage = computed(() => SOP_STAGE_BY_ID.get(props.id));
</script>

<template>
  <span v-if="stage" :class="`stage-badge stage-badge--${id}`">{{ stage.order }}. {{ stage.name }}</span>
</template>
