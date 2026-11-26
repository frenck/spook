const FORM = "https://github.com/frenck/spook/issues/new";

/**
 * Where to report a problem with a translated page: an issue form, already
 * filled in with the language and the page.
 */
export function translationReportUrl(language: string, path: string): string {
  const name = LANGUAGES.find(({ code }) => code === language)?.english ?? "";
  const query = new URLSearchParams({
    template: "translation.yml",
    language: name,
    page: `https://spook.boo${path}`,
  });

  return `${FORM}?${query}`;
}
