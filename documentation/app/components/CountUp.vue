<script setup lang="ts">
// A number that counts up the first time it comes into view. The page is
// built with the real number in it, so without script, for a search engine,
// or for anyone who asked for less motion, it is simply there.
const props = defineProps<{ value: number }>();

const element = ref<HTMLElement>();
const shown = ref(props.value);

// Written the way the page's language writes numbers: 1,234 or 1.234.
const { language } = useSiteLanguage();
const format = (value: number) =>
  Math.round(value).toLocaleString(language.value);

// Gone before it was ever seen, like a reader leaving the home page before
// scrolling down: the observer goes with it, rather than watching a number
// that is no longer on the page.
let observer: IntersectionObserver | undefined;
onBeforeUnmount(() => observer?.disconnect());

onMounted(() => {
  if (
    !element.value ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    return;
  }

  shown.value = 0;
  observer = new IntersectionObserver(([entry]) => {
    if (!entry?.isIntersecting) {
      return;
    }
    observer?.disconnect();

    const start = performance.now();
    const duration = 1400;
    const step = (now: number) => {
      // Fast at first, slowing down as it gets there.
      const progress = Math.min(1, (now - start) / duration);
      shown.value = props.value * (1 - Math.pow(1 - progress, 4));
      if (progress < 1) {
        requestAnimationFrame(step);
      }
    };
    requestAnimationFrame(step);
  });
  observer.observe(element.value);
});
</script>

<template>
  <span ref="element" class="tabular-nums">{{ format(shown) }}</span>
</template>
