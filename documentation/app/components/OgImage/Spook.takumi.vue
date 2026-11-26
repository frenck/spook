<script setup lang="ts">
// The share card: the picture a link to spook.boo shows in Slack, Discord,
// the forum, or a social network. One frame, filled in per kind of page:
//
// - "home" and "tour": a page that sells, with a real screenshot next to it.
// - "integration": an integration page, with its brand icon and how much
//   Spook adds to it.
// - "docs": every other page. Its title is the point, so no screenshot: at
//   the size of a link preview, it would only be noise.
//
// Cards are always on ink: dark is where Spook looks best.
//
// Fonts are set with classes, never in a style binding: the build reads the
// classes to know which fonts to hand the renderer, and cannot see into
// bindings.
defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    kind?: "home" | "tour" | "integration" | "docs";
    eyebrow?: string;
    title: string;
    description?: string;
    // The path of the page, shown at the bottom.
    path?: string;
    // A screenshot from the screenshot tool, by name. Always the dark one,
    // in the language of the page: its text comes from the page already.
    screenshot?: string;
    language?: string;
    // The domain of an integration, for its icon from the brands repository.
    brand?: string;
    stats?: { value: string | number; label: string }[];
  }>(),
  { kind: "docs", language: "en" },
);

const INK_950 = "#17191b";
const INK_900 = "#1d2025";
const INK_800 = "#2a2e34";
const INK_400 = "#8a929d";
const INK_300 = "#b4bbc3";
const CYAN = "#24fefd";

const visual = computed(() => Boolean(props.screenshot || props.brand));

// Long titles get a smaller size, so most fit in two or three lines.
const titleSize = computed(() => {
  const length = props.title.length;
  if (props.kind === "home") return 70;
  if (length <= 18) return visual.value ? 76 : 88;
  if (length <= 36) return visual.value ? 62 : 72;
  return visual.value ? 52 : 60;
});

const address = computed(() =>
  props.path && props.path !== "/" ? `spook.boo${props.path}` : "spook.boo",
);
</script>

<template>
  <div
    class="font-sans font-normal"
    :style="{
      display: 'flex',
      position: 'relative',
      width: '100%',
      height: '100%',
      overflow: 'hidden',
      backgroundColor: INK_950,
      backgroundImage: `radial-gradient(70% 90% at 30% 0%, rgba(36, 254, 253, 0.16) 0%, rgba(36, 254, 253, 0) 70%), linear-gradient(160deg, ${INK_900} 0%, ${INK_950} 60%, #0b1418 100%)`,
      color: '#fff',
    }"
  >
    <!-- The text, with the wordmark on top and the address at the bottom. -->
    <div
      :style="{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        width: visual ? '640px' : '100%',
        height: '100%',
        padding: '56px 0 52px 72px',
        paddingRight: visual ? '0' : '72px',
      }"
    >
      <img
        src="/images/logo_transparent.png"
        :style="{ width: '224px', height: '56px' }"
      />

      <div :style="{ display: 'flex', flexDirection: 'column' }">
        <div
          v-if="eyebrow"
          class="font-mono font-medium"
          :style="{
            fontSize: '22px',
            letterSpacing: '3px',
            textTransform: 'uppercase',
            color: CYAN,
            marginBottom: '20px',
          }"
        >
          {{ eyebrow }}
        </div>

        <div
          class="font-display font-bold"
          :style="{
            fontSize: `${titleSize}px`,
            lineHeight: 1.02,
            letterSpacing: '-2px',
            lineClamp: 3,
            textOverflow: 'ellipsis',
          }"
        >
          {{ title }}
        </div>

        <div
          v-if="description && !stats?.length"
          :style="{
            marginTop: '22px',
            fontSize: '28px',
            lineHeight: 1.38,
            color: INK_300,
            lineClamp: visual ? 3 : 2,
            textOverflow: 'ellipsis',
          }"
        >
          {{ description }}
        </div>

        <!-- Numbers instead of a description: what Spook brings, at a glance. -->
        <div
          v-if="stats?.length"
          :style="{ display: 'flex', gap: '44px', marginTop: '34px' }"
        >
          <div
            v-for="stat in stats"
            :key="stat.label"
            :style="{
              display: 'flex',
              flexDirection: 'column',
              paddingLeft: '20px',
              borderLeft: `2px solid ${INK_800}`,
            }"
          >
            <div
              class="font-display font-bold"
              :style="{
                fontSize: '48px',
                lineHeight: 1,
                letterSpacing: '-1px',
              }"
            >
              {{ stat.value }}
            </div>
            <div
              class="font-mono font-normal"
              :style="{
                fontSize: '19px',
                color: INK_400,
                marginTop: '10px',
              }"
            >
              {{ stat.label }}
            </div>
          </div>
        </div>
      </div>

      <div
        class="font-mono font-medium"
        :style="{
          fontSize: '22px',
          color: CYAN,
          lineClamp: 1,
        }"
      >
        {{ address }}
      </div>
    </div>

    <!-- A real screenshot, on the same kind of backdrop as on the site. -->
    <div
      v-if="screenshot"
      :style="{
        display: 'flex',
        position: 'absolute',
        left: '700px',
        top: '72px',
        width: '560px',
      }"
    >
      <img
        :src="`/images/screenshots/${language}/dark/${screenshot}.webp`"
        :style="{
          width: '560px',
          borderRadius: '18px',
          boxShadow: '0 0 60px -10px rgba(36, 254, 253, 0.35)',
        }"
      />
      <img
        src="/images/spook-ghost.png"
        :style="{
          position: 'absolute',
          left: '-44px',
          bottom: '-66px',
          width: '84px',
          height: '84px',
          transform: 'rotate(-12deg)',
        }"
      />
    </div>

    <!-- The integration's own icon, glowing, with the ghost on its corner. -->
    <div
      v-if="brand && !screenshot"
      :style="{
        display: 'flex',
        position: 'absolute',
        right: '110px',
        top: '170px',
        width: '300px',
        height: '300px',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: '48px',
        backgroundColor: INK_900,
        border: `2px solid ${INK_800}`,
        boxShadow: '0 0 80px -12px rgba(36, 254, 253, 0.4)',
      }"
    >
      <img
        :src="`https://brands.home-assistant.io/${brand}/icon@2x.png`"
        :style="{ width: '190px', height: '190px' }"
      />
      <img
        src="/images/spook-ghost.png"
        :style="{
          position: 'absolute',
          right: '-30px',
          bottom: '-30px',
          width: '96px',
          height: '96px',
          transform: 'rotate(-12deg)',
        }"
      />
    </div>
  </div>
</template>
