interface Item {
  path: string;
  stem: string;
  meta?: { counts?: Record<string, number>; sections?: number };
}

/**
 * How much Spook has, counted from the documentation itself, so the numbers
 * on the marketing pages grow with Spook instead of going stale in a
 * sentence somewhere.
 */
export async function useSpookCounts() {
  const { data: items } = await useAsyncData(
    "spook-counts",
    () =>
      queryCollection("docs").select("path", "stem", "meta").all() as Promise<
        Item[]
      >,
  );

  return computed(() => {
    const all = items.value ?? [];
    const sectionsOf = (path: string) =>
      all.find((item) => item.path === path)?.meta?.sections ?? 0;
    const integrations = all.filter(
      (item) =>
        item.stem.includes(".enhanced-integrations/") &&
        !item.stem.endsWith("/.navigation") &&
        item.path !== "/enhanced-integrations",
    );

    return {
      actions: sectionsOf("/actions"),
      triggers: sectionsOf("/triggers"),
      conditions: sectionsOf("/conditions"),
      integrations: integrations.length,
      repairs: all.reduce(
        (total, item) => total + (item.meta?.counts?.repairs ?? 0),
        0,
      ),
    };
  });
}
