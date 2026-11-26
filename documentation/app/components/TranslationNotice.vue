<script setup lang="ts">
/**
 * Says what a translated page is: made by a machine, from the English one.
 *
 * It is there to be honest, and to send what is wrong with a translation to
 * the place that can fix it. A translated page is regenerated from English,
 * so it has no "Edit this page": a report improves the instructions the
 * translator works from, and with that every page.
 */
const { t } = useI18n();
const { language, pagePath } = useSiteLanguage();
const route = useRoute();

const report = computed(() => translationReportUrl(language.value, route.path));

function pickEnglish() {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, DEFAULT_LANGUAGE);
  } catch {
    // The link still goes to the English page.
  }
}
</script>

<template>
  <UAlert
    color="neutral"
    variant="subtle"
    icon="i-mdi-translate"
    :title="t('language.noticeTitle')"
    :description="t('language.noticeText')"
    class="mb-8"
    :ui="{ description: 'text-sm' }"
    :actions="[
      {
        label: t('language.report'),
        to: report,
        target: '_blank',
        color: 'neutral',
        variant: 'outline',
        icon: 'i-mdi-message-alert-outline',
      },
      {
        label: t('language.original'),
        to: pagePath,
        color: 'neutral',
        variant: 'link',
        onClick: pickEnglish,
      },
    ]"
  />
</template>
