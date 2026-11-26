<script setup lang="ts">
const { t } = useI18n();
const { localTo, intlLocale } = useSiteLanguage();

// The pages the navigation already loaded: with their title and description
// in the language being read, where the page is translated.
const { items } = useDocsNavigation();

const integrations = computed(() =>
  (items.value ?? [])
    .filter(
      (item) =>
        item.stem.includes(".enhanced-integrations/") &&
        item.path !== "/enhanced-integrations" &&
        !item.stem.endsWith("/.navigation"),
    )
    .map((item) => ({
      ...item,
      meta: item.meta as { offers?: string[] } | undefined,
    }))
    .sort((a, b) => a.title.localeCompare(b.title, intlLocale.value)),
);

const filters = computed(() => [
  { label: t("catalog.all"), value: "all" },
  {
    label: t("catalog.repairs"),
    value: "repairs",
    icon: "i-mdi-ghost-outline",
  },
  {
    label: t("catalog.actions"),
    value: "actions",
    icon: "i-mdi-lightning-bolt-outline",
  },
  { label: t("catalog.entities"), value: "entities", icon: "i-mdi-chip" },
]);

const search = ref("");
const filter = ref("all");

const shown = computed(() => {
  const query = search.value.trim().toLowerCase();
  return (integrations.value ?? []).filter((integration) => {
    if (
      filter.value !== "all" &&
      !integration.meta?.offers?.includes(filter.value)
    ) {
      return false;
    }

    return (
      !query ||
      integration.title.toLowerCase().includes(query) ||
      integration.description?.toLowerCase().includes(query)
    );
  });
});

// Home Assistant's brand images are named after the integration's domain,
// which is the page's address with underscores.
function icon(path: string): string {
  return `https://brands.home-assistant.io/${path
    .slice(1)
    .replaceAll("-", "_")}/icon.png`;
}

function count(value: string): number {
  return (integrations.value ?? []).filter(
    (integration) =>
      value === "all" || integration.meta?.offers?.includes(value),
  ).length;
}
</script>

<template>
  <div class="not-prose space-y-6">
    <div class="flex flex-col sm:flex-row gap-3">
      <UInput
        v-model="search"
        icon="i-mdi-magnify"
        :placeholder="t('catalog.placeholder')"
        class="flex-1"
      />
      <UTabs
        v-model="filter"
        :items="filters.map((item) => ({ ...item, badge: count(item.value) }))"
        :content="false"
        size="sm"
        variant="pill"
        :ui="{ leadingIcon: 'hidden sm:block', label: 'overflow-visible' }"
      />
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <UPageCard
        v-for="integration in shown"
        :key="integration.path"
        :to="localTo(integration.path)"
        :title="integration.title"
        :description="integration.description"
        variant="outline"
        :ui="{ description: 'line-clamp-2' }"
      >
        <template #leading>
          <img
            :src="icon(integration.path)"
            :alt="t('catalog.logo', { title: integration.title })"
            class="size-8"
            loading="lazy"
          />
        </template>
      </UPageCard>
    </div>

    <p v-if="!shown.length" class="text-muted text-center py-8">
      {{ t("catalog.none") }}
    </p>
  </div>
</template>
