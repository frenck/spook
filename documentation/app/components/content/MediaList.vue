<script setup lang="ts">
const { data } = await useAsyncData("media", () =>
  queryCollection("media").first(),
);

const { t } = useI18n();

function newestFirst<T extends { date: string }>(items: T[] = []): T[] {
  return [...items].sort((a, b) => b.date.localeCompare(a.date));
}

// Videos link to YouTube instead of being embedded, so the page does not
// load a player, or YouTube itself, for every video on it.
function watch(id: string, start?: number): string {
  return `https://www.youtube.com/watch?v=${id}${start ? `&t=${start}s` : ""}`;
}

const sections = computed(() => [
  {
    title: t("media.videos"),
    items: newestFirst(data.value?.videos).map((video) => ({
      to: watch(video.youtube, video.start),
      title: video.title,
      byline: video.author,
      icon: "i-mdi-youtube",
      language: video.language,
      date: video.date,
      image: `https://i.ytimg.com/vi/${video.youtube}/hqdefault.jpg`,
      crop: true,
    })),
  },
  {
    title: t("media.articles"),
    items: newestFirst(data.value?.articles).map((article) => ({
      to: article.url,
      title: article.title,
      byline: article.author,
      icon: "i-mdi-post-outline",
      language: article.language,
      date: article.date,
      image: article.image,
    })),
  },
  {
    title: t("media.podcasts"),
    items: newestFirst(data.value?.podcasts).map((podcast) => ({
      to: podcast.url,
      title: podcast.title,
      byline: podcast.show,
      icon: "i-mdi-microphone-outline",
      language: podcast.language,
      date: podcast.date,
      image: podcast.image,
      description: podcast.note,
    })),
  },
]);
</script>

<template>
  <div v-if="data" class="not-prose space-y-14">
    <section v-for="section in sections" :key="section.title">
      <h2 class="mb-6 text-2xl font-semibold text-highlighted">
        {{ section.title }}
        <UBadge
          color="neutral"
          variant="subtle"
          :label="String(section.items.length)"
          class="ms-2 align-middle"
        />
      </h2>
      <UPageGrid class="lg:grid-cols-2 xl:grid-cols-2">
        <MediaCard v-for="item in section.items" :key="item.to" v-bind="item" />
      </UPageGrid>
    </section>
  </div>
</template>
