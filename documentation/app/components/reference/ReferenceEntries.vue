<script setup lang="ts">
import { useClipboard } from "@vueuse/core";

/**
 * The actions, triggers or conditions page, as an index you can filter.
 *
 * Read from the page's own Markdown (see utils/reference.ts), so the entries
 * are written down in one place only.
 */
const props = defineProps<{
  page: { body?: { type?: string; value?: unknown[] } };
  // What one entry is called, like "action".
  noun: "action" | "trigger" | "condition";
}>();

const { t } = useI18n();
const { localTo } = useSiteLanguage();

// Icons for the groups on the actions page, the ones Home Assistant itself
// uses for them where it has one. A group that is not here gets the ghost.
const icons: Record<string, string> = {
  Areas: "i-mdi-sofa-outline",
  Automation: "i-mdi-robot-outline",
  Blueprint: "i-mdi-paper-roll-outline",
  Calendar: "i-mdi-calendar",
  Categories: "i-mdi-folder-outline",
  Climate: "i-mdi-thermostat",
  Counter: "i-mdi-counter",
  Cover: "i-mdi-window-shutter",
  Device: "i-mdi-devices",
  Entity: "i-mdi-shape-outline",
  Floors: "i-mdi-home-floor-1",
  Group: "i-mdi-google-circles-communities",
  "Home Assistant": "i-spook-home-assistant",
  Humidifier: "i-mdi-air-humidifier",
  "Input boolean": "i-mdi-toggle-switch-outline",
  "Input button": "i-mdi-gesture-tap-button",
  "Input datetime": "i-mdi-calendar-clock",
  "Input number": "i-mdi-ray-vertex",
  "Input select": "i-mdi-format-list-bulleted",
  "Input text": "i-mdi-form-textbox",
  Integration: "i-mdi-puzzle-outline",
  Labels: "i-mdi-label-outline",
  Light: "i-mdi-lightbulb-outline",
  "Media player": "i-mdi-cast",
  Number: "i-mdi-ray-vertex",
  Person: "i-mdi-account-outline",
  Recorder: "i-mdi-database-outline",
  Repairs: "i-mdi-tools",
  Schedule: "i-mdi-calendar-week",
  Select: "i-mdi-format-list-bulleted",
  Sensor: "i-mdi-eye-outline",
  Timer: "i-mdi-timer-outline",
  "To-do list": "i-mdi-clipboard-list-outline",
  User: "i-mdi-account-lock-outline",
  Valve: "i-mdi-valve",
  "Water heater": "i-mdi-water-boiler",
  Zone: "i-mdi-map-marker-radius",
};

const parsed = computed(() => referenceSections(props.page.body as never));

// Everything above the first entry, rendered as written.
const intro = computed(() => ({
  body: { type: "minimark", value: parsed.value.intro },
}));

const entries = computed(() =>
  referenceEntries(parsed.value.sections).map((entry) => ({
    ...entry,
    body: { type: "minimark", value: entry.nodes },
  })),
);

// A page without groups (triggers, conditions) is one list without a title.
const groups = computed(() => {
  const grouped = referenceGroups(entries.value);
  return grouped.length
    ? grouped
    : [{ id: "", title: "", entries: entries.value }];
});

const { search, words } = useReferenceSearch();

const shown = computed(() =>
  groups.value
    .map((group) => ({
      ...group,
      entries: group.entries.filter((entry) =>
        words.value.every((word) => entry.text.includes(word)),
      ),
    }))
    .filter((group) => group.entries.length),
);

const shownCount = computed(() =>
  shown.value.reduce((total, group) => total + group.entries.length, 0),
);

const { copy, copied, text: copiedText } = useClipboard({ copiedDuring: 1500 });
</script>

