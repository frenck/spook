/**
 * The search bar of a reference page: what was typed, as words to match.
 *
 * Expects the page to have `ref="index"` on the element holding the search
 * bar and the entries, and `ref="toolbar"` on the search bar itself.
 */
export function useReferenceSearch() {
  const search = ref("");
  const index = useTemplateRef<HTMLElement>("index");
  const toolbar = useTemplateRef<HTMLElement>("toolbar");

  // Every word has to be in there somewhere, so "label area" finds
  // "Labels: Add a label to an area".
  const words = computed(() =>
    search.value.toLowerCase().split(/\s+/).filter(Boolean),
  );

  // Typed halfway down the page, the list shrinks out from under you and
  // the few results end up above the screen, behind the search bar. Bring
  // the top of the list back to just under it.
  watch(search, async () => {
    await nextTick();
    if (!search.value || !index.value || !toolbar.value) {
      return;
    }

    const stuckAt = parseFloat(getComputedStyle(toolbar.value).top) || 0;
    const top = index.value.getBoundingClientRect().top;
    if (top < stuckAt) {
      window.scrollTo({ top: window.scrollY + top - stuckAt });
    }
  });

  // Following a link to an entry, from the table of contents or from
  // another entry, should land on it, also when the search hides it.
  const route = useRoute();
  watch(
    () => route.hash,
    async (hash) => {
      if (!search.value || !hash) {
        return;
      }

      search.value = "";
      await nextTick();
      document
        .getElementById(decodeURIComponent(hash.slice(1)))
        ?.scrollIntoView();
    },
  );

  return { search, words };
}
