<script setup lang="ts">
import { useClipboard } from "@vueuse/core";
import { withoutTrailingSlash } from "ufo";

const route = useRoute();
const toast = useToast();
const { copy, copied } = useClipboard();
const site = useSiteConfig();
const { t } = useI18n();

// Every page also exists as plain Markdown under /raw, for pasting into an
// assistant or reading without the site around it.
const routePath = computed(() => withoutTrailingSlash(route.path));
const rawPath = computed(() => `/raw${routePath.value}.md`);

const items = computed(() => [
  {
    label: t("page.copyLink"),
    icon: "i-mdi-link-variant",
    onSelect() {
      copy(`${site.url}${rawPath.value}`);
      toast.add({
        title: t("page.copied"),
        icon: "i-mdi-check-circle-outline",
      });
    },
  },
  {
    label: t("page.viewMarkdown"),
    icon: "i-mdi-language-markdown-outline",
    target: "_blank",
    to: rawPath.value,
  },
]);

async function copyPage() {
  copy(await $fetch<string>(rawPath.value));
}
</script>

<template>
  <UFieldGroup>
    <UButton
      :label="t('page.copy')"
      :icon="copied ? 'i-mdi-check-all' : 'i-mdi-content-copy'"
      color="neutral"
      variant="outline"
      :ui="{ leadingIcon: [copied && 'text-primary', 'size-3.5'] }"
      @click="copyPage"
    />
    <UDropdownMenu
      :items="items"
      :content="{ align: 'end', side: 'bottom', sideOffset: 8 }"
      :ui="{ content: 'w-48' }"
    >
      <UButton
        icon="i-mdi-chevron-down"
        size="sm"
        color="neutral"
        variant="outline"
        :aria-label="t('page.moreCopy')"
      />
    </UDropdownMenu>
  </UFieldGroup>
</template>
