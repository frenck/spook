<script setup lang="ts">
// The questions people ask before they install, answered honestly. The
// text is in content/data/answers.yml, and its translations.
const { t } = useI18n();
const { language, translated, pagePath, localTo, intlLocale } =
  useSiteLanguage();

const { data: answers } = await useAsyncData(`answers-${language.value}`, () =>
  queryAnswers(language.value),
);

// Under `/nl` only once the answers are in Dutch, like every other page.
if (
  !answers.value ||
  (translated.value && !isTranslated(pagePath.value, language.value))
) {
  throw createError({
    statusCode: 404,
    statusMessage: "Page not found",
    fatal: true,
  });
}

// The newest release, fetched while the site is built: alive and kicking,
// shown instead of claimed.
const { data: outside } = await useFetch<{
  release: { version: string; date: string } | null;
}>("/api/stats");

const release = computed(() => {
  const latest = outside.value?.release;
  if (!latest) {
    return undefined;
  }
  const date = new Date(latest.date).toLocaleDateString(intlLocale.value, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  return t("answers.release", { version: latest.version, date });
});

useSeoMeta({
  title: answers.value.title,
  ogTitle: answers.value.title,
  description: answers.value.description,
  ogDescription: answers.value.description,
});

// The questions and answers, as an FAQ for search engines and AI assistants.
useStructuredData(() => [
  websiteNode(language.value),
  {
    "@type": "FAQPage",
    "@id": `${siteUrl(inLanguage(pagePath.value, language.value))}#answers`,
    name: answers.value?.title,
    description: answers.value?.description,
    inLanguage: language.value,
    about: { "@id": SPOOK_ID },
    mainEntity: (answers.value?.groups ?? []).flatMap((group) =>
      group.questions.map((item) => ({
        "@type": "Question",
        name: plainText(item.question),
        acceptedAnswer: { "@type": "Answer", text: plainText(item.answer) },
      })),
    ),
  },
]);

defineOgImage("Spook", {
  kind: "docs",
  eyebrow: t("answers.share.eyebrow"),
  title: t("answers.share.title"),
  description: answers.value.description,
  path: "/straight-answers",
});
</script>

<template>
  <div v-if="answers">
    <UPageHero
      :headline="t('answers.headline')"
      :description="t('answers.description')"
      :ui="{
        container: 'py-16 sm:py-24',
        wrapper: 'fade-away',
        headline: 'font-mono text-xs uppercase tracking-[0.1em]',
      }"
    >
      <template #title>
        {{ t("answers.titleStart") }}<br />
        <span class="text-primary">{{ t("answers.titleEnd") }}</span>
      </template>
    </UPageHero>

    <UPageSection
      v-for="group in answers.groups"
      :key="group.title"
      :headline="group.title"
      class="border-t border-muted"
      :ui="{ container: 'py-14 sm:py-20 lg:py-20', header: 'reveal' }"
    >
      <UPageGrid class="reveal-stagger lg:grid-cols-2">
        <UPageCard
          v-for="item in group.questions"
          :key="item.question"
          :icon="group.icon"
          :title="item.question"
          variant="subtle"
          :ui="{ title: 'text-lg font-display', description: 'text-base' }"
        >
          <template #description>
            {{ item.answer }}
          </template>
          <template v-if="item.link" #footer>
            <ULink
              :to="localTo(item.link.to)"
              :target="item.link.to.startsWith('http') ? '_blank' : undefined"
              class="inline-flex items-center gap-1 text-sm font-medium text-primary"
            >
              {{ item.link.label }}
              <UIcon name="i-mdi-arrow-right" class="size-4" />
            </ULink>
          </template>
        </UPageCard>
      </UPageGrid>
    </UPageSection>

    <UPageSection
      class="border-t border-muted"
      :ui="{ container: 'py-14 sm:py-20 lg:py-20' }"
    >
      <UPageCTA
        variant="subtle"
        :title="t('answers.ctaTitle')"
        :description="
          release ? t('answers.ctaLatest', { release }) : t('answers.cta')
        "
        :links="[
          {
            label: t('cta.takeTour'),
            to: localTo('/tour'),
            size: 'lg',
            trailingIcon: 'i-mdi-arrow-right',
          },
          {
            label: t('cta.install'),
            icon: 'i-mdi-download',
            to: INSTALL_URL,
            target: '_blank',
            size: 'lg',
            color: 'neutral',
            variant: 'outline',
          },
        ]"
      />
    </UPageSection>
  </div>
</template>
