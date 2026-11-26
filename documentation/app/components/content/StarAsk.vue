<script setup lang="ts">
// The one place the docs ask for something back: right after Spook did
// something for you. Never before, and never as a popup.
const { data: outside } = await useFetch<{ stars: number | null }>(
  "/api/stats",
);

const { t } = useI18n();
const { intlLocale } = useSiteLanguage();
</script>

<template>
  <div
    class="not-prose my-10 flex flex-col gap-4 rounded-2xl bg-(image:--screenshot-backdrop) p-6 ring ring-default sm:flex-row sm:items-center"
  >
    <img
      src="/images/spook-ghost.png"
      alt=""
      class="ghost-float size-12 shrink-0"
    />

    <div class="flex-1">
      <p class="font-display text-lg font-bold text-highlighted">
        {{ t("star.title") }}
      </p>
      <p class="mt-1 text-[15px]/6 text-muted">
        {{ t("star.text") }}
      </p>
    </div>

    <div class="flex shrink-0 flex-wrap gap-2">
      <UButton
        to="https://github.com/frenck/spook"
        target="_blank"
        icon="i-mdi-star-outline"
      >
        {{ t("star.button") }}
        <span v-if="outside?.stars" class="font-mono text-xs opacity-80">
          {{ outside.stars.toLocaleString(intlLocale) }}
        </span>
      </UButton>
      <UButton
        to="https://github.com/sponsors/frenck"
        target="_blank"
        color="neutral"
        variant="ghost"
        icon="i-mdi-heart-outline"
        :label="t('star.sponsor')"
      />
    </div>
  </div>
</template>
