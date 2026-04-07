<template>
  <div v-if="$slots.extra" class="page-header page-header--actions">
    <div class="page-header__extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: ''
  },
  description: {
    type: String,
    default: ''
  }
});
</script>
