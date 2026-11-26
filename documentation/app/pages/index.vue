<script setup lang="ts">
// The words of the home page are the site's own words, `home.*` in
// `locales/`, so they are translated together with the menus and buttons.
// `content/index.md` is the same page in plain Markdown, for assistants.
const { t } = useI18n();
const { language, translated, localTo, intlLocale } = useSiteLanguage();

// Under `/nl` only once the site's own words are in Dutch.
if (translated.value && !isTranslated("/", language.value)) {
  throw createError({
    statusCode: 404,
    statusMessage: "Page not found",
    fatal: true,
  });
}

const title = t("home.meta.title");
const description = t("home.meta.description");

useSeoMeta({
  titleTemplate: "",
  title,
  ogTitle: title,
  description,
  ogDescription: description,
});

// This page in plain Markdown, `content/index.md`, for assistants and
// agents. In English only.
useHead({
  link: translated.value
    ? []
    : [
        {
          rel: "alternate",
          type: "text/markdown",
          href: siteUrl("/raw/index.md"),
        },
      ],
});

// Counted from the documentation, so they grow with Spook.
const counts = await useSpookCounts();

// About one in four Home Assistant installations shares analytics, so the
// Open Home Foundation estimates the real number as four times the count.
// The same estimate is used here.
const ANALYTICS_SHARE = 4;

// Numbers from outside these docs, fetched while the site is built.
const { data: outside } = await useFetch<{
  installations: number | null;
  stars: number | null;
  release: { version: string; date: string } | null;
}>("/api/stats");

// What Spook is, for search engines and AI assistants. The version comes from
// the newest release, fetched while the site is built, and is left out when
// GitHub could not be reached.
useStructuredData(() => [
  websiteNode(language.value),
  frenckNode,
  {
    "@type": "SoftwareApplication",
    "@id": SPOOK_ID,
    name: "Spook",
    description,
    url: siteUrl("/"),
    applicationCategory: "HomeApplication",
    applicationSubCategory: "Home Assistant custom integration",
    operatingSystem: "Home Assistant",
    installUrl: siteUrl("/installation"),
    downloadUrl: "https://github.com/frenck/spook/releases",
    softwareRequirements: t("home.requires"),
    license: "https://opensource.org/license/mit",
    isAccessibleForFree: true,
    offers: { "@type": "Offer", price: "0", priceCurrency: "EUR" },
    author: { "@id": frenckNode["@id"] },
    sameAs: ["https://github.com/frenck/spook"],
    ...(outside.value?.release && {
      softwareVersion: outside.value.release.version.replace(/^v/, ""),
      dateModified: outside.value.release.date,
    }),
  },
]);

const stats = computed(() => [
  ...(outside.value?.installations
    ? [
        {
          value: outside.value.installations * ANALYTICS_SHARE,
          label: t("home.stats.installations"),
          to: "https://analytics.home-assistant.io/custom_integrations",
        },
      ]
    : []),
  ...(outside.value?.stars
    ? [
        {
          value: outside.value.stars,
          label: t("home.stats.stars"),
          to: "https://github.com/frenck/spook/stargazers",
        },
      ]
    : []),
  { value: counts.value.repairs, label: t("home.stats.repairs") },
  { value: counts.value.actions, label: t("home.stats.actions") },
  {
    value: counts.value.triggers + counts.value.conditions,
    label: t("home.stats.triggersConditions"),
  },
  {
    value: counts.value.integrations,
    label: t("home.stats.integrations"),
  },
]);

const install = INSTALL_URL;

// The share card: the hero, the repairs it finds, and two numbers that sell.
defineOgImage("Spook", {
  kind: "home",
  eyebrow: t("home.share.eyebrow"),
  title: t("home.share.title"),
  screenshot: "repairs-list",
  stats: [
    ...(outside.value?.installations
      ? [
          {
            value: (
              outside.value.installations * ANALYTICS_SHARE
            ).toLocaleString(intlLocale.value),
            label: t("home.share.installations"),
          },
        ]
      : []),
    { value: counts.value.repairs, label: t("home.share.repairs") },
  ],
});

const repairs = [
  {
    icon: "i-mdi-alert-outline",
    color: "text-warning",
    title: t("home.toolbox.unknownEntities"),
    where: "dashboard.home",
  },
  {
    icon: "i-mdi-floor-plan",
    color: "text-info",
    title: t("home.toolbox.emptyAreas"),
    where: "area.attic",
  },
  {
    icon: "i-mdi-label-off-outline",
    color: "text-error",
    title: t("home.toolbox.unusedLabels"),
    where: "label.old_test",
  },
];

