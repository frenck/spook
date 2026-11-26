<script setup lang="ts">
import type { VNode } from "vue";

/**
 * A word with an entry in the glossary, linking to that entry.
 *
 * Written as `:term[entity]`, or `:term[entities]{to="entity"}` when the
 * word on the page is not quite the one in the glossary.
 */
const props = defineProps<{
  to?: string;
}>();

const slots = defineSlots<{ default?: () => VNode[] }>();

function textOf(nodes: VNode[] = []): string {
  return nodes
    .map((node) =>
      typeof node.children === "string"
        ? node.children
        : textOf(
            Array.isArray(node.children) ? (node.children as VNode[]) : [],
          ),
    )
    .join("");
}

const { localTo } = useSiteLanguage();

// The anchor is made from the English word, so on a translated page a term
// always names its glossary entry with `to`.
const target = computed(() =>
  localTo(`/glossary#term-${anchor(props.to ?? textOf(slots.default?.()))}`),
);
</script>

<template>
  <NuxtLink
    :to="target"
    class="text-inherit underline decoration-dotted underline-offset-4 hover:text-primary"
  >
    <slot />
  </NuxtLink>
</template>
