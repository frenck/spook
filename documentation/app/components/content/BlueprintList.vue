<script setup lang="ts">
// Blueprints by others that use what Spook adds, from
// content/data/blueprints.yml. Checked by hand before they go in.
const { data } = await useAsyncData("blueprints", () =>
  queryCollection("blueprints").first(),
);

const { t } = useI18n();
const { intlLocale } = useSiteLanguage();

// The label of a kind is `blueprints.<kind>` in the site's own words.
const icons: Record<string, string> = {
  automation: "i-mdi-robot-outline",
  script: "i-mdi-script-text-outline",
  template: "i-mdi-code-braces",
};

const blueprints = computed(() =>
  [...(data.value?.blueprints ?? [])].sort((a, b) =>
    b.date.localeCompare(a.date),
  ),
);

function when(date: string): string {
  return new Date(date).toLocaleDateString(intlLocale.value, {
    month: "short",
    year: "numeric",
  });
}
</script>

<template>
  <UPageGrid v-if="blueprints.length" class="not-prose my-8 lg:grid-cols-2">
    <UPageCard
      v-for="blueprint in blueprints"
      :key="blueprint.url"
      :icon="icons[blueprint.kind]"
      :title="blueprint.title"
      :description="blueprint.summary"
      variant="subtle"
      class="reveal"
      :ui="{
        container: 'justify-between gap-5',
        title: 'font-display text-lg',
        description: 'text-base',
      }"
    >
      <template #footer>
        <div class="flex flex-col gap-4">
          <div class="flex flex-wrap gap-1.5">
            <UBadge
              v-for="action in blueprint.uses"
              :key="action"
              :label="action"
              color="neutral"
              variant="soft"
              class="font-mono"
            />
          </div>
          <p class="text-sm text-muted">
            {{
              t("blueprints.byline", {
                kind: t(`blueprints.${blueprint.kind}`),
                author: blueprint.author,
              })
            }}
            · {{ when(blueprint.date) }}
          </p>
          <div class="flex flex-wrap gap-2">
            <UButton
              v-if="blueprint.import"
              :to="blueprint.import"
              target="_blank"
              icon="i-mdi-import"
              :label="t('blueprints.import')"
            />
            <UButton
              :to="blueprint.url"
              target="_blank"
              color="neutral"
              variant="outline"
              icon="i-mdi-open-in-new"
              :label="t('blueprints.readMore')"
            />
          </div>
        </div>
      </template>
    </UPageCard>
  </UPageGrid>
</template>
