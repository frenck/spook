<script setup lang="ts">
// A screenshot made by the screenshot tool (screenshots/ in this folder),
// shown in the light or dark theme of Home Assistant to match the site.
//
// Home Assistant itself stays exactly as people know it. The branding is
// around it: Spook's backdrop, and the ghost peeking out from behind.
// No fixed size: most are cropped to what they show, so each has its own.
const props = withDefaults(
  defineProps<{
    name: string;
    alt: string;
    // Only to show a screenshot in one language on purpose. Left out, it
    // follows the language of the page.
    language?: string;
    // Where it arrives from as you scroll to it: the side it sits on next to
    // its text, or from below.
    from?: "below" | "left" | "right";
    // Give the frame one shape whatever the picture's own, for screenshots
    // shown side by side: cards in a row should line up.
    even?: boolean;
  }>(),
  { language: undefined, from: "below", even: false },
);

const arrival = computed(
  () =>
    ({ below: "reveal", left: "reveal-left", right: "reveal-right" })[
      props.from
    ],
);

// Home Assistant in the reader's language, when this shot was made in it.
const { screenshotLanguage } = useSiteLanguage();
const base = computed(
  () =>
    `/images/screenshots/${props.language ?? screenshotLanguage(props.name)}`,
);

// A drop shadow follows the shape of the picture, so a dialog cut out along
// its rounded corners gets rounded shadows too, which a box shadow would not.
const picture = computed(() => [
  "relative w-full rounded-lg drop-shadow-xl dark:drop-shadow-[0_0_28px_rgb(36_254_253/0.16)]",
  props.even ? "h-full object-contain" : "",
]);
</script>

<template>
  <figure class="not-prose group my-6" :class="arrival">
    <div
      class="relative overflow-hidden rounded-2xl bg-(image:--screenshot-backdrop) p-5 ring ring-default sm:p-8"
      :class="even ? 'aspect-[4/3]' : ''"
    >
      <!-- Both are in the page, CSS shows one. A hidden lazy image is never
           downloaded, so a visitor only loads the one they see. -->
      <img
        :src="`${base}/light/${name}.webp`"
        :alt="alt"
        loading="lazy"
        :class="[picture, 'dark:hidden']"
      />
      <img
        :src="`${base}/dark/${name}.webp`"
        :alt="alt"
        loading="lazy"
        :class="[picture, 'hidden dark:block']"
      />

      <!-- Painted last, on top of everything: the ghost sits on the corner
           of the screenshot, whole, never cut off by it. -->
      <img
        src="/images/spook-ghost.png"
        alt=""
        aria-hidden="true"
        class="ghost-pop pointer-events-none absolute right-2 bottom-2 z-10 size-9 -rotate-12 drop-shadow-md transition-transform duration-300 group-hover:-translate-y-1 group-hover:rotate-0 sm:right-3 sm:bottom-3 sm:size-10 dark:drop-shadow-[0_0_10px_rgb(36_254_253/0.45)]"
      />
    </div>
    <figcaption
      v-if="$slots.default"
      class="mt-3 text-center text-sm text-muted italic"
    >
      <slot mdc-unwrap="p" />
    </figcaption>
  </figure>
</template>
