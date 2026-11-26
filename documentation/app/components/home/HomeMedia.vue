<script setup lang="ts">
/**
 * Spook in the media: videos, articles and podcasts, on a strip that drifts
 * the other way from the quotes above it. The full list is on the media
 * page; this is the teaser for it.
 */
const { data } = await useAsyncData("media", () =>
  queryCollection("media").first(),
);

const { t } = useI18n();
const { language, localTo } = useSiteLanguage();

interface Item {
  to: string;
  title: string;
  byline: string;
  icon: string;
  language: string;
  date: string;
  image?: string;
  crop?: boolean;
}

const items = computed<Item[]>(() => {
  const all: Item[] = [
    ...(data.value?.videos ?? []).map((video) => ({
      to: `https://www.youtube.com/watch?v=${video.youtube}${video.start ? `&t=${video.start}s` : ""}`,
      title: video.title,
      byline: video.author,
      icon: "i-mdi-youtube",
      language: video.language,
      date: video.date,
      image: `https://i.ytimg.com/vi/${video.youtube}/hqdefault.jpg`,
      crop: true,
    })),
    ...(data.value?.articles ?? []).map((article) => ({
      to: article.url,
      title: article.title,
      byline: article.author,
      icon: "i-mdi-post-outline",
      language: article.language,
      date: article.date,
      image: article.image,
    })),
    ...(data.value?.podcasts ?? []).map((podcast) => ({
      to: podcast.url,
      title: podcast.title,
      byline: podcast.show,
      icon: "i-mdi-microphone-outline",
      language: podcast.language,
      date: podcast.date,
      image: podcast.image,
    })),
  ];

  // What is in the reader's own language first, then the newest.
  const own = (item: Item) => (item.language === language.value ? 0 : 1);
  return all.sort((a, b) => own(a) - own(b) || b.date.localeCompare(a.date));
});

// The same slow drift as the quotes, the other way round. Set once mounted,
// and never for whoever asked their system for less motion.
const drift = ref<false | Record<string, unknown>>(false);
onMounted(() => {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }

  drift.value = {
    speed: 0.4,
    direction: "backward",
    startDelay: 0,
    stopOnInteraction: false,
    stopOnMouseEnter: true,
  };
});
</script>

<template>
  <!-- A grid item grows to fit its content unless told otherwise, and a
       carousel's content is every card in a row. -->
  <div v-if="items.length" class="mt-4 w-full min-w-0">
    <UCarousel
      v-slot="{ item }"
      :items="items"
      loop
      :auto-scroll="drift"
      wheel-gestures
      align="start"
      class="w-full min-w-0"
      :ui="{
        container: 'items-stretch',
        item: 'flex basis-3/4 sm:basis-1/3 lg:basis-1/4 ps-4',
        viewport:
          'py-2 [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]',
      }"
    >
      <MediaCard v-bind="item" class="h-full w-full" />
    </UCarousel>

    <div class="mt-6 flex justify-center">
      <UButton
        :to="localTo('/media')"
        :label="t('home.media.more', { count: items.length })"
        color="neutral"
        variant="ghost"
        trailing-icon="i-mdi-arrow-right"
        :ui="{ label: 'whitespace-normal text-center' }"
        class="max-w-full"
      />
    </div>
  </div>
</template>
