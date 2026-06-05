<script setup lang="ts">
/**
 * frontend/src/components/help/HelpItem.vue
 *
 * Purpose:
 *     Single accordion question/answer card. Bold question with chevron;
 *     click to expand and reveal the answer. Verbatim port of po.vin's
 *     src/components/HelpItem.vue, with the rounds <Icon> helper used in
 *     place of lucide-vue-next since rounds does not ship lucide.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §6
 */
import { ref, watch } from 'vue';
import Icon from '@/components/shared/Icon.vue';

const props = defineProps<{
  q: string;
  a: string;
  defaultOpen?: boolean;
}>();

const open = ref(!!props.defaultOpen);
watch(() => props.q, () => { open.value = !!props.defaultOpen; });
</script>

<template>
  <div :class="['help-item', { 'is-open': open }]">
    <button
      class="help-item__q"
      :aria-expanded="open"
      type="button"
      @click="open = !open"
    >
      <span class="help-item__q-text">{{ q }}</span>
      <span class="help-item__chev" :style="open ? 'transform: rotate(180deg)' : ''">
        <Icon name="chevron-down" :size="12" />
      </span>
    </button>
    <div v-if="open" class="help-item__a">{{ a }}</div>
  </div>
</template>
