<script setup lang="ts">
/**
 * FormRow — verbatim port of settings-pages.jsx::FormRow (807-816).
 * Two-column form row: left label/sub, right control (slot or default).
 */
defineProps<{
  label: string;
  sub?: string;
}>();
</script>

<template>
  <div class="set-formrow">
    <div class="set-formrow__lbl">
      <div class="set-formrow__label">{{ label }}</div>
      <div v-if="sub" class="set-formrow__sub">{{ sub }}</div>
    </div>
    <div class="set-formrow__ctrl">
      <slot name="control">
        <slot />
      </slot>
    </div>
  </div>
</template>
