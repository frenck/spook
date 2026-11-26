<script setup lang="ts">
// The start of the tour: every part of it, with the screenshot it opens with.
const { t } = useI18n();
const { language, translated, pagePath, localTo } = useSiteLanguage();

// Under `/nl` only once the whole tour is in Dutch, like every other page.
if (translated.value && !isTranslated(pagePath.value, language.value)) {
  throw createError({
    statusCode: 404,
    statusMessage: "Page not found",
    fatal: true,
  });
}

const { data: tours } = await useAsyncData(`tours-${language.value}`, () =>
  queryTours(language.value),
);

const counts = await useSpookCounts();

useSeoMeta({
  title: t("tour.title"),
  ogTitle: t("tour.title"),
  description: t("tour.description"),
  ogDescription: t("tour.description"),
});

defineOgImage("Spook", {
  kind: "tour",
  eyebrow: t("tour.headline"),
  title: t("tour.share.title"),
  description: t("tour.share.description"),
  path: "/tour",
  screenshot: "repair-fix-empty-area",
});
</script>

<template>
  <div>
    <UPageHero
      :headline="t('tour.headline')"
      :ui="{
        container: 'py-16 sm:pt-24 sm:pb-8 lg:pt-28 lg:pb-8',
        wrapper: 'fade-away',
        headline: 'font-mono text-xs uppercase tracking-[0.1em]',
      }"
    >
      <template #title>
        {{ t("tour.titleStart") }}<br />
        <span class="text-primary">{{ t("tour.titleEnd") }}</span>
      </template>
      <template #description>
        {{
          t("tour.intro", { repairs: counts.repairs, actions: counts.actions })
        }}
      </template>
    </UPageHero>

    <UContainer class="pb-20 lg:pb-28">
      <!-- Says out loud that the three below are a choice, not a gallery. -->
      <div
        class="reveal mb-6 flex items-end justify-center gap-3 text-primary"
        aria-hidden="true"
      >
        <p class="-rotate-3 pb-5 font-display text-2xl font-bold sm:text-3xl">
          {{ t("tour.pick") }}
        </p>
        <svg
          viewBox="0 0 64 72"
          fill="none"
          stroke="currentColor"
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="h-16 w-14"
        >
          <path d="M6 8c26-4 44 14 38 54" />
          <path d="M30 50l14 14 12-18" />
        </svg>
      </div>
      <h2 class="sr-only">{{ t("tour.pickLabel") }}</h2>

      <div class="reveal-stagger grid gap-6 lg:grid-cols-3">
        <TourCard v-for="tour in tours" :key="tour.stem" :tour="tour" />
      </div>

      <ULink
        :to="localTo('/straight-answers')"
        class="reveal group mt-6 flex flex-col items-start gap-4 rounded-2xl bg-(image:--screenshot-backdrop) p-8 ring ring-default transition hover:ring-primary/60 sm:flex-row sm:items-center"
      >
        <img
          src="/images/spook-ghost.png"
          alt=""
          class="ghost-float size-14 shrink-0"
        />
        <div class="flex-1">
          <h2 class="font-display text-2xl font-bold text-highlighted">
            {{ t("tour.answers.title") }}
          </h2>
          <p class="mt-1 text-muted">
            {{ t("tour.answers.text") }}
          </p>
        </div>
        <span
          class="inline-flex items-center gap-1 text-sm font-medium text-primary"
        >
          {{ t("tour.answers.read") }}
          <UIcon
            name="i-mdi-arrow-right"
            class="size-4 transition group-hover:translate-x-1"
          />
        </span>
      </ULink>
    </UContainer>
  </div>
</template>
