<script setup lang="ts">
// The way into the docs: every part of them, with how much is in it. The
// numbers are counted from the pages themselves, so they never go stale.
const counts = await useSpookCounts();
const { currentSection } = useDocsNavigation();
const { t } = useI18n();
const { localTo } = useSiteLanguage();

// How many pages a group of the docs has, without its own overview page.
function pagesIn(folder: string): number {
  const group = currentSection.value?.groups.find(
    (candidate) => candidate.path === `/${folder}`,
  );
  return Math.max((group?.children?.length ?? 1) - 1, 0);
}

const parts = computed(() => [
  {
    title: t("hub.integrations"),
    to: "/enhanced-integrations",
    icon: "i-mdi-puzzle-outline",
    count: t(
      "hub.integrationsCount",
      { count: counts.value.integrations },
      counts.value.integrations,
    ),
    description: t("hub.integrationsText"),
  },
  {
    title: t("hub.coreExtensions"),
    to: "/core-extensions",
    icon: "i-spook-home-assistant",
    count: t(
      "hub.pages",
      { count: pagesIn("core-extensions") },
      pagesIn("core-extensions"),
    ),
    description: t("hub.coreExtensionsText"),
  },
  {
    title: t("hub.helpers"),
    to: "/helpers",
    icon: "i-mdi-tools",
    count: t(
      "hub.helpersCount",
      { count: pagesIn("helpers") },
      pagesIn("helpers"),
    ),
    description: t("hub.helpersText"),
  },
  {
    title: t("hub.triggersConditions"),
    to: "/other-features",
    icon: "i-mdi-ray-start-arrow",
    count: t("hub.triggersConditionsCount", {
      triggers: counts.value.triggers,
      conditions: counts.value.conditions,
    }),
    description: t("hub.triggersConditionsText"),
  },
  {
    title: t("hub.assistants"),
    to: "/assistants",
    icon: "i-mdi-robot-happy-outline",
    count: t("hub.assistantsCount"),
    description: t("hub.assistantsText"),
  },
]);

const lookups = computed(() => [
  {
    title: t("hub.actions"),
    to: "/actions",
    icon: "i-mdi-lightning-bolt-outline",
    count: counts.value.actions,
  },
  {
    title: t("hub.triggers"),
    to: "/triggers",
    icon: "i-mdi-ray-start-arrow",
    count: counts.value.triggers,
  },
  {
    title: t("hub.conditions"),
    to: "/conditions",
    icon: "i-mdi-source-branch",
    count: counts.value.conditions,
  },
  {
    title: t("hub.repairs"),
    to: "/all-repairs",
    icon: "i-mdi-wrench-outline",
    count: counts.value.repairs,
  },
  {
    title: t("hub.blueprints"),
    to: "/blueprints",
    icon: "i-mdi-floor-plan",
  },
  {
    title: t("hub.glossary"),
    to: "/glossary",
    icon: "i-mdi-book-alphabet",
  },
]);
</script>

<template>
  <div class="not-prose my-10 space-y-12">
    <div class="grid gap-4 sm:grid-cols-2">
      <ULink
        v-for="(part, index) in parts"
        :key="part.to"
        :to="localTo(part.to)"
        class="reveal group flex flex-col gap-3 rounded-2xl p-5 ring ring-default transition hover:ring-primary/60"
        :class="
          index === 0
            ? 'bg-(image:--screenshot-backdrop) sm:col-span-2 sm:p-7'
            : ''
        "
      >
        <div class="flex items-center justify-between gap-3">
          <span
            class="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary"
          >
            <UIcon :name="part.icon" class="size-5.5" />
          </span>
          <span
            class="font-mono text-[11px] font-medium tracking-[0.1em] text-muted uppercase"
          >
            {{ part.count }}
          </span>
        </div>

        <h2 class="font-display text-xl font-bold text-highlighted">
          {{ part.title }}
        </h2>
        <p class="text-[15px]/6 text-muted">{{ part.description }}</p>

        <span
          class="mt-auto inline-flex items-center gap-1 pt-1 text-sm font-medium text-primary"
        >
          {{ t("hub.open") }}
          <UIcon
            name="i-mdi-arrow-right"
            class="size-4 transition group-hover:translate-x-1"
          />
        </span>
      </ULink>
    </div>

    <div>
      <p
        class="mb-4 font-mono text-xs font-medium tracking-[0.14em] text-primary uppercase"
      >
        {{ t("hub.lookItUp") }}
      </p>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <ULink
          v-for="lookup in lookups"
          :key="lookup.to"
          :to="localTo(lookup.to)"
          class="flex items-center gap-2.5 rounded-xl px-3.5 py-3 ring ring-default transition hover:ring-primary/60"
        >
          <UIcon :name="lookup.icon" class="size-5 shrink-0 text-primary" />
          <span class="font-display font-bold text-highlighted">
            {{ lookup.title }}
          </span>
          <span
            v-if="lookup.count"
            class="ms-auto font-mono text-xs text-muted"
          >
            {{ lookup.count }}
          </span>
        </ULink>
      </div>
    </div>
  </div>
</template>
