<script setup lang="ts">
import { withoutTrailingSlash } from "ufo";

definePageMeta({
  layout: "docs",
});

const { t } = useI18n();
const { github } = useAppConfig();
const { currentGroup, currentSection, surround } = useDocsNavigation();
const { language, translated, pagePath, localTo } = useSiteLanguage();

// The page itself, whatever language it is read in: `/automation`.
const routePath = computed(() => withoutTrailingSlash(pagePath.value));

// A translated page is the same page in the collection of its language. One
// that was never translated is not there, and does not exist under `/nl`:
// links to it go to the English page instead.
const collection = translated.value
  ? `docs_${collectionCode(language.value)}`
  : "docs";

const { data: page } = await useAsyncData(
  `${language.value}:${routePath.value}`,
  () =>
    queryCollection(collection as "docs")
      .path(routePath.value)
      .first(),
);
if (!page.value) {
  throw createError({
    statusCode: 404,
    statusMessage: "Page not found",
    fatal: true,
  });
}

const title = page.value.seo?.title || page.value.title;
const description = page.value.seo?.description || page.value.description;

// When the English text last changed, from Git: see `modules/page-dates.ts`.
// Looked up while the page is rendered and kept in its payload, so the
// dates never ship to the browser. A translation is regenerated from the
// English page whenever that changes, so it goes without one.
const { data: modified } = await useAsyncData(
  `${language.value}:modified:${page.value.stem}`,
  async () => {
    if (!import.meta.server || translated.value || !page.value) {
      return null;
    }

    const { default: dates } = await import("#build/page-dates.mjs");
    return dates[`${page.value.stem}.${page.value.extension}`] ?? null;
  },
);

useSeoMeta({
  title,
  ogTitle: title,
  description,
  ogDescription: description,
  ogType: "article",
  // The sitemap reads its `lastmod` from this one.
  articleModifiedTime: () => modified.value ?? undefined,
});

// The same page as Markdown, for the assistants and agents that look for
// it. Only the English pages have one, see `llms` in `nuxt.config.ts`.
useHead({
  link: translated.value
    ? []
    : [
        {
          rel: "alternate",
          type: "text/markdown",
          href: siteUrl(`/raw${routePath.value}.md`),
        },
      ],
});

// Where the page sits, and what it is about, for search engines and AI
// assistants: the home page, the area of the docs, the page. Worked out
// here, in setup: the navigation it reads needs the Nuxt instance.
const here = siteUrl(inLanguage(routePath.value, language.value));
const section = currentSection.value;
const trail = [
  { name: "Spook", url: siteUrl(localTo("/")) },
  ...(section && section.hub !== routePath.value
    ? [{ name: t(`nav.${section.key}`), url: siteUrl(section.to) }]
    : []),
  { name: page.value.title, url: here },
];
const website = websiteNode(language.value);

useStructuredData(() => [
  website,
  {
    "@type": "TechArticle",
    "@id": `${here}#article`,
    headline: page.value?.title,
    description,
    url: here,
    inLanguage: language.value,
    isPartOf: { "@id": website["@id"] },
    about: { "@id": SPOOK_ID },
    author: frenckNode,
    ...(modified.value && { dateModified: modified.value }),
  },
  {
    "@type": "BreadcrumbList",
    itemListElement: trail.map((crumb, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: crumb.name,
      item: crumb.url,
    })),
  },
]);

// The small line above the title: the group the page is in. The overview of
// an area is in no group that matters, so it names the area itself.
const headline = computed(() =>
  currentSection.value?.hub === routePath.value
    ? t(`nav.${currentSection.value.key}`)
    : currentGroup.value?.title,
);

// The share card. An integration page shows the integration's own icon and
// how much Spook adds to it; every other page its title and description.
const integration =
  page.value.stem.includes(".enhanced-integrations/") &&
  routePath.value !== "/enhanced-integrations";
const counts = (page.value.meta?.counts ?? {}) as Record<string, number>;

// What Spook adds to an integration, as numbers for its card.
const stats = [
  { count: counts.repairs, key: "share.repairs" },
  { count: counts.actions, key: "share.actions" },
  { count: counts.entities, key: "share.entities" },
]
  .filter(({ count }) => count)
  .map(({ count, key }) => ({
    value: count!,
    label: t(key, count!),
  }));

// The brands repository names an integration by its domain.
const brand = integration
  ? routePath.value.slice(1).replaceAll("-", "_")
  : undefined;

