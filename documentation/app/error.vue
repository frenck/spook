<script setup lang="ts">
import type { NuxtError } from "#app";

const props = defineProps<{
  error: NuxtError;
}>();

const { t } = useI18n();
const { language, localTo } = useSiteLanguage();

// An error page is never a search result, whatever address it shows up at.
useHead({
  htmlAttrs: { lang: language },
  meta: [{ name: "robots", content: "noindex" }],
});

useSeoMeta({
  title: () => t("error.notFound"),
  description: () => t("error.description"),
});

await fetchDocsItems();

// Nuxt UI's own words, like "Close" and "Previous", in the same language.
const uiLocale = computed(() => uiLocaleOf(language.value));

// A missing page says so in the language of the address it was looked for.
const shown = computed(() =>
  props.error.statusCode === 404
    ? { ...props.error, statusMessage: t("error.notFound") }
    : props.error,
);
</script>

<template>
  <UApp :locale="uiLocale">
    <AppHeader />

    <UError :error="shown" :redirect="localTo('/')" />

    <AppFooter />

    <SiteSearch />
  </UApp>
</template>
