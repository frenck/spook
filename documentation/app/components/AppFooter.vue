<script setup lang="ts">
import type { FooterColumn } from "@nuxt/ui";

const { t } = useI18n();

const { localTo } = useSiteLanguage();

// The labels are `footer.columns.<key>`. A page of the site is linked in
// the language being read, where it exists in it.
const columns = computed<FooterColumn[]>(() =>
  [
    {
      label: "tour",
      children: [
        { label: "repairs", to: "/tour/repairs" },
        { label: "automations", to: "/tour/automations" },
        { label: "manage", to: "/tour/manage" },
        { label: "straightAnswers", to: "/straight-answers" },
      ],
    },
    {
      label: "docs",
      children: [
        { label: "installation", to: "/installation" },
        { label: "everything", to: "/docs" },
        { label: "firstRepair", to: "/fix-your-first-repair" },
        { label: "help", to: "/support" },
      ],
    },
    {
      label: "about",
      children: [
        { label: "whatIs", to: "/about" },
        { label: "whatsNew", to: "/whats-new" },
        { label: "history", to: "/background-and-history" },
        { label: "development", to: "/development" },
        { label: "security", to: "/security" },
        { label: "license", to: "/license" },
      ],
    },
    {
      label: "community",
      children: [
        {
          label: "GitHub",
          to: "https://github.com/frenck/spook",
          target: "_blank",
        },
        {
          label: "discussions",
          to: "https://github.com/frenck/spook/discussions",
          target: "_blank",
        },
        {
          label: "sponsor",
          to: "https://github.com/sponsors/frenck",
          target: "_blank",
        },
        {
          label: "newsletter",
          to: "https://frenck.dev/newsletter/",
          target: "_blank",
        },
      ],
    },
  ].map((column) => ({
    label: t(`footer.columns.${column.label}`),
    children: column.children.map((link) => ({
      ...link,
      // GitHub is a name, in every language.
      label:
        link.label === "GitHub"
          ? link.label
          : t(`footer.columns.${link.label}`),
      to: localTo(link.to),
    })),
  })),
);
</script>

<template>
  <UFooter :ui="{ top: 'border-b border-muted' }">
    <template #top>
      <UContainer>
        <UFooterColumns :columns="columns">
          <template #left>
            <div class="mb-3.5 flex items-center gap-2.5">
              <AppLogo />
            </div>
            <p class="max-w-xs text-sm leading-relaxed text-muted">
              {{ t("footer.tagline") }}
            </p>
            <p class="mt-2 text-sm text-muted">
              {{ t("footer.madeWith") }}
              <ULink to="https://frenck.dev" class="text-highlighted"
                >Frenck</ULink
              >.
            </p>
          </template>
        </UFooterColumns>
      </UContainer>
    </template>

    <template #left>
      <!-- On every page, in words a person reads, not only in llms.txt:
           Spook is free, and who it comes from. -->
      <p class="text-xs text-dimmed">© Franck Nijhof · {{ t("home.free") }}</p>
    </template>

    <template #right>
      <p class="text-xs text-dimmed">
        {{ t("footer.notAffiliated") }}
      </p>
    </template>
  </UFooter>
</template>