// An integration page is laid out from its Markdown, not shown as one long
// read: see `integrationPage`.
const laidOut = computed(() =>
  integration ? integrationPage(page.value?.body as never) : undefined,
);

// What Spook adds here, as the way into each part of the page.
const adds = [
  { count: counts.actions, key: "integration.actions", to: "#actions" },
  { count: counts.repairs, key: "integration.repairs", to: "#repairs" },
  {
    count: counts.entities,
    key: "integration.entities",
    to: "#devices-entities",
  },
]
  .filter(({ count }) => count)
  .map(({ count, key, to }) => ({
    label: t(key, { count: count! }, count!),
    to,
  }));

defineOgImage("Spook", {
  kind: integration ? "integration" : "docs",
  eyebrow: headline.value,
  title,
  description,
  path: routePath.value,
  brand,
  stats: integration ? stats : undefined,
});

// On the actions page, over a hundred entries make a table of contents
// nobody reads. Their groups make a better one.
// The What's new page lists releases that are not in its Markdown, so its
// table of contents is the releases themselves. The same list the page shows,
// fetched once while the site is built.
const hasReleases = JSON.stringify(page.value?.body ?? "").includes(
  '"release-notes"',
);
const { data: releases } = hasReleases
  ? await useFetch<{ version: string }[]>("/api/releases")
  : { data: ref(null) };

const toc = computed(() => {
  if (releases.value?.length) {
    return releases.value.map(({ version }) => ({
      id: version.replaceAll(".", "-"),
      text: version,
      depth: 2,
    }));
  }

  const links = page.value?.body?.toc?.links ?? [];
  if (!page.value?.reference || page.value.reference === "glossary") {
    return links;
  }

  const { sections } = referenceSections(page.value.body);
  const groups = referenceGroups(referenceEntries(sections));
  return groups.length
    ? groups.map((group) => ({ id: group.id, text: group.title, depth: 2 }))
    : links;
});

// A translated page has no "Edit this page": it is regenerated from the
// English one. What is wrong with it gets reported instead.
const links = computed(() => [
  translated.value
    ? {
        icon: "i-mdi-message-alert-outline",
        label: t("language.report"),
        to: translationReportUrl(language.value, useRoute().path),
        target: "_blank",
      }
    : {
        icon: "i-mdi-pencil-outline",
        label: t("page.edit"),
        to: `${github.edit}/${page.value?.stem}.${page.value?.extension}`,
        target: "_blank",
      },
  {
    icon: "i-mdi-forum-outline",
    label: t("page.ask"),
    to: "https://github.com/frenck/spook/discussions",
    target: "_blank",
  },
]);
</script>

<template>
  <UPage v-if="page">
    <UPageHeader
      :title="page.title"
      :description="page.description"
      :headline="headline"
    >
      <template v-if="brand" #title>
        <span class="flex items-center gap-4">
          <img
            :src="`https://brands.home-assistant.io/${brand}/icon.png`"
            alt=""
            class="size-11 shrink-0 object-contain sm:size-12"
          />
          {{ page.title }}
        </span>
      </template>

      <template #links>
        <PageHeaderLinks />
      </template>

      <div v-if="integration && adds.length" class="mt-5 flex flex-wrap gap-2">
        <UButton
          v-for="add in adds"
          :key="add.to"
          :to="add.to"
          :label="add.label"
          color="neutral"
          variant="subtle"
          trailing-icon="i-mdi-arrow-down"
          class="font-mono"
        />
      </div>
    </UPageHeader>

    <UPageBody>
      <TranslationNotice v-if="translated" />

      <ReferenceGlossary v-if="page.reference === 'glossary'" :page="page" />
      <ReferenceEntries
        v-else-if="page.reference"
        :page="page"
        :noun="page.reference"
      />
      <IntegrationBody v-else-if="laidOut" :chunks="laidOut.chunks" />
      <ContentRenderer v-else :value="page" />

      <USeparator v-if="surround.length" />

      <UContentSurround :surround="surround" />
    </UPageBody>

    <template #right>
      <UContentToc
        v-if="toc.length"
        :title="t('page.onThisPage')"
        :links="toc"
        :ui="{ linkText: 'text-wrap' }"
      >
        <template #bottom>
          <div class="hidden lg:block space-y-6 mt-6">
            <USeparator type="dashed" />
            <UPageLinks
              title="Spook"
              :links="links"
              :ui="{ link: 'items-start', linkLabel: 'text-wrap' }"
            />
          </div>
        </template>
      </UContentToc>
    </template>
  </UPage>
</template>
