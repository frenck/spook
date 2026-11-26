<script setup lang="ts">
/**
 * A link in the text of a page.
 *
 * On a translated page, a link to another page of the site goes to that page
 * in the same language when it has been translated, and to the English one
 * when it has not. The Markdown says `/support` either way.
 */
import UiProseA from "@nuxt/ui/components/prose/A.vue";

const props = defineProps<{
  href?: string;
  target?: string;
}>();

const { localTo } = useSiteLanguage();

const to = computed(() => (props.href ? localTo(props.href) : props.href));
</script>

<template>
  <UiProseA :href="to" :target="target">
    <slot />
  </UiProseA>
</template>
