<script setup lang="ts">
import type { IntegrationChunk } from "~/utils/integration";

/**
 * The body of an integration page.
 *
 * Everything is the page's own Markdown, shown as written, except the
 * repairs: an integration can have fifteen of them, and nobody reads fifteen
 * sections to find the one their Home Assistant is showing. So each is a row
 * that says what is wrong, and opens for how to fix it.
 */
const props = defineProps<{ chunks: IntegrationChunk[] }>();

const route = useRoute();
const { t } = useI18n();
const { localTo } = useSiteLanguage();

const body = (nodes: unknown[]) => ({
  body: { type: "minimark", value: nodes },
});

const ids = computed(
  () =>
    new Set(
      props.chunks.flatMap((chunk) =>
        chunk.kind === "repairs"
          ? chunk.repairs.map((repair) => repair.id)
          : [],
      ),
    ),
);

const opened = ref(new Set<string>());

// A repair in Home Assistant links straight to its row here. Whoever follows
// that link wants the fix, so the row is open when they arrive.
function openLinked() {
  const id = decodeURIComponent(route.hash.slice(1));
  if (ids.value.has(id)) {
    opened.value.add(id);
  }
}

onMounted(openLinked);
watch(() => route.hash, openLinked);

function onToggle(id: string, event: Event) {
  if ((event.target as HTMLDetailsElement).open) {
    opened.value.add(id);
  } else {
    opened.value.delete(id);
  }
}
</script>

<template>
  <div>
    <template v-for="(chunk, index) in chunks" :key="index">
      <!-- A long page is not made interactive all at once: each section
           wakes up when it scrolls into view. It is all there to read from
           the start, since the HTML comes from the server. -->
      <LazyContentRenderer
        v-if="chunk.kind === 'content'"
        hydrate-on-visible
        :value="body(chunk.nodes)"
      />

      <div
        v-else
        class="not-prose my-6 divide-y divide-default overflow-hidden rounded-xl border border-default"
      >
        <details
          v-for="repair in chunk.repairs"
          :key="repair.id"
          :open="opened.has(repair.id)"
          class="integration-repair group/repair transition-colors"
          @toggle="onToggle(repair.id, $event)"
        >
          <summary
            class="flex cursor-pointer list-none items-start gap-3 px-4 py-4 transition-colors hover:bg-elevated/50 sm:px-5 [&::-webkit-details-marker]:hidden"
          >
            <UIcon
              name="i-mdi-wrench-outline"
              class="mt-1 size-5 shrink-0 text-primary"
            />

            <div class="min-w-0 flex-1">
              <!-- The anchor is on the heading itself: "On this page" follows
                   headings, and lights up the wrong ones without it. -->
              <h3
                :id="repair.id"
                class="scroll-mt-[calc(var(--ui-header-height)+5.5rem)] lg:scroll-mt-[calc(var(--ui-header-height)+2.5rem)] font-display text-lg/7 font-bold text-highlighted"
              >
                {{ repair.title }}
              </h3>
              <ContentRenderer
                :value="body(repair.summary)"
                class="text-[15px]/6 text-toned *:my-0"
              />
            </div>

            <UIcon
              name="i-mdi-chevron-down"
              class="mt-1.5 size-5 shrink-0 text-dimmed transition-transform group-open/repair:rotate-180"
            />
          </summary>

          <!-- Wakes up when its row is opened, not before. -->
          <LazyContentRenderer
            hydrate-on-visible
            :value="body(repair.details)"
            class="px-4 pb-5 text-[15px]/6 *:first:mt-0 *:last:mb-0 sm:px-5 sm:ps-13"
          />
        </details>
      </div>
    </template>

    <!-- What every integration page used to end with, said once. -->
    <div
      class="not-prose mt-12 flex flex-col gap-4 rounded-xl border border-default bg-elevated/40 p-5 sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <p class="font-display font-bold text-highlighted">
          {{ t("integration.missingTitle") }}
        </p>
        <p class="text-sm text-muted">
          {{ t("integration.missingText") }}
        </p>
      </div>
      <div class="flex shrink-0 flex-wrap gap-2">
        <UButton
          to="https://github.com/frenck/spook/discussions"
          target="_blank"
          icon="i-mdi-lightbulb-on-outline"
          :label="t('integration.shareIdea')"
        />
        <UButton
          :to="localTo('/support')"
          color="neutral"
          variant="outline"
          icon="i-mdi-lifebuoy"
          :label="t('integration.getHelp')"
        />
      </div>
    </div>
  </div>
</template>
