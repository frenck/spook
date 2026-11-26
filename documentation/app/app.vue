<script setup lang="ts">
const { seo } = useAppConfig();
const { language, translated, pagePath } = useSiteLanguage();

await fetchDocsItems();

// Which languages the page being read exists in, written on the page itself.
// The few lines below read it before anything is on screen.
const available = computed(() =>
  TRANSLATED_LANGUAGES.map(({ code }) => code)
    .filter((code) => isTranslated(pagePath.value, code))
    .join(" "),
);

/**
 * Take somebody who lands on an English page to their own language, when the
 * page exists in it, before the English one shows. What they picked by hand
 * wins; without a pick, the first language of their browser the page has.
 * Where they were sent to on the page (the anchor) comes along.
 *
 * The same rule as `app/middleware/language.global.ts`, which covers every
 * page after the first. Plain old JavaScript: it runs before the site does.
 */
const TO_OWN_LANGUAGE = `(function(){try{var d=document.documentElement;if(d.lang!=="${DEFAULT_LANGUAGE}")return;var has=(d.getAttribute("data-translated")||"").split(" ");var want=localStorage.getItem("${LANGUAGE_STORAGE_KEY}");if(!want){var all=navigator.languages||[navigator.language];for(var i=0;i<all.length;i++){var l=all[i].toLowerCase();var c=/^zh(-hans|-cn|-sg|-my|$)/.test(l)?"zh-Hans":/^pt(-|$)/.test(l)?"pt-BR":l.slice(0,2);if(c==="${DEFAULT_LANGUAGE}"||has.indexOf(c)>-1){want=c;break}}}if(want&&want!=="${DEFAULT_LANGUAGE}"&&has.indexOf(want)>-1){var p=location.pathname;location.replace("/"+want+(p==="/"?"":p)+location.search+location.hash)}}catch(e){}})()`;

useHead({
  meta: [{ name: "viewport", content: "width=device-width, initial-scale=1" }],
  link: [{ rel: "icon", href: "/favicon.ico" }],
  htmlAttrs: {
    lang: language,
    "data-translated": available,
  },
  script: [{ innerHTML: TO_OWN_LANGUAGE, tagPosition: "head" }],
});

// Nuxt UI's own words, like "Close" and "Previous", in the same language.
const uiLocale = computed(() => uiLocaleOf(language.value));

const { t } = useI18n();

/**
 * The title in search results and browser tabs. People search for Spook and
 * Home Assistant, so the title names both, without saying either twice.
 */
function titleFor(title?: string): string {
  if (!title) {
    return t("seo.titleSuffix");
  }

  if (title.includes("Spook")) {
    return title;
  }

  return title.includes("Home Assistant")
    ? `${title} - ${seo?.siteName}`
    : `${title} - ${t("seo.titleSuffix")}`;
}

// The one address of this page, whatever way somebody got to it: with or
// without a slash at the end, with a query, through an old redirect.
const canonical = computed(() =>
  siteUrl(inLanguage(pagePath.value, language.value)),
);

// The same page in other languages. Only told to search engines once the
// translations may be indexed, see `INDEX_TRANSLATIONS`; English is the one
// for everybody else.
const alternates = computed(() => {
  if (!INDEX_TRANSLATIONS) {
    return [];
  }

  const languages = LANGUAGES.filter(({ code }) =>
    isTranslated(pagePath.value, code),
  );
  if (languages.length < 2) {
    return [];
  }

  return [
    ...languages.map(({ code }) => ({
      rel: "alternate",
      hreflang: code,
      href: siteUrl(inLanguage(pagePath.value, code)),
    })),
    {
      rel: "alternate",
      hreflang: "x-default",
      href: siteUrl(pagePath.value),
    },
  ];
});

useHead({
  link: computed(() => [
    { rel: "canonical", href: canonical.value },
    ...alternates.value,
  ]),
  meta: computed(() =>
    translated.value && !INDEX_TRANSLATIONS
      ? [{ name: "robots", content: "noindex" }]
      : [],
  ),
});

useSeoMeta({
  titleTemplate: titleFor,
  ogSiteName: seo?.siteName,
  ogType: "website",
  ogUrl: canonical,
  twitterCard: "summary_large_image",
});
</script>

<template>
  <UApp :locale="uiLocale">
    <NuxtLoadingIndicator />

    <AppHeader />

    <UMain>
      <NuxtLayout>
        <NuxtPage />
      </NuxtLayout>
    </UMain>

    <AppFooter />

    <SiteSearch />
  </UApp>
</template>
