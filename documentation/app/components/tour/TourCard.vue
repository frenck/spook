<script setup lang="ts">
// One part of the tour to pick: the screenshot it opens with, and what it
// is about. Used where the tour starts, and at the end of each part for the
// ones you have not seen yet.
defineProps<{
  tour: {
    stem: string;
    description: string;
    hero: { headline: string; title: string; screenshot: string; alt: string };
  };
}>();

const { t } = useI18n();
const { localTo } = useSiteLanguage();
</script>

<template>
  <ULink
    :to="localTo(tourPath(tour.stem))"
    class="group flex flex-col rounded-2xl p-2 ring ring-default transition hover:-translate-y-1 hover:ring-primary/60"
  >
    <Screenshot
      :name="tour.hero.screenshot"
      :alt="tour.hero.alt"
      even
      class="!my-0"
    />
    <div class="flex flex-1 flex-col gap-2 p-4">
      <p class="font-mono text-xs tracking-[0.1em] text-primary uppercase">
        {{ tour.hero.headline }}
      </p>
      <h2 class="font-display text-2xl font-bold text-highlighted">
        {{ tour.hero.title }}
      </h2>
      <p class="text-muted">{{ tour.description }}</p>
      <span
        class="mt-auto inline-flex items-center gap-1 pt-3 text-sm font-medium text-primary"
      >
        {{ t("tour.card") }}
        <UIcon
          name="i-mdi-arrow-right"
          class="size-4 transition group-hover:translate-x-1"
        />
      </span>
    </div>
  </ULink>
</template>
