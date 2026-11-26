<script setup lang="ts">
/**
 * Pick the language of the site.
 *
 * A pick is remembered, and wins from the language of the browser from then
 * on. Where the page being read does not exist in the language picked, it
 * stays as it is: there is nothing to move to, and the next page that does
 * exist in it shows up in it.
 */
const { t } = useI18n();
const { language, pagePath } = useSiteLanguage();
const route = useRoute();

const current = computed(
  () => LANGUAGES.find(({ code }) => code === language.value) ?? LANGUAGES[0]!,
);

// The round flags the media page also uses to say what language a video is
// in. They are flags of languages, not of countries.
const flag = flagOf;

async function pick(code: string) {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, code);
  } catch {
    // Without storage the pick lasts as long as the visit, which is fine.
  }

  // Stay on the same page, and on the same spot on it.
  if (isTranslated(pagePath.value, code)) {
    await navigateTo(inLanguage(pagePath.value, code) + route.hash);
  }
}

const items = computed(() =>
  // Each by its own name, in alphabetical order, so nobody has to know the
  // order we happened to add them in. Chinese sorts last, after the Latin
  // script names, which is where people look for it.
  [...LANGUAGES]
    .sort((a, b) => a.name.localeCompare(b.name, "en"))
    .map(({ code, name }) => {
      const exists = isTranslated(pagePath.value, code);

      return {
        label: name,
        icon: flag(code),
        type: "checkbox" as const,
        checked: code === language.value,
        // Says so up front, instead of a pick that seems to do nothing.
        description: exists ? undefined : t("language.notTranslated"),
        onSelect: () => pick(code),
      };
    }),
);
</script>

<template>
  <UDropdownMenu :items="items" :content="{ align: 'end' }">
    <UButton
      color="neutral"
      variant="ghost"
      :icon="flag(current.code)"
      :aria-label="t('language.label')"
      :ui="{ leadingIcon: 'size-5' }"
    >
      <!-- Only the language, not the region or script: "PT", not "PT-BR".
           The flag already tells which one, and the menu says it in full. -->
      <span class="hidden font-mono text-xs uppercase lg:inline">
        {{ current.code.split("-")[0] }}
      </span>
    </UButton>
  </UDropdownMenu>
</template>
