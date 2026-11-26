<script setup lang="ts">
// A page of the tour: what one part of the toolbox does, shown with real
// screenshots, before the docs explain how. The text is in content/data/tour,
// and its translations.
const route = useRoute();
const slug = String(route.params.slug);

const { t } = useI18n();
const { language, translated, pagePath, localTo } = useSiteLanguage();

const { data: tours } = await useAsyncData(`tours-${language.value}`, () =>
  queryTours(language.value),
);

const tour = computed(() =>
  tours.value?.find((candidate) => candidate.stem === `data/tour/${slug}`),
);

// Under `/nl` only once this part is in Dutch, like every other page.
if (
  !tour.value ||
  (translated.value && !isTranslated(pagePath.value, language.value))
) {
  throw createError({
    statusCode: 404,
    statusMessage: "Page not found",
    fatal: true,
  });
}

const counts = await useSpookCounts();

// The parts of the tour somebody on this page has not seen yet.
const others = computed(() =>
  (tours.value ?? []).filter((candidate) => candidate !== tour.value),
);

/** Fill in `{repairs}` and the like with the counts from the docs. */
function fill(text: string): string {
  return text.replace(/\{(\w+)\}/g, (placeholder, key: string) => {
    const value = counts.value[key as keyof typeof counts.value];
    return value === undefined ? placeholder : String(value);
  });
}

useSeoMeta({
  title: tour.value!.title,
  ogTitle: tour.value!.title,
  description: tour.value!.description,
  ogDescription: tour.value!.description,
});

// The share card shows the same screenshot as the hero of the page.
defineOgImage("Spook", {
  kind: "tour",
  eyebrow: tour.value!.hero.headline,
  title: tour.value!.hero.title,
  description: tour.value!.description,
  path: route.path,
  screenshot: tour.value!.hero.screenshot,
});
</script>

<template>
  <div v-if="tour">
    <UPageHero
      orientation="horizontal"
      :headline="tour.hero.headline"
      :title="tour.hero.title"
      :description="fill(tour.hero.description)"
      :links="[
        {
          label: t('cta.install'),
          icon: 'i-mdi-download',
          to: INSTALL_URL,
          target: '_blank',
          size: 'xl',
          class: 'dark:shadow-(--glow-cyan-sm)',
        },
        {
          label: t('cta.whatIs'),
          to: localTo('/about'),
          size: 'xl',
          color: 'neutral',
          variant: 'ghost',
          trailingIcon: 'i-mdi-arrow-right',
        },
      ]"
      :ui="{
        container: 'lg:grid-cols-[1fr_1.1fr] py-16 sm:py-24',
        wrapper: 'fade-away',
        headline: 'font-mono text-xs uppercase tracking-[0.1em]',
      }"
    >
      <!-- Drifts up a little slower than the page as you scroll on. -->
      <div class="drift">
        <Screenshot :name="tour.hero.screenshot" :alt="tour.hero.alt" />
      </div>
    </UPageHero>

    <UPageSection
      v-for="(section, index) in tour.sections"
      :key="section.screenshot"
      orientation="horizontal"
      :reverse="index % 2 === 1"
      :headline="section.headline"
      :title="section.title"
      :description="fill(section.description)"
      :features="section.features"
      class="border-t border-muted"
      :ui="{ header: 'reveal', features: 'reveal-stagger' }"
    >
      <!-- In from the side it sits on: the sections take turns. -->
      <Screenshot
        :name="section.screenshot"
        :alt="section.alt"
        :from="index % 2 === 1 ? 'left' : 'right'"
      />
    </UPageSection>

    <UPageSection
      :headline="t('tour.more.headline')"
      :title="t('tour.more.title')"
      class="border-t border-muted"
      :ui="{ header: 'reveal' }"
    >
      <div class="reveal-stagger grid gap-6 lg:grid-cols-3">
        <TourCard v-for="other in others" :key="other.stem" :tour="other" />

        <!-- Built like the two next to it: a frame on top, the words below.
             The frame holds the questions the page answers. -->
        <ULink
          :to="localTo('/straight-answers')"
          class="group flex flex-col rounded-2xl p-2 ring ring-default transition hover:-translate-y-1 hover:ring-primary/60"
        >
          <div
            class="relative flex aspect-[4/3] flex-col items-center justify-center gap-3 overflow-hidden rounded-2xl bg-(image:--screenshot-backdrop) p-6 ring ring-default"
          >
            <img
              src="/images/spook-ghost.png"
              alt=""
              class="ghost-float mb-2 size-16"
            />
            <span
              v-for="(question, index) in [
                t('tour.more.questions.safe'),
                t('tour.more.questions.cost'),
                t('tour.more.questions.remove'),
              ]"
              :key="question"
              class="rounded-full bg-default px-3.5 py-1.5 font-display text-sm font-bold text-highlighted shadow-sm ring ring-default"
              :class="['-rotate-2', 'rotate-1', '-rotate-1'][index]"
            >
              {{ question }}
            </span>
          </div>

          <div class="flex flex-1 flex-col gap-2 p-4">
            <p
              class="font-mono text-xs tracking-[0.1em] text-primary uppercase"
            >
              {{ t("tour.more.answersHeadline") }}
            </p>
            <h2 class="font-display text-2xl font-bold text-highlighted">
              {{ t("tour.answers.title") }}
            </h2>
            <p class="text-muted">
              {{ t("tour.more.answersText") }}
            </p>
            <span
              class="mt-auto inline-flex items-center gap-1 pt-3 text-sm font-medium text-primary"
            >
              {{ t("tour.answers.read") }}
              <UIcon
                name="i-mdi-arrow-right"
                class="size-4 transition group-hover:translate-x-1"
              />
            </span>
          </div>
        </ULink>
      </div>
    </UPageSection>

    <UPageSection :title="tour.more.title" class="border-t border-muted">
      <UPageGrid class="reveal-stagger lg:grid-cols-4">
        <UPageCard
          v-for="link in tour.more.links"
          :key="link.to"
          :title="link.title"
          :description="link.description"
          :icon="link.icon"
          :to="localTo(link.to)"
          spotlight
        />
      </UPageGrid>
    </UPageSection>

    <div class="relative overflow-hidden border-t border-muted">
      <div
        aria-hidden="true"
        class="pointer-events-none absolute inset-0 bg-(image:--gradient-glow)"
      />
      <UContainer class="relative py-4 lg:py-8">
        <UPageCTA
          variant="naked"
          :description="t('tour.end')"
          :links="[
            {
              label: t('cta.install'),
              icon: 'i-mdi-download',
              to: INSTALL_URL,
              target: '_blank',
              size: 'lg',
              class: 'dark:shadow-(--glow-cyan-sm)',
            },
            {
              label: t('cta.readDocs'),
              to: localTo('/docs'),
              size: 'lg',
              color: 'neutral',
              variant: 'outline',
            },
          ]"
        >
          <template #title>
            <i18n-t keypath="cta.ready" scope="global">
              <template #booo>
                <span class="text-primary">{{ t("cta.booo") }}</span>
              </template>
            </i18n-t>
          </template>
        </UPageCTA>
      </UContainer>
    </div>
  </div>
</template>
