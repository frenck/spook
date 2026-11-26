/**
 * The languages of the site.
 *
 * English is the source, written by people. Every other language is a
 * machine translation of it, made by the pipeline in `translations/`.
 */
export interface SiteLanguage {
  code: string;
  // Its own name for itself, for the language switcher.
  name: string;
  // What the "report a translation problem" form calls it.
  english: string;
  // The round flag of the language, from `circle-flags`, when its code is
  // not the flag's name.
  flag?: string;
}

export const DEFAULT_LANGUAGE = "en";

export const LANGUAGES: SiteLanguage[] = [
  { code: "en", name: "English", english: "English" },
  { code: "nl", name: "Nederlands", english: "Dutch" },
  { code: "de", name: "Deutsch", english: "German" },
  { code: "fr", name: "Français", english: "French" },
  { code: "es", name: "Español", english: "Spanish" },
  { code: "it", name: "Italiano", english: "Italian" },
  {
    code: "zh-Hans",
    name: "简体中文",
    english: "Chinese (Simplified)",
    flag: "zh",
  },
  {
    code: "pt-BR",
    name: "Português (Brasil)",
    english: "Brazilian Portuguese",
    flag: "pt-br",
  },
  { code: "ja", name: "日本語", english: "Japanese" },
];

/**
 * Whether search engines may index the translations.
 *
 * Off while the translations are a pilot. This one switch decides three
 * things together: the `noindex` on every translated page, whether the
 * translated pages are in the sitemap, and whether pages tell search engines
 * about their other languages (`hreflang`). Turn it on and the translated
 * pages become search results of their own, each pointing at the others,
 * with English as the default.
 */
export const INDEX_TRANSLATIONS = true;

export const TRANSLATED_LANGUAGES = LANGUAGES.filter(
  (language) => language.code !== DEFAULT_LANGUAGE,
);

const PREFIX = new RegExp(
  `^/(${TRANSLATED_LANGUAGES.map((language) => language.code).join("|")})(?=/|$)`,
);

/** The language a path is in, going by its prefix: `/nl/automation` is Dutch. */
export function languageOf(path: string): string {
  return path.match(PREFIX)?.[1] ?? DEFAULT_LANGUAGE;
}

/** A path without its language: `/nl/automation` is `/automation`. */
export function withoutLanguage(path: string): string {
  return path.replace(PREFIX, "") || "/";
}

/** A path in a language: `/automation` in Dutch is `/nl/automation`. */
export function inLanguage(path: string, language: string): string {
  const plain = withoutLanguage(path);
  if (language === DEFAULT_LANGUAGE) {
    return plain;
  }

  return plain === "/" ? `/${language}` : `/${language}${plain}`;
}

/** The round flag of a language, for the language menu and the media page. */
export function flagOf(code: string): string {
  const flag = LANGUAGES.find((language) => language.code === code)?.flag;
  return `i-circle-flags-lang-${flag ?? code}`;
}

/**
 * The name a language has in Nuxt Content: the code, in a form that does as
 * part of a table name. `zh-Hans` is `zh_hans`, so its pages are the
 * collection `docs_zh_hans`.
 */
export function collectionCode(code: string): string {
  return code.toLowerCase().replace(/-/g, "_");
}

/**
 * The language of the site that a language of the browser asks for, if any.
 *
 * Mostly the first two letters: `de-AT` reads German. Chinese is the
 * exception, because two letters do not say which script. Simplified is
 * what mainland China, Singapore and Malaysia write; Taiwan, Hong Kong and
 * Macau write Traditional, and get English rather than a script they did
 * not ask for.
 *
 * Portuguese is the other one. The site has Brazilian Portuguese, and every
 * Portuguese reader gets it, from Portugal and Angola too: another country's
 * spelling reads a lot easier than English.
 *
 * `app.vue` has the same rule in plain JavaScript, for the first page.
 */
export function siteLanguageOfBrowser(tag: string): string | undefined {
  const lower = tag.toLowerCase();
  const code = /^zh(-hans|-cn|-sg|-my|$)/.test(lower)
    ? "zh-Hans"
    : /^pt(-|$)/.test(lower)
      ? "pt-BR"
      : lower.slice(0, 2);

  return LANGUAGES.some((language) => language.code === code)
    ? code
    : undefined;
}
