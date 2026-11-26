<script setup lang="ts">
/**
 * The glossary, as an A to Z you can filter.
 *
 * Every term stays a `##` heading with its `{#term-...}` anchor in the
 * Markdown; `:term[...]` links all over the documentation land on those, and
 * the entries here carry the very same ids.
 */
const props = defineProps<{
  page: { body?: { type?: string; value?: unknown[] } };
}>();

const { t } = useI18n();
const { intlLocale } = useSiteLanguage();

const parsed = computed(() => referenceSections(props.page.body as never));

const intro = computed(() => ({
  body: { type: "minimark", value: parsed.value.intro },
}));

// Sorted here rather than trusted to the order of the page, so a term added
// at the bottom still ends up under its own letter.
const terms = computed(() =>
  parsed.value.sections
    .map((section) => ({
      id: section.id,
      title: section.heading,
      body: { type: "minimark", value: section.nodes },
      text: referenceText(section),
    }))
    .sort((a, b) => a.title.localeCompare(b.title, intlLocale.value)),
);

const letters = computed(() => {
  const found = new Map<string, typeof terms.value>();
  for (const term of terms.value) {
    const letter = term.title[0]!.toUpperCase();
    found.set(letter, [...(found.get(letter) ?? []), term]);
  }

  return [...found].map(([letter, entries]) => ({
    letter,
    id: `letter-${letter.toLowerCase()}`,
    entries,
  }));
});

const { search, words } = useReferenceSearch();

const shown = computed(() => {
  return letters.value
    .map((group) => ({
      ...group,
      entries: group.entries.filter((term) =>
        words.value.every((word) => term.text.includes(word)),
      ),
    }))
    .filter((group) => group.entries.length);
});

const shownLetters = computed(
  () => new Set(shown.value.map((group) => group.letter)),
);

const shownCount = computed(() =>
  shown.value.reduce((total, group) => total + group.entries.length, 0),
);
</script>

<template>
  <div>
    <ContentRenderer :value="intro" />

    <div
      ref="index"
      class="reference-index not-prose mt-10 [--reference-toolbar:8.5rem] sm:[--reference-toolbar:6.5rem]"
    >
      <div
        ref="toolbar"
        class="reference-toolbar sticky z-10 -mx-4 space-y-3 border-b border-default bg-default/85 px-4 py-2 backdrop-blur-md lg:py-3 sm:-mx-6 sm:px-6 lg:mx-0 lg:px-0"
      >
        <div class="flex items-center gap-3">
          <UInput
            v-model="search"
            icon="i-mdi-magnify"
            size="lg"
            :placeholder="t('reference.lookUp')"
            :aria-label="t('reference.lookUp')"
            class="flex-1"
            :ui="{ trailing: 'pe-1' }"
          >
            <template v-if="search" #trailing>
              <UButton
                color="neutral"
                variant="link"
                size="sm"
                icon="i-mdi-close"
                :aria-label="t('reference.clear')"
                @click="search = ''"
              />
            </template>
          </UInput>
          <p
            class="shrink-0 font-mono text-xs uppercase tracking-[0.1em] text-muted"
            aria-live="polite"
          >
            <template v-if="search">
              {{
                t("reference.shown", { shown: shownCount, total: terms.length })
              }}
            </template>
            <template v-else>
              {{ t("reference.words", { count: terms.length }, terms.length) }}
            </template>
          </p>
        </div>

        <nav :aria-label="t('reference.letters')" class="flex flex-wrap gap-1">
          <a
            v-for="group in letters"
            :key="group.id"
            :href="shownLetters.has(group.letter) ? `#${group.id}` : undefined"
            :aria-disabled="!shownLetters.has(group.letter) || undefined"
            class="grid size-7 place-items-center rounded-md font-mono text-sm font-medium transition-colors"
            :class="
              shownLetters.has(group.letter)
                ? 'text-toned hover:bg-primary/10 hover:text-primary'
                : 'text-dimmed/50'
            "
          >
            {{ group.letter }}
          </a>
        </nav>
      </div>

      <section
        v-for="group in shown"
        :id="group.id"
        :key="group.id"
        class="reference-anchor mt-8 grid gap-3 sm:grid-cols-[3rem_1fr] sm:gap-6"
      >
        <!-- Stays in view next to its words, so you know where you are. -->
        <h2
          class="font-display text-4xl leading-none font-bold text-primary sm:sticky sm:top-[calc(var(--ui-header-height)+var(--reference-toc)+var(--reference-toolbar)+1rem)] sm:self-start sm:pt-4"
        >
          {{ group.letter }}
        </h2>

        <div
          class="min-w-0 divide-y divide-default overflow-hidden rounded-xl border border-default"
        >
          <article
            v-for="term in group.entries"
            :id="term.id"
            :key="term.id"
            class="reference-anchor reference-entry group/entry px-4 py-4 transition-colors sm:px-5"
          >
            <h3 class="font-display text-lg/7 font-bold text-highlighted">
              <a
                :href="`#${term.id}`"
                class="inline-flex items-center gap-1.5 hover:text-primary"
              >
                {{ term.title }}
                <UIcon
                  name="i-mdi-pound"
                  class="size-4 text-dimmed opacity-0 transition-opacity group-hover/entry:opacity-100"
                />
              </a>
            </h3>

            <ContentRenderer
              :value="term.body"
              class="text-[15px]/6 text-toned *:my-3 *:leading-6 *:first:mt-1.5 *:last:mb-0"
            />
          </article>
        </div>
      </section>

      <p v-if="!shown.length" class="py-12 text-center text-muted">
        {{ t("reference.noWord") }}
      </p>
    </div>
  </div>
</template>
