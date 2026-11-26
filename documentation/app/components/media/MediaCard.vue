<script setup lang="ts">
const props = defineProps<{
  to: string;
  title: string;
  byline: string;
  icon: string;
  language: string;
  date: string;
  description?: string;
  image?: string;
  // Fill the frame edge to edge. Right for YouTube thumbnails, which carry
  // black bars; everything else is shown whole on a blurred copy of itself,
  // so a square podcast cover is not cut in half.
  crop?: boolean;
}>();

const { intlLocale } = useSiteLanguage();

// The language it is in, named in the language of the page.
const languages = computed(
  () => new Intl.DisplayNames([intlLocale.value], { type: "language" }),
);

const when = computed(() => {
  if (props.date.length === 4) {
    return props.date;
  }

  return new Date(props.date).toLocaleDateString(intlLocale.value, {
    year: "numeric",
    month: "long",
  });
});

const site = computed(() => new URL(props.to).hostname.replace(/^www\./, ""));
</script>

<template>
  <UPageCard
    :to="to"
    target="_blank"
    :title="title"
    variant="outline"
    :ui="{
      container: 'p-0 sm:p-0 gap-0',
      header: 'w-full',
      // Two lines, always: a one-line title would make its card shorter
      // than the ones next to it.
      title: 'line-clamp-2 min-h-[2lh]',
    }"
  >
    <template #header>
      <!-- The title right below says it all, so the images are decorative. -->
      <div class="relative aspect-video overflow-hidden rounded-t-lg bg-muted">
        <img
          v-if="image && crop"
          :src="image"
          alt=""
          class="size-full object-cover"
          loading="lazy"
        />
        <template v-else-if="image">
          <img
            :src="image"
            alt=""
            class="absolute inset-0 size-full scale-110 object-cover opacity-60 blur-xl"
            loading="lazy"
          />
          <img
            :src="image"
            alt=""
            class="relative size-full object-contain"
            loading="lazy"
          />
        </template>
        <div
          v-else
          class="flex size-full flex-col items-center justify-center gap-3 bg-(image:--gradient-haunt)"
        >
          <img src="/images/spook-ghost.png" alt="" class="size-14" />
          <span class="font-mono text-xs text-ink-300">{{ site }}</span>
        </div>
      </div>
    </template>

    <template #title>
      <span class="block px-4 pt-3">{{ title }}</span>
    </template>

    <template v-if="description" #description>
      <span class="block px-4 pt-1">{{ description }}</span>
    </template>

    <template #footer>
      <!-- Byline and badges each get their own row, so every card in the
           grid lays out the same, however long the name. -->
      <div class="flex flex-col gap-2.5 px-4 pb-4 text-sm text-muted">
        <span class="flex min-w-0 items-center gap-2">
          <UIcon :name="icon" class="size-4 shrink-0" />
          <span class="truncate">{{ byline }}</span>
        </span>
        <span class="flex flex-wrap gap-1.5">
          <!-- Language flags, not country flags: English is not just Britain. -->
          <UBadge
            color="neutral"
            variant="subtle"
            size="sm"
            :icon="`i-circle-flags-lang-${language}`"
            :label="languages.of(language)"
          />
          <UBadge
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-mdi-calendar-blank-outline"
            :label="when"
          />
        </span>
      </div>
    </template>
  </UPageCard>
</template>