<template>
  <div>
    <ContentRenderer :value="intro" />

    <div ref="index" class="reference-index not-prose mt-10">
      <div
        ref="toolbar"
        class="reference-toolbar sticky z-10 -mx-4 flex items-center gap-3 border-b border-default bg-default/85 px-4 py-2 backdrop-blur-md lg:py-3 sm:-mx-6 sm:px-6 lg:mx-0 lg:px-0"
      >
        <UInput
          v-model="search"
          icon="i-mdi-magnify"
          size="lg"
          :placeholder="t(`reference.find.${noun}`)"
          :aria-label="t(`reference.find.${noun}`)"
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
              t("reference.shown", {
                shown: shownCount,
                total: entries.length,
              })
            }}
          </template>
          <template v-else>
            {{
              t(
                `reference.count.${noun}`,
                { count: entries.length },
                entries.length,
              )
            }}
          </template>
        </p>
      </div>

      <section
        v-for="group in shown"
        :id="group.id || undefined"
        :key="group.id"
        :aria-label="group.title || undefined"
        class="reference-anchor mt-8"
      >
        <header v-if="group.title" class="mb-3 flex items-center gap-3">
          <span
            class="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/20 ring-inset"
          >
            <UIcon
              :name="icons[group.title] ?? 'i-mdi-ghost-outline'"
              class="size-5"
            />
          </span>
          <h2 class="font-display text-xl font-bold text-highlighted">
            {{ group.title }}
          </h2>
          <span class="font-mono text-xs text-dimmed">
            {{ group.entries.length }}
          </span>
        </header>

        <ul
          class="divide-y divide-default overflow-hidden rounded-xl border border-default"
        >
          <li
            v-for="entry in group.entries"
            :id="entry.id"
            :key="entry.id"
            class="reference-anchor reference-entry group/entry px-4 py-3.5 transition-colors sm:px-5"
          >
            <div
              class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6"
            >
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <component
                    :is="group.title ? 'h3' : 'h2'"
                    class="font-display text-base/6 font-semibold text-highlighted"
                  >
                    <a
                      :href="`#${entry.id}`"
                      class="inline-flex items-center gap-1 hover:text-primary"
                    >
                      {{ entry.title }}
                      <UIcon
                        name="i-mdi-pound"
                        class="size-4 text-dimmed opacity-0 transition-opacity group-hover/entry:opacity-100"
                      />
                    </a>
                  </component>

                  <button
                    v-if="entry.name"
                    type="button"
                    class="inline-flex max-w-full items-center gap-1.5 rounded-md bg-elevated/60 px-1.5 py-0.5 font-mono text-xs text-toned ring-1 ring-default ring-inset transition-colors hover:text-primary hover:ring-primary/40"
                    :title="t('reference.copy', { name: entry.name })"
                    :aria-label="t('reference.copy', { name: entry.name })"
                    @click="copy(entry.name)"
                  >
                    <span class="truncate">{{ entry.name }}</span>
                    <UIcon
                      :name="
                        copied && copiedText === entry.name
                          ? 'i-mdi-check'
                          : 'i-mdi-content-copy'
                      "
                      class="size-3.5 shrink-0 opacity-60"
                    />
                  </button>
                </div>

                <ContentRenderer
                  :value="entry.body"
                  class="mt-1.5 text-[15px]/6 text-muted *:my-0 *:leading-6"
                />
              </div>

              <div class="flex shrink-0 gap-2">
                <UButton
                  v-if="entry.tryIt"
                  :to="entry.tryIt"
                  target="_blank"
                  size="sm"
                  variant="soft"
                  icon="i-spook-home-assistant"
                  :label="t('reference.tryIt')"
                  :aria-label="
                    t('reference.tryItLabel', { title: entry.title })
                  "
                />
                <UButton
                  v-if="entry.docs"
                  :to="localTo(entry.docs)"
                  size="sm"
                  color="neutral"
                  variant="outline"
                  trailing-icon="i-mdi-arrow-right"
                  :label="t('reference.docs')"
                  :aria-label="t('reference.docsLabel', { title: entry.title })"
                />
              </div>
            </div>
          </li>
        </ul>
      </section>

      <p v-if="!shown.length" class="py-12 text-center text-muted">
        {{ t(`reference.none.${noun}`) }}
      </p>
    </div>
  </div>
</template>