const actions = [
  "homeassistant.disable_device",
  "homeassistant.delete_all_orphaned_entities",
  "homeassistant.ignore_all_discovered",
  "automation.snooze",
  "light.set_brightness",
  "input_select.random",
  "zone.create",
  "repairs.create",
  "spook.boo",
];

const triggersAndConditions = [
  "spook.cron",
  "spook.automation_turned_off",
  "spook.device_added",
  "spook.flapping",
  "spook.cooldown",
  "spook.triggered_by_user",
];

const brands = [
  "automation",
  "lovelace",
  "light",
  "climate",
  "calendar",
  "cloud",
];

const steps = [
  {
    icon: "i-mdi-numeric-1-circle-outline",
    title: t("home.steps.install"),
    description: t("home.steps.installText"),
  },
  {
    icon: "i-mdi-numeric-2-circle-outline",
    title: t("home.steps.setUp"),
    description: t("home.steps.setUpText"),
  },
  {
    icon: "i-mdi-numeric-3-circle-outline",
    title: t("home.steps.see"),
    description: t("home.steps.seeText"),
  },
];

// The objections people raise before they install, answered right where
// they decide: the first of each group on the straight answers page.
const { data: answers } = await useAsyncData(
  `home-answers-${language.value}`,
  () => queryAnswers(language.value),
);
const honest = computed(
  () => answers.value?.groups.map((group) => group.questions[0]) ?? [],
);

// Rendered like every code block in the docs: highlighted, with the file
// name on top and a copy button.
const { data: example } = await useAsyncData("home-example", () =>
  queryCollection("snippets").path("/data/snippets/weekday-morning").first(),
);
</script>

