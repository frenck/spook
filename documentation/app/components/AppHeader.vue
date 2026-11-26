<script setup lang="ts">
const { sections, currentSection } = useDocsNavigation();

const route = useRoute();
const { t } = useI18n();
const { language, pagePath, localTo } = useSiteLanguage();

// Fetched while the site is built, the same file the home page reads.
const { data: outside } = await useFetch<{ stars: number | null }>(
  "/api/stats",
);

// 7482 reads as "7.5k" next to an icon.
const compact = (count: number) =>
  new Intl.NumberFormat(language.value, {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(count);

// The tour comes first: see what Spook does, then read how.
const tabs = computed(() => [
  {
    label: t("nav.tour"),
    icon: "i-mdi-compass-outline",
    to: localTo("/tour"),
    active:
      pagePath.value.startsWith("/tour") ||
      pagePath.value === "/straight-answers",
  },
  ...sections.value.map((section) => ({
    label: t(`nav.${section.key}`),
    icon: section.icon,
    to: section.to,
    active: section.label === currentSection.value?.label,
  })),
]);
</script>

<template>
  <UHeader
    :to="localTo('/')"
    title="Spook"
    :ui="{ center: 'flex-1 justify-center' }"
  >
    <template #title>
      <AppLogo />
    </template>

    <UNavigationMenu :items="tabs" variant="link" />

    <template #right>
      <UContentSearchButton />
      <LanguageSwitcher />
      <UColorModeButton />
      <!-- The star count is proof, not a request: it only says how many
           people already did. -->
      <UButton
        color="neutral"
        variant="ghost"
        icon="i-mdi-github"
        to="https://github.com/frenck/spook"
        target="_blank"
        :aria-label="
          outside?.stars
            ? t('nav.githubStars', { count: outside.stars })
            : t('nav.github')
        "
      >
        <span
          v-if="outside?.stars"
          class="hidden items-center gap-0.5 font-mono text-xs lg:inline-flex"
        >
          <UIcon name="i-mdi-star" class="size-3.5 text-primary" />
          {{ compact(outside.stars) }}
        </span>
      </UButton>
      <UButton
        :label="t('nav.install')"
        icon="i-mdi-download"
        :to="INSTALL_URL"
        target="_blank"
        size="sm"
        class="hidden sm:inline-flex"
      />
    </template>

    <!-- The menu on a phone: the same four tabs first, then the pages of the
         area you are in. Everything at once was sixty pages to scroll past. -->
    <template #body>
      <UNavigationMenu
        :items="tabs"
        orientation="vertical"
        class="-mx-2.5"
        :ui="{ link: 'py-2.5 text-base', linkLeadingIcon: 'size-5' }"
      />

      <template v-if="currentSection">
        <USeparator class="my-4" />
        <p
          class="mb-2 font-mono text-[11px] font-semibold tracking-[0.08em] text-dimmed uppercase"
        >
          {{ t(`nav.${currentSection.key}`) }}
        </p>
        <DocsSidebar />
      </template>
    </template>
  </UHeader>
</template>
