<script setup lang="ts">
/**
 * Every repair Spook can raise, on one page.
 *
 * Home Assistant shows a repair by its name, not by the integration it
 * belongs to, so this is where to look one up. The list is read from the
 * integration pages: a repair documented there is in here, and nowhere else
 * to keep up to date.
 */
interface Page {
  path: string;
  title: string;
  meta?: { repairs?: { id: string; title: string; summary: string }[] };
}

const { data: pages } = await useAsyncData(
  "repair-index",
  () =>
    queryCollection("docs")
      .where("stem", "LIKE", "%.enhanced-integrations/%")
      .where("stem", "NOT LIKE", "%/.navigation")
      .order("title", "ASC")
      .select("path", "title", "meta")
      .all() as Promise<Page[]>,
);

const { t } = useI18n();
const { localTo } = useSiteLanguage();

const search = ref("");

const words = computed(() =>
  search.value.toLowerCase().split(/\s+/).filter(Boolean),
);

const groups = computed(() =>
  (pages.value ?? [])
    .map((page) => ({
      ...page,
      icon: `https://brands.home-assistant.io/${page.path.slice(1).replaceAll("-", "_")}/icon.png`,
      repairs: (page.meta?.repairs ?? []).filter((repair) => {
        const text =
          `${page.title} ${repair.title} ${repair.summary}`.toLowerCase();
        return words.value.every((word) => text.includes(word));
      }),
    }))
    .filter((page) => page.repairs.length),
);

const total = computed(() =>
  (pages.value ?? []).reduce(
    (count, page) => count + (page.meta?.repairs?.length ?? 0),
    0,
  ),
);

const shown = computed(() =>
  groups.value.reduce((count, group) => count + group.repairs.length, 0),
);
</script>

<template>
  <div class="not-prose my-8">
    <div
      class="sticky top-(--ui-header-height) z-10 -mx-4 flex items-center gap-3 border-b border-default bg-default/85 px-4 py-3 backdrop-blur-md sm:-mx-6 sm:px-6 lg:mx-0 lg:px-0"
    >
      <UInput
        v-model="search"
        icon="i-mdi-magnify"
        size="lg"
        :placeholder="t('repairs.placeholder')"
        :aria-label="t('repairs.label')"
        class="flex-1"
      />
      <p
        class="shrink-0 font-mono text-xs tracking-[0.1em] text-muted uppercase"
        aria-live="polite"
      >
        <template v-if="search">
          {{ t("reference.shown", { shown, total }) }}
        </template>
        <template v-else>
          {{ t("repairs.count", { count: total }, total) }}
        </template>
      </p>
    </div>

    <section v-for="group in groups" :key="group.path" class="mt-8">
      <h2 class="mb-3 flex items-center gap-3">
        <img :src="group.icon" alt="" class="size-7 object-contain" />
        <ULink
          :to="localTo(group.path)"
          class="font-display text-xl font-bold text-highlighted hover:text-primary"
        >
          {{ group.title }}
        </ULink>
        <span class="font-mono text-xs text-dimmed">
          {{ group.repairs.length }}
        </span>
      </h2>

      <div
        class="divide-y divide-default overflow-hidden rounded-xl border border-default"
      >
        <ULink
          v-for="repair in group.repairs"
          :key="repair.id"
          :to="localTo(`${group.path}#${repair.id}`)"
          class="group flex items-start gap-3 px-4 py-3.5 transition-colors hover:bg-elevated/50 sm:px-5"
        >
          <div class="min-w-0 flex-1">
            <p class="font-display font-bold text-highlighted">
              {{ repair.title }}
            </p>
            <p class="text-[15px]/6 text-muted">{{ repair.summary }}</p>
          </div>
          <UIcon
            name="i-mdi-arrow-right"
            class="mt-1 size-5 shrink-0 text-dimmed transition group-hover:translate-x-1 group-hover:text-primary"
          />
        </ULink>
      </div>
    </section>

    <p v-if="!groups.length" class="py-12 text-center text-muted">
      {{ t("repairs.none") }}
    </p>
  </div>
</template>
