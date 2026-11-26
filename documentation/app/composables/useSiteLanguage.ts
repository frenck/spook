import {
  localizedScreenshots,
  translatedPages,
} from "#build/site-translations.mjs";

const pagesIn = Object.fromEntries(
  Object.entries(translatedPages).map(([code, paths]) => [
    code,
    new Set(paths),
  ]),
);

/** Whether a page of the site exists in a language. English always does. */
export function isTranslated(path: string, language: string): boolean {
  if (language === DEFAULT_LANGUAGE) {
    return true;
  }

  const [plain] = withoutLanguage(path).split(/[?#]/);
  return pagesIn[language]?.has(plain!.replace(/(.)\/$/, "$1")) ?? false;
}

/**
 * The language somebody wants the site in.
 *
 * What they picked themselves, when they did. Otherwise the first language
 * of their browser that the site has. Only known in the browser.
 */
export const LANGUAGE_STORAGE_KEY = "spook-language";

// The pick of this visit, for a browser that blocks storage. Without it,
// picking English sends somebody straight back to their browser's language.
let pickedThisVisit: string | undefined;

/** Remember the language somebody picked by hand, for good when allowed. */
export function rememberLanguage(code: string): void {
  pickedThisVisit = code;

  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, code);
  } catch {
    // Storage can be blocked. Then the pick lasts as long as the visit.
  }
}

export function preferredLanguage(): string {
  if (import.meta.server) {
    return DEFAULT_LANGUAGE;
  }

  if (pickedThisVisit) {
    return pickedThisVisit;
  }

  const known = LANGUAGES.map((language) => language.code);

  try {
    const picked = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (picked && known.includes(picked)) {
      return picked;
    }
  } catch {
    // Storage can be blocked. The browser's language still works.
  }

  for (const language of navigator.languages ?? [navigator.language]) {
    const code = siteLanguageOfBrowser(language);
    if (code) {
      return code;
    }
  }

  return DEFAULT_LANGUAGE;
}

export function useSiteLanguage() {
  const route = useRoute();

  // The language of the page being read, from its address.
  const language = computed(() => languageOf(route.path));
  const translated = computed(() => language.value !== DEFAULT_LANGUAGE);

  // The page being read, whatever language it is read in.
  const pagePath = computed(() =>
    withoutLanguage(route.path).replace(/(.)\/$/, "$1"),
  );

  /**
   * Where a link on this page should go: the same language as the page, when
   * the target exists in it, and the English page when it does not.
   */
  function localTo(to: string): string {
    if (!to.startsWith("/") || to.startsWith("//")) {
      return to;
    }

    return isTranslated(to, language.value)
      ? inLanguage(to, language.value)
      : withoutLanguage(to);
  }

  /** A screenshot's language: this one when it was made in it, else English. */
  function screenshotLanguage(name: string): string {
    return localizedScreenshots[language.value]?.includes(name)
      ? language.value
      : DEFAULT_LANGUAGE;
  }

  // How dates and numbers are written. English as most of the world writes
  // it: day, month, year.
  const intlLocale = computed(() =>
    language.value === DEFAULT_LANGUAGE ? "en-GB" : language.value,
  );

  return {
    language,
    translated,
    pagePath,
    localTo,
    screenshotLanguage,
    intlLocale,
  };
}
