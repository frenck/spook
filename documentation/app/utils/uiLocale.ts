import { de, en, es, fr, it, ja, nl, pt_br, zh_cn } from "@nuxt/ui/locale";

// Nuxt UI's own words, like "Close" and "Previous". Only the languages of
// the site, so the others stay out of the bundle: a new language of the site
// goes in here too.
const UI_LOCALES: Record<string, typeof en> = {
  en,
  nl,
  de,
  fr,
  es,
  it,
  "zh-Hans": zh_cn,
  "pt-BR": pt_br,
  ja,
};

/** Nuxt UI's words in a language of the site. */
export function uiLocaleOf(language: string) {
  return UI_LOCALES[language] ?? en;
}