<template>
  <div>
    <UPageHero
      orientation="horizontal"
      :ui="{
        // The screenshot keeps a readable width, whatever the language. A
        // title that does not fit next to it wraps instead of pushing it.
        container:
          'lg:grid-cols-[minmax(0,1.1fr)_minmax(26rem,0.9fr)] py-16 sm:py-24 lg:py-28',
        wrapper: 'fade-away',
        headline:
          'mb-7 flex items-center gap-3 font-mono text-xs uppercase tracking-[0.1em] text-muted',
        // Chinese characters fill the whole line height: at 0.98 two lines
        // of them touch.
        title:
          'text-[clamp(2.5rem,4.6vw,4.5rem)] sm:text-[clamp(2.5rem,4.6vw,4.5rem)] leading-[0.98] [&:lang(zh)]:leading-[1.15] [&:lang(ja)]:leading-[1.15] tracking-[-0.04em] hyphens-auto',
        description: 'max-w-[30rem]',
      }"
    >
      <template #headline>
        <img
          src="/images/spook-ghost.png"
          alt=""
          class="ghost-float size-11 drop-shadow-[0_0_18px_rgb(36_254_253/0.45)]"
        />
        <i18n-t
          keypath="home.headline"
          tag="span"
          scope="global"
          class="leading-snug"
        >
          <template #br><br /></template>
        </i18n-t>
      </template>

      <template #title>
        <span class="block text-balance">
          {{ t("home.titleStart") }}
        </span>
        <span class="block text-balance text-primary">{{
          t("home.titleEnd")
        }}</span>
      </template>

      <template #description>
        {{ t("home.description") }}
      </template>

      <template #links>
        <UButton
          size="xl"
          icon="i-mdi-download"
          :to="install"
          target="_blank"
          :label="t('cta.install')"
          class="dark:shadow-(--glow-cyan-sm)"
        />
        <UButton
          size="xl"
          color="neutral"
          variant="ghost"
          trailing-icon="i-mdi-arrow-right"
          :to="localTo('/docs')"
          :label="t('cta.readDocs')"
        />
        <div
          class="mt-6 flex basis-full flex-wrap gap-x-5 gap-y-1 font-mono text-xs text-dimmed"
        >
          <span>{{ t("home.free") }}</span>
          <span aria-hidden="true" class="text-(--ui-border-accented)">/</span>
          <span>{{ t("home.requires") }}</span>
          <span aria-hidden="true" class="text-(--ui-border-accented)">/</span>
          <span>{{ t("home.noYaml") }}</span>
        </div>
      </template>

      <!-- Drifts up a little slower than the page as you scroll on. -->
      <Screenshot class="drift" name="repairs-list" :alt="t('home.heroAlt')" />
    </UPageHero>

    <!-- Numbers: from Home Assistant, GitHub and these docs -->
    <section class="border-y border-muted">
      <UContainer class="py-9">
        <div
          class="grid grid-cols-2 gap-x-5 gap-y-7 md:grid-cols-3 lg:grid-cols-6"
        >
          <component
            :is="stat.to ? 'a' : 'div'"
            v-for="stat in stats"
            :key="stat.label"
            :href="stat.to"
            :target="stat.to ? '_blank' : undefined"
            class="group border-s border-default ps-5"
          >
            <p
              class="font-display text-[clamp(1.625rem,3vw,2.125rem)] font-bold leading-tight tracking-tight text-highlighted"
            >
              <CountUp :value="stat.value" />
            </p>
            <p
              class="mt-1.5 font-mono text-[11.5px] tracking-wide text-muted group-hover:text-highlighted"
            >
              {{ stat.label }}
            </p>
          </component>
        </div>
        <p
          v-if="outside?.installations"
          class="mt-6 font-mono text-[11px] text-dimmed"
        >
          {{ t("home.estimate") }}
        </p>
      </UContainer>
    </section>

    <UPageSection
      :headline="t('home.toolbox.headline')"
      :ui="{ title: 'max-w-3xl', container: 'lg:py-28' }"
    >
      <template #title>
        <i18n-t keypath="home.toolbox.title" scope="global">
          <template #br><br /></template>
        </i18n-t>
      </template>

      <div class="reveal-stagger grid gap-4 lg:grid-cols-12">
        <UPageCard
          class="lg:col-span-7"
          :title="t('home.toolbox.ghosts')"
          icon="i-mdi-ghost-outline"
          :to="localTo('/tour/repairs')"
          spotlight
          :description="t('home.toolbox.ghostsText', { count: counts.repairs })"
        >
          <div class="flex flex-col gap-2">
            <div
              v-for="repair in repairs"
              :key="repair.title"
              class="flex items-center gap-2.5 rounded-md border border-muted bg-muted px-3 py-2.5"
            >
              <UIcon :name="repair.icon" class="size-4" :class="repair.color" />
              <span class="text-sm font-medium">{{ repair.title }}</span>
              <span class="ms-auto font-mono text-[11px] text-dimmed">
                {{ repair.where }}
              </span>
            </div>
          </div>
        </UPageCard>

        <UPageCard
          class="lg:col-span-5"
          :title="t('home.toolbox.triggers')"
          icon="i-mdi-timer-cog-outline"
          :to="localTo('/tour/automations')"
          spotlight
          :description="t('home.toolbox.triggersText')"
        >
          <HomeChips :items="triggersAndConditions" />
        </UPageCard>

        <UPageCard
          class="lg:col-span-5"
          :title="t('home.toolbox.integrations')"
          icon="i-mdi-puzzle-outline"
          :to="localTo('/enhanced-integrations')"
          spotlight
          :description="
            t('home.toolbox.integrationsText', { count: counts.integrations })
          "
        >
          <UAvatarGroup size="lg" :max="brands.length + 1">
            <UAvatar
              v-for="brand in brands"
              :key="brand"
              :src="`https://brands.home-assistant.io/${brand}/icon.png`"
              alt=""
              class="bg-muted p-1.5"
            />
            <UAvatar
              :text="`+${counts.integrations - brands.length}`"
              class="bg-elevated font-mono text-xs"
            />
          </UAvatarGroup>
        </UPageCard>

        <UPageCard
          class="lg:col-span-7"
          :title="t('home.toolbox.actions', { count: counts.actions })"
          icon="i-mdi-lightning-bolt-outline"
          :to="localTo('/tour/manage')"
          spotlight
          :description="t('home.toolbox.actionsText')"
        >
          <HomeChips :items="actions" />
        </UPageCard>
      </div>
    </UPageSection>

    <UPageSection
      :headline="t('home.steps.headline')"
      :title="t('home.steps.title')"
      :features="steps"
      :ui="{ header: 'reveal', features: 'reveal-stagger' }"
      :links="[
        {
          label: t('home.steps.guide'),
          to: localTo('/installation'),
          variant: 'link',
          color: 'neutral',
          trailingIcon: 'i-mdi-arrow-right',
        },
      ]"
      class="border-t border-muted"
    />

    <!-- An example, always on ink: dark is where Spook looks best -->
    <div class="dark border-y border-muted bg-(image:--gradient-haunt)">
      <UPageSection
        orientation="horizontal"
        :headline="t('home.example.headline')"
        :title="t('home.example.title')"
        :description="t('home.example.description')"
        :links="[
          {
            label: t('cta.install'),
            icon: 'i-mdi-download',
            to: install,
            target: '_blank',
            size: 'lg',
            class: 'shadow-(--glow-cyan-sm)',
          },
          {
            label: t('cta.takeTour'),
            to: localTo('/tour/automations'),
            size: 'lg',
            color: 'neutral',
            variant: 'ghost',
            trailingIcon: 'i-mdi-arrow-right',
          },
        ]"
      >
        <UTabs
          :items="[
            {
              label: t('home.example.editor'),
              icon: 'i-mdi-cursor-default-click-outline',
              slot: 'editor',
            },
            {
              label: t('home.example.yaml'),
              icon: 'i-mdi-code-braces',
              slot: 'yaml',
            },
          ]"
          variant="link"
          class="w-full"
        >
          <template #editor>
            <Screenshot name="automation-editor" :alt="t('home.example.alt')" />
          </template>
          <template #yaml>
            <ContentRenderer v-if="example" :value="example" class="w-full" />
          </template>
        </UTabs>
      </UPageSection>
    </div>

    <!-- What others say, word for word and linked -->
    <HomeQuotes />

    <!-- The honest bits, before anyone has to ask -->
    <UPageSection
      :headline="t('home.answers.headline')"
      :title="t('home.answers.title')"
      :description="t('home.answers.description')"
      class="border-t border-muted"
      :links="[
        {
          label: t('home.answers.all'),
          to: localTo('/straight-answers'),
          variant: 'link',
          color: 'neutral',
          trailingIcon: 'i-mdi-arrow-right',
        },
      ]"
    >
      <UPageGrid class="reveal-stagger">
        <UPageCard
          v-for="item in honest"
          :key="item.question"
          :title="item.question"
          :description="item.answer"
          :to="localTo('/straight-answers')"
          variant="subtle"
          :ui="{
            title: 'text-lg font-display',
            description: 'line-clamp-4',
          }"
        />
      </UPageGrid>
    </UPageSection>

    <!-- In his own words -->
    <UContainer class="py-14 lg:py-24">
      <figure class="mx-auto max-w-3xl text-center">
        <img
          src="/images/spook-ghost.png"
          alt=""
          class="mx-auto mb-5 size-10 opacity-90"
        />
        <blockquote
          class="font-display text-[clamp(1.375rem,3vw,2rem)] font-medium leading-snug tracking-[-0.02em] text-highlighted [text-wrap:balance]"
        >
          {{ t("home.own.quote") }}
        </blockquote>
        <i18n-t
          keypath="home.own.caption"
          tag="figcaption"
          scope="global"
          class="mt-4 font-mono text-xs text-dimmed"
        >
          <template #link>
            <ULink :to="localTo('/support')" class="underline">
              {{ t("home.own.link") }}
            </ULink>
          </template>
        </i18n-t>
      </figure>
    </UContainer>

    <!-- Call to action, with the one indulgent glow -->
    <div class="relative overflow-hidden border-t border-muted">
      <div
        aria-hidden="true"
        class="pointer-events-none absolute inset-0 bg-(image:--gradient-glow)"
      />
      <UContainer class="relative py-4 lg:py-8">
        <UPageCTA
          variant="naked"
          :links="[
            {
              label: t('cta.install'),
              icon: 'i-mdi-download',
              to: install,
              target: '_blank',
              size: 'lg',
              class: 'dark:shadow-(--glow-cyan-sm)',
            },
            {
              label: t('cta.star'),
              icon: 'i-mdi-github',
              to: 'https://github.com/frenck/spook',
              target: '_blank',
              size: 'lg',
              color: 'neutral',
              variant: 'outline',
            },
          ]"
        >
          <template #title>
            <img
              src="/images/spook-ghost.png"
              alt=""
              class="ghost-float mx-auto mb-6 size-16 drop-shadow-[0_0_24px_rgb(36_254_253/0.5)]"
            />
            <i18n-t keypath="cta.ready" scope="global">
              <template #booo>
                <span class="text-primary">{{ t("cta.booo") }}</span>
              </template>
            </i18n-t>
          </template>
          <template #description>
            <i18n-t keypath="home.end.description" scope="global">
              <template #link>
                <ULink
                  :to="localTo('/support')"
                  class="text-highlighted underline"
                  >{{ t("home.end.link") }}</ULink
                >
              </template>
            </i18n-t>
          </template>
        </UPageCTA>
      </UContainer>
    </div>
  </div>
</template>
