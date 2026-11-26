<script setup lang="ts">
// People's own words: never translated, whatever language the page is in.
const { data } = await useAsyncData("quotes", () =>
  queryCollection("quotes").first(),
);

const { t } = useI18n();
const { intlLocale, language } = useSiteLanguage();

const platforms: Record<string, { icon: string; name: string }> = {
  reddit: { icon: "i-mdi-reddit", name: "Reddit" },
  forum: { icon: "i-spook-home-assistant", name: "Home Assistant forum" },
  github: { icon: "i-mdi-github", name: "GitHub" },
  mastodon: { icon: "i-mdi-mastodon", name: "Mastodon" },
  bluesky: { icon: "i-mdi-butterfly-outline", name: "Bluesky" },
  x: { icon: "i-mdi-alpha-x", name: "X" },
  youtube: { icon: "i-mdi-youtube", name: "YouTube" },
  blog: { icon: "i-mdi-post-outline", name: "Blog" },
  "hacker-news": { icon: "i-mdi-alpha-y-box-outline", name: "Hacker News" },
};

type Quote = NonNullable<typeof data.value>["quotes"][number];

// The copy of the avatar that scripts/quote-avatars.mjs keeps, by the same
// name it gives it.
function avatar(quote: Quote): string | undefined {
  if (!quote.avatar) {
    return undefined;
  }
  const name = `${quote.platform}-${quote.author}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `/images/quotes/${name}.webp`;
}

function when(date?: string): string | undefined {
  return date
    ? new Date(date).toLocaleDateString(intlLocale.value, {
        month: "short",
        year: "numeric",
      })
    : undefined;
}

// The English ones everywhere, and the ones in the language of the page on
// that page. A quote in Dutch is somebody's own words: it stays Dutch, and
// shows where Dutch is read.
const shown = computed(() =>
  (data.value?.quotes ?? []).filter(
    (quote) => !quote.language || quote.language === language.value,
  ),
);

// Newest first, three to a column: the carousel scrolls through columns.
const ROWS = 3;
const columns = computed(() => {
  const quotes = [...shown.value].sort((a, b) =>
    (b.date ?? "").localeCompare(a.date ?? ""),
  );
  const result: Quote[][] = [];
  for (let index = 0; index < quotes.length; index += ROWS) {
    result.push(quotes.slice(index, index + ROWS));
  }
  return result;
});

// A pinboard, not a spreadsheet: every card hangs a little crooked, the
// columns don't line up, and some cards stand out. All of it picked by
// position, never at random, so the server and the browser agree on it.
const TILTS = [
  "-rotate-[1.2deg]",
  "rotate-[0.8deg]",
  "-rotate-[0.4deg]",
  "rotate-[1.4deg]",
  "rotate-[0.3deg]",
  "-rotate-[0.9deg]",
  "rotate-[0.6deg]",
];
const DROPS = ["pt-0", "pt-14", "pt-6"];

// A short quote is a shout: bigger letters.
const SHOUT = 90;

function card(quote: Quote, column: number, row: number) {
  const position = column * ROWS + row;
  const shout = quote.quote.length <= SHOUT;
  const tinted = position % 5 === 2;

  return {
    class: [
      "transition duration-300 ease-out hover:z-10 hover:-translate-y-1 hover:scale-[1.02] hover:rotate-0",
      TILTS[position % TILTS.length],
      tinted ? "bg-primary/10 ring-primary/30" : "",
    ],
    description: shout
      ? "font-display text-xl sm:text-2xl font-bold text-highlighted leading-snug"
      : "text-base text-default leading-relaxed",
  };
}

// A slow, endless drift through the wall, so people see more than the first
// nine. It holds still under the mouse, arrows included, so whoever reads a
// quote keeps it. Set once mounted: the server can't know whether someone
// asked their system for less motion, and then it never moves at all.
const drift = ref<false | Record<string, unknown>>(false);
onMounted(() => {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }

  drift.value = {
    speed: 0.5,
    startDelay: 0,
    stopOnInteraction: false,
    stopOnMouseEnter: true,
    // The whole carousel, not only the strip of cards, so reaching for an
    // arrow pauses it too.
    rootNode: (viewport: HTMLElement) => viewport.parentElement,
  };
});
</script>

<template>
  <UPageSection
    v-if="data?.quotes?.length"
    :headline="t('home.quotes.headline')"
    :title="t('home.quotes.title')"
    :description="t('home.quotes.description', { count: shown.length })"
    class="border-t border-muted"
  >
    <UCarousel
      v-slot="{ item: column, index: columnIndex }"
      :items="columns"
      arrows
      loop
      :auto-scroll="drift"
      wheel-gestures
      align="start"
      slides-to-scroll="auto"
      :prev="{ color: 'neutral', variant: 'outline', size: 'lg' }"
      :next="{ color: 'neutral', variant: 'outline', size: 'lg' }"
      prev-icon="i-mdi-arrow-left"
      next-icon="i-mdi-arrow-right"
      class="reveal w-full min-w-0"
      :ui="{
        item: 'basis-full sm:basis-1/2 lg:basis-1/3',
        container: 'items-start',
        // Room for the crooked cards, so their corners aren't clipped, and
        // soft edges: cards drift in and out instead of being sliced off.
        viewport:
          'py-6 [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]',
      }"
    >
      <div
        class="flex flex-col gap-5 px-2"
        :class="DROPS[columnIndex % DROPS.length]"
      >
        <UPageCard
          v-for="(quote, row) in column"
          :key="quote.url"
          :to="quote.url"
          target="_blank"
          variant="subtle"
          :class="card(quote, columnIndex, row).class"
          :ui="{
            container: 'justify-between gap-5',
            description: card(quote, columnIndex, row).description,
          }"
          :description="`“${quote.quote}”`"
          :lang="quote.language ?? 'en'"
        >
          <template #footer>
            <div class="flex items-center gap-3">
              <!-- No picture of their own: their initials, from the name. -->
              <UAvatar
                :src="avatar(quote)"
                :alt="quote.author.replace(/^@/, '')"
                size="md"
                loading="lazy"
              />
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-highlighted">
                  {{ quote.author }}
                </p>
                <p class="flex items-center gap-1.5 text-xs text-muted">
                  <UIcon
                    :name="platforms[quote.platform]?.icon ?? 'i-mdi-web'"
                    class="size-3.5"
                  />
                  {{ platforms[quote.platform]?.name }}
                  <template v-if="when(quote.date)">
                    · {{ when(quote.date) }}
                  </template>
                </p>
              </div>
            </div>
          </template>
        </UPageCard>
      </div>
    </UCarousel>

    <!-- What people made about Spook, drifting the other way. -->
    <HomeMedia />
  </UPageSection>
</template>
