<script setup lang="ts">
// What changed in Spook lately: the notes of the latest releases, the way
// they were written for GitHub. Fetched while the site is built.
const { data: releases } =
  await useFetch<
    { version: string; date: string; url: string; notes: never }[]
  >("/api/releases");

const ALL = "https://github.com/frenck/spook/releases";

const { t } = useI18n();
const { intlLocale } = useSiteLanguage();

function when(date: string): string {
  return new Date(date).toLocaleDateString(intlLocale.value, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}
</script>

<template>
  <div class="my-8 space-y-6">
    <!-- One card per release, so where one ends and the next begins is
         never in doubt, however long the notes. -->
    <article
      v-for="(release, index) in releases ?? []"
      :key="release.version"
      class="rounded-2xl border border-default p-5 sm:p-7"
      :class="index === 0 ? 'ring-1 ring-primary/30' : ''"
    >
      <header
        class="not-prose mb-5 flex flex-wrap items-center gap-3 border-b border-default pb-4"
      >
        <h2
          :id="release.version.replaceAll('.', '-')"
          class="scroll-mt-[calc(var(--ui-header-height)+1.5rem)] font-display text-2xl font-bold text-highlighted"
        >
          {{ release.version }}
        </h2>
        <UBadge
          v-if="index === 0"
          :label="t('releases.latest')"
          class="font-mono"
        />
        <span class="font-mono text-xs tracking-[0.08em] text-muted uppercase">
          {{ when(release.date) }}
        </span>
        <UButton
          :to="release.url"
          target="_blank"
          color="neutral"
          variant="link"
          size="sm"
          trailing-icon="i-mdi-arrow-top-right"
          :label="t('releases.onGitHub')"
          class="ms-auto"
        />
      </header>

      <MDCRenderer
        :body="release.notes"
        tag="div"
        class="*:first:mt-0 *:last:mb-0"
      />
    </article>

    <div
      class="not-prose mt-4 flex flex-col gap-3 rounded-xl border border-default bg-elevated/40 p-5 sm:flex-row sm:items-center sm:justify-between"
    >
      <p class="text-sm text-muted">
        <template v-if="releases?.length">
          {{ t("releases.older") }}
        </template>
        <template v-else>
          {{ t("releases.failed") }}
        </template>
      </p>
      <UButton
        :to="ALL"
        target="_blank"
        color="neutral"
        variant="outline"
        icon="i-mdi-github"
        :label="t('releases.all')"
        class="shrink-0"
      />
    </div>
  </div>
</template>
