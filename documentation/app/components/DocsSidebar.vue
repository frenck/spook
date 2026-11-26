<script setup lang="ts">
import type { ContentNavigationItem } from "@nuxt/content";

/**
 * The sidebar: the pages of the area you are in.
 *
 * A small area, like Get started, simply lists its pages. The docs are too
 * big for that, so there the groups fold: the one you are in is open, the
 * rest is one select away, and a long group gets a filter.
 */
const { t } = useI18n();
const { currentSection, currentGroup } = useDocsNavigation();
const { pagePath, localTo } = useSiteLanguage();

// From here on, a group is long enough to want a filter above it.
const FILTER_FROM = 15;

// Below this many pages, an area shows everything and nothing folds.
const FOLD_FROM = 12;

const hub = computed(() => currentSection.value?.hub);

// The overview has its own link above the groups, so it does not show up
// again inside the group its file happens to sit in.
const groups = computed(() =>
  (currentSection.value?.groups ?? []).map((group) => ({
    ...group,
    children: (group.children ?? []).filter(
      (page) => page.canonical !== hub.value,
    ),
  })),
);

const folds = computed(
  () =>
    groups.value.reduce((total, group) => total + group.children.length, 0) >=
    FOLD_FROM,
);

// Which groups are open. Kept while you move through the docs: a group you
// opened yourself stays open.
const opened = ref(new Set<string>());

watch(
  () => currentGroup.value?.path,
  (path) => {
    if (path && pagePath.value !== hub.value) {
      opened.value.add(path);
    }
  },
  { immediate: true },
);

function toggle(group: ContentNavigationItem) {
  if (!opened.value.delete(group.path)) {
    opened.value.add(group.path);
  }
}

const filters = ref<Record<string, string>>({});

function pages(group: ContentNavigationItem): ContentNavigationItem[] {
  const words = (filters.value[group.path] ?? "")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);

  return (group.children ?? []).filter((page) =>
    words.every((word) => page.title.toLowerCase().includes(word)),
  );
}

// In a long group, the page you are on can be far down the list. Bring it
// into view, without moving the page itself.
const root = useTemplateRef<HTMLElement>("root");

async function showCurrent() {
  await nextTick();
  root.value
    ?.querySelector('[aria-current="page"]')
    ?.scrollIntoView({ block: "nearest" });
}

onMounted(showCurrent);
watch(pagePath, showCurrent);
</script>

<template>
  <nav ref="root" :aria-label="t('nav.pages')" class="space-y-1">
    <UContentNavigation
      v-if="hub"
      highlight
      variant="pill"
      :navigation="[
        {
          title: t('nav.overview'),
          path: localTo(hub),
          icon: 'i-mdi-view-grid-outline',
        },
      ]"
    />

    <template v-if="folds">
      <section v-for="group in groups" :key="group.path">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-2 rounded-md py-2 text-left font-display text-sm font-bold text-highlighted transition-colors hover:text-primary"
          :aria-expanded="opened.has(group.path)"
          @click="toggle(group)"
        >
          <span>{{ group.title }}</span>
          <span class="flex items-center gap-1.5 text-dimmed">
            <span class="font-mono text-[11px] font-medium">
              {{ group.children.length }}
            </span>
            <UIcon
              name="i-mdi-chevron-down"
              class="size-4 transition-transform"
              :class="opened.has(group.path) ? 'rotate-180' : ''"
            />
          </span>
        </button>

        <!-- Set in from the group name, along a line, so it reads as what
             is inside it. -->
        <div
          v-show="opened.has(group.path)"
          class="mb-3 ms-0.5 border-s border-default ps-3"
        >
          <UInput
            v-if="group.children.length >= FILTER_FROM"
            v-model="filters[group.path]"
            icon="i-mdi-magnify"
            size="sm"
            :placeholder="t('nav.findIn', { group: group.title.toLowerCase() })"
            :aria-label="t('nav.findIn', { group: group.title.toLowerCase() })"
            class="mb-2 w-full"
          />

          <UContentNavigation
            highlight
            variant="pill"
            :navigation="pages(group)"
          />

          <p v-if="!pages(group).length" class="py-2 text-sm text-muted">
            {{ t("nav.nothingFound") }}
          </p>
        </div>
      </section>
    </template>

    <UContentNavigation
      v-else
      highlight
      variant="pill"
      :navigation="groups.length === 1 ? groups[0]!.children : groups"
    />
  </nav>
</template>
