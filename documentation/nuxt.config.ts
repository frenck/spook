import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  DEFAULT_LANGUAGE,
  INDEX_TRANSLATIONS,
  LANGUAGES,
  TRANSLATED_LANGUAGES,
} from "./shared/utils/languages";
import { SITE_URL } from "./shared/utils/site";

// The oldest Home Assistant Spook runs on, from what HACS is told. Said in
// `llms.txt`, so assistants don't send people with an older one to install.
const MINIMUM_HOME_ASSISTANT = JSON.parse(
  readFileSync(new URL("../hacs.json", import.meta.url), "utf-8"),
).homeassistant.replace(/\.0$/, "");

// The site's own words (menus, buttons, notices). English is written by
// hand; the others are translated from it by the pipeline, and may not be
// there yet. English goes in first for every language, so a word without a
// translation shows in English instead of as a key.
function wordsFor(code: string): string[] {
  const translated = `translations/output/${code}/locale.json`;
  const exists = existsSync(
    fileURLToPath(new URL(`./${translated}`, import.meta.url)),
  );

  return [
    "locales/en.json",
    ...(code !== DEFAULT_LANGUAGE && exists ? [translated] : []),
  ];
}

export default defineNuxtConfig({
  modules: [
    "@nuxt/image",
    // Nuxt UI brings this one along too, but it has to be here by name, before
    // nuxt-og-image: that only hands the fonts to the share cards when it
    // finds @nuxt/fonts already set up.
    "@nuxt/fonts",
    "@nuxt/ui",
    "@nuxt/content",
    "@nuxtjs/sitemap",
    "nuxt-og-image",
    "nuxt-llms",
    "nuxt-agent-discovery",
    "@nuxtjs/i18n",
  ],

  // Until search engines may index the translations (`INDEX_TRANSLATIONS`),
  // their pages ask not to be, and stay out of the sitemap as well.
  sitemap: {
    exclude: INDEX_TRANSLATIONS
      ? []
      : TRANSLATED_LANGUAGES.map(({ code }) => `/${code}/**`),
  },

  // The site's own words in each language. Only that: which language a page
  // is in comes from its address (`/nl/automation`), and the site reads that
  // itself, see `app/middleware/language.global.ts`. The module is told not to
  // add a language to addresses or links, because it would add one to pages
  // that were never translated.
  i18n: {
    defaultLocale: DEFAULT_LANGUAGE,
    strategy: "no_prefix",
    detectBrowserLanguage: false,
    restructureDir: ".",
    langDir: ".",
    locales: LANGUAGES.map(({ code, name }) => ({
      code,
      language: code,
      name,
      files: wordsFor(code),
    })),
  },

  devtools: {
    enabled: false,
  },

  css: ["~/assets/css/main.css"],

  // The icons are Material Design Icons, like Home Assistant's own. What that
  // set lacks or has outdated, like the Home Assistant logo, is in here.
  icon: {
    customCollections: [{ prefix: "spook", dir: "./app/assets/icons" }],
  },

  site: {
    url: SITE_URL,
    name: "Spook",
  },

  content: {
    build: {
      markdown: {
        highlight: {
          langs: ["yaml", "jinja", "bash", "json"],
        },
      },
    },
    experimental: {
      sqliteConnector: "native",
    },
  },

  experimental: {
    asyncContext: true,
  },

  // The CSS goes in a file of its own, not into every page. With the font
  // rules for Chinese and Japanese it is over 600 KB, and inlined it made each
  // of the 800 pages that much bigger: the built site came close to the 1 GB
  // GitHub Pages allows. As a file, a browser fetches it once and caches it.
  features: {
    inlineStyles: false,
  },

  compatibilityDate: "2026-06-30",

  // The overview of the docs was at /features before it was the way into
  // them. Old links keep working.
  routeRules: {
    "/features": { redirect: "/docs" },
    // The FAQ and the straight answers were two lists of the same questions.
    "/faq": { redirect: "/straight-answers" },
  },

  // Listed per area, the same way as the site. Naming the sections also keeps
  // Nuxt Content from adding every page collection by itself, snippets
  // included.
  //
  // English only: the translated pages are machine translations of
  // these. An assistant that quotes Spook should quote what people wrote and
  // checked, and the English page is the one every translation follows.
  llms: {
    domain: SITE_URL,
    title: "Spook",
    description:
      "Spook is a free, MIT licensed custom integration for Home Assistant, made by Franck Nijhof (Frenck). It finds problems in a Home Assistant setup and raises them as repairs, and adds actions, triggers, conditions and helpers that Home Assistant does not ship.",
    full: {
      title: "Spook, the full documentation",
      description:
        "Every page of the Spook documentation in one file, in English, as Markdown.",
    },
    sections: [
      { title: "Home", contentCollection: "landing" },
      {
        title: "Get started",
        contentCollection: "docs",
        contentFilters: [
          { field: "stem", operator: "LIKE", value: "%.getting-started/%" },
        ],
      },
      {
        title: "Guides",
        contentCollection: "docs",
        contentFilters: [
          { field: "stem", operator: "LIKE", value: "%.guides/%" },
        ],
      },
      {
        title: "Core extensions",
        contentCollection: "docs",
        contentFilters: [
          { field: "stem", operator: "LIKE", value: "%.core-extensions/%" },
        ],
      },
      {
        title: "Helpers",
        contentCollection: "docs",
        contentFilters: [
          { field: "stem", operator: "LIKE", value: "%.helpers/%" },
        ],
      },
      {
        title: "More features",
        contentCollection: "docs",
        contentFilters: [
          { field: "stem", operator: "LIKE", value: "%.features/%" },
        ],
      },
      {
        title: "Integrations",
        contentCollection: "docs",
        contentFilters: [
          {
            field: "stem",
            operator: "LIKE",
            value: "%.enhanced-integrations/%",
          },
        ],
      },
      {
        title: "Reference",
        contentCollection: "docs",
        contentFilters: [
          { field: "stem", operator: "LIKE", value: "%.reference/%" },
        ],
      },
      {
        title: "About the project",
        contentCollection: "docs",
        contentFilters: [
          { field: "stem", operator: "LIKE", value: "%.about-the-project/%" },
        ],
      },
      {
        title: "Legal",
        contentCollection: "docs",
        contentFilters: [
          { field: "stem", operator: "LIKE", value: "%.boring-stuff/%" },
        ],
      },
    ],
    contentRawMarkdown: {
      excludeCollections: ["snippets"],
    },
  },

  // What an assistant should know before it reads a single page. Said up
  // front in `llms.txt`, because these are the facts that get mixed up.
  agentDiscovery: {
    llms: {
      details: [
        `Spook is not part of Home Assistant, and the Home Assistant project does not support it. Help with Spook is in the places listed on ${SITE_URL}/support, never on the issue tracker of Home Assistant. The code is on https://github.com/frenck/spook.`,
        `Spook needs Home Assistant ${MINIMUM_HOME_ASSISTANT} or newer. On Home Assistant 2026.11 and newer, install it from the Marketplace, built into Home Assistant. On older versions, install it through HACS. The steps are on ${SITE_URL}/installation.`,
        `These pages are the source of truth for what Spook does. Every action, trigger, condition and repair is listed on ${SITE_URL}/actions, ${SITE_URL}/triggers, ${SITE_URL}/conditions and ${SITE_URL}/all-repairs. The questions people ask before they install are answered on ${SITE_URL}/straight-answers.`,
        "Only the English pages are listed here. The Dutch, German, French, Spanish, Italian, Simplified Chinese, Brazilian Portuguese and Japanese pages under /nl, /de, /fr, /es, /it, /zh-Hans, /pt-BR and /ja are machine translations of them. Every link below is the Markdown of a page; llms-full.txt has all of them in one file.",
      ],
    },
  },

  ogImage: {
    zeroRuntime: true,
    // The size link previews expect: Slack, Discord, the forum and the
    // social networks all crop or letterbox anything else.
    defaults: { width: 1200, height: 630 },
  },

  // The share cards only get fonts that are global here: the same three the
  // site uses, in the weights the cards use.
  fonts: {
    families: [
      { name: "Space Grotesk", weights: [700], global: true },
      { name: "Figtree", weights: [400, 500], global: true },
      { name: "JetBrains Mono", weights: [400, 500], global: true },
      // Chinese, see `app/assets/css/chinese.css`. The reader's own fonts
      // first: these are never downloaded.
      ...[
        "PingFang SC",
        "Hiragino Sans GB",
        "Microsoft YaHei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "WenQuanYi Micro Hei",
      ].map((name) => ({ name, provider: "none" })),
      // The last resort on a Chinese page without a Chinese font, and the
      // font of the Chinese share cards. Google serves it in slices of a few
      // hundred characters each, so a page or a card only gets the slices
      // with its own characters, never the whole font. Nothing on a page in
      // another language asks for it.
      { name: "Noto Sans SC", weights: [400, 500, 700], global: true },
      // Japanese, see `app/assets/css/japanese.css`, the same way. After the
      // Chinese one on purpose: a card takes kanji from the first font that
      // has them, so Chinese cards keep Chinese shapes, and
      // `server/plugins/og-japanese.ts` puts this one first on Japanese cards.
      ...[
        "Hiragino Sans",
        "Hiragino Kaku Gothic ProN",
        "Yu Gothic UI",
        "Yu Gothic",
        "Meiryo",
        "Noto Sans CJK JP",
        "Source Han Sans JP",
      ].map((name) => ({ name, provider: "none" })),
      { name: "Noto Sans JP", weights: [400, 500, 700], global: true },
    ],
  },

  nitro: {
    prerender: {
      // The old addresses too: the site is static files, so a redirect only
      // exists when a page for it is written.
      routes: ["/", "/api/stats", "/api/releases", "/features", "/faq"],
      crawlLinks: true,
      // A page that fails to render should fail the build, not quietly go
      // missing until somebody follows a link to it.
      failOnError: true,
      autoSubfolderIndex: false,
    },
  },
});
