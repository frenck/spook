<script setup lang="ts">
/**
 * The search of the site, the same on every page, the error page included.
 */
const { t } = useI18n();
const { localTo } = useSiteLanguage();
const { navigation } = useDocsNavigation();

// The search has its own index, built when somebody first opens it.
const { search, status, build } = useSiteSearch();
const { open: searchOpen } = useContentSearch();
watch(searchOpen, (open) => open && build());

// A result only shows when its page is in here, and the tour is not part of
// the docs. The list is flat on purpose: a result then reads "Automations >
// Actions > Snooze", not three levels of where the page sits before its name,
// which on a phone is all that fits.
const searchable = computed(() => [
  ...[
    { title: t("search.tourRepairs"), path: "/tour/repairs" },
    { title: t("search.tourAutomations"), path: "/tour/automations" },
    { title: t("search.tourManage"), path: "/tour/manage" },
    { title: t("search.straightAnswers"), path: "/straight-answers" },
  ].map((page) => ({
    ...page,
    path: localTo(page.path),
    icon: "i-mdi-compass-outline",
  })),

  ...navigation.value.flatMap((section) =>
    (section.children ?? []).flatMap((group) =>
      (group.children ?? []).map((page) => ({
        title: page.title,
        path: page.path,
        icon: section.icon,
      })),
    ),
  ),
]);

const searchTerm = ref("");

// What the search offers before anything is typed. Once there is a word,
// they make way: the results are better at matching it than a list of six.
const shortcuts = computed(() =>
  [
    {
      label: t("search.install"),
      icon: "i-mdi-download",
      to: "/installation",
    },
    { label: t("search.tour"), icon: "i-mdi-compass-outline", to: "/tour" },
    {
      label: t("search.everything"),
      icon: "i-mdi-book-open-variant",
      to: "/docs",
    },
    {
      label: t("search.integrations"),
      icon: "i-mdi-puzzle-outline",
      to: "/enhanced-integrations",
    },
    {
      label: t("search.actions"),
      icon: "i-mdi-lightning-bolt-outline",
      to: "/actions",
    },
    { label: t("search.help"), icon: "i-mdi-lifebuoy", to: "/support" },
  ].map((shortcut) => ({ ...shortcut, to: localTo(shortcut.to) })),
);
</script>

<template>
  <ClientOnly>
    <LazyUContentSearch
      :search="search"
      :search-status="status"
      :navigation="searchable"
      v-model:search-term="searchTerm"
      :links="searchTerm ? undefined : shortcuts"
      :fuse="{ resultLimit: 16 }"
      :placeholder="t('search.placeholder')"
    />
  </ClientOnly>
</template>
