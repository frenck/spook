<script setup lang="ts">
defineProps<{
  items: string[];
}>();
</script>

<template>
  <div class="flex flex-wrap gap-1.5">
    <UBadge
      v-for="item in items"
      :key="item"
      :label="item"
      color="neutral"
      variant="subtle"
      class="font-mono"
    />
  </div>
</template>
