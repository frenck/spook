/**
 * Take somebody to their own language, when the page exists in it.
 *
 * A link from inside Home Assistant, or from anywhere else, points at the
 * English page: `/automation`. Whoever follows it and reads Dutch gets
 * `/nl/automation`, with the anchor they were sent to. A page that was never
 * translated stays English, and nobody is moved away from a language they
 * picked by hand.
 *
 * The first page somebody lands on is moved even earlier, by the few lines
 * in the head of the page (see `app.vue`), before anything is on screen.
 * This covers every page after that.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const language = languageOf(to.path);

  // The site's own words follow the page: Dutch menus on a Dutch page.
  const { $i18n } = useNuxtApp();
  if ($i18n.locale.value !== language) {
    await $i18n.setLocale(language);
  }

  if (import.meta.server || language !== DEFAULT_LANGUAGE) {
    return;
  }

  const wanted = preferredLanguage();
  if (wanted === DEFAULT_LANGUAGE || !isTranslated(to.path, wanted)) {
    return;
  }

  return navigateTo(
    { path: inLanguage(to.path, wanted), query: to.query, hash: to.hash },
    { replace: true },
  );
});
