import type { ContentNavigationItem } from "@nuxt/content";

interface DocsItem {
  path: string;
  title: string;
  description?: string;
  stem: string;
  navigation?: boolean | { title?: string; icon?: string };
  meta?: Record<string, unknown>;
}

interface SectionConfig {
  // Names the area in the site's own words: `nav.<key>` in `locales/`.
  key: string;
  // Its name in English, also what tells one area from another.
  label: string;
  icon: string;
  folders: string[];
  // The page a section opens on, when that is not simply its first page. The
  // sidebar shows it above the groups, as the way back to the overview.
  hub?: string;
}

export interface Section extends SectionConfig {
  to: string;
  groups: DocsLink[];
}

// An entry in the menus. `path` is where it links to, in the language being
// read. `canonical` is the page itself, whatever the language: that is what
// "which page am I on" is answered with.
export type DocsLink = ContentNavigationItem & {
  canonical?: string;
  children?: DocsLink[];
};

export const DOCS_ITEMS_KEY = "docs-items";

const itemsKey = (language: string) => `${DOCS_ITEMS_KEY}-${language}`;

function itemsOf(collection: "docs" | `docs_${string}`) {
  return queryCollection(collection as "docs")
    .order("stem", "ASC")
    .select("path", "title", "description", "stem", "navigation", "meta")
    .all() as Promise<DocsItem[]>;
}

/**
 * Load every page once, for the navigation. Called from `app.vue`, so the
 * rest of the site reads it from the payload instead of querying again.
 *
 * The English pages are the menu: every page is in there. In another
 * language, the pages that are translated bring their own title along.
 */
export function fetchDocsItems() {
  const { language } = useSiteLanguage();

  return useAsyncData(
    () => itemsKey(language.value),
    async () => {
      const english = await itemsOf("docs");
      if (language.value === DEFAULT_LANGUAGE) {
        return english;
      }

      const translated = new Map(
        (await itemsOf(`docs_${collectionCode(language.value)}`)).map(
          (item) => [item.stem, item],
        ),
      );

      return english.map((item) => {
        const own = translated.get(item.stem);
        return own
          ? {
              ...item,
              title: own.title,
              description: own.description,
              navigation: own.navigation,
            }
          : item;
      });
    },
    { watch: [language] },
  );
}

function folderOf(stem: string): string | undefined {
  const [folder, ...rest] = stem.split("/");
  return rest.length ? folder!.replace(/^\d+\./, "") : undefined;
}

/**
 * The site's navigation, built from the content folders.
 *
 * Pages keep flat URLs (`/automation`), because Spook releases link to them,
 * so the structure cannot come from the URL. It comes from the folder a page
 * sits in, and `app.config.ts` decides which folders make up which section.
 */
export function useDocsNavigation() {
  const appConfig = useAppConfig();
  const { t, te } = useI18n();
  const { language, pagePath, localTo } = useSiteLanguage();
  const items = computed(
    () => useNuxtData<DocsItem[]>(itemsKey(language.value)).data.value,
  );

  const groups = computed(() => {
    const found = new Map<string, DocsLink>();

    for (const item of items.value ?? []) {
      const folder = folderOf(item.stem);
      if (!folder) {
        continue;
      }

      // A group is named in the site's own words, so it is translated with
      // them: `nav.groups.<folder>`. The title in the folder's
      // `.navigation.yml` is for a folder that has no name there yet.
      const key = `nav.groups.${folder}`;
      if (!found.has(folder)) {
        found.set(folder, {
          title: te(key) ? t(key) : folder,
          path: `/${folder}`,
          children: [],
        });
      }

      const group = found.get(folder)!;
      if (item.stem.endsWith("/.navigation")) {
        if (!te(key)) {
          group.title = item.title;
        }
        continue;
      }

      if (item.navigation === false) {
        continue;
      }

      const navigation =
        typeof item.navigation === "object" ? item.navigation : {};
      group.children!.push({
        title: navigation.title ?? item.title,
        path: localTo(item.path),
        canonical: item.path,
        description: item.description,
        icon: navigation.icon,
      });
    }

    return found;
  });

  const sections = computed<Section[]>(() =>
    ((appConfig.sections ?? []) as SectionConfig[]).map((section) => {
      const sectionGroups = section.folders
        .map((folder) => groups.value.get(folder))
        .filter((group): group is DocsLink => !!group);

      return {
        ...section,
        groups: sectionGroups,
        to: section.hub
          ? localTo(section.hub)
          : (sectionGroups[0]?.children?.[0]?.path ?? "/"),
      };
    }),
  );

  // Everything, grouped by section, for search and the mobile menu.
  const navigation = computed<DocsLink[]>(() =>
    sections.value.map((section) => ({
      title: section.label,
      path: section.to,
      icon: section.icon,
      children: section.groups,
    })),
  );

  const currentSection = computed(() =>
    sections.value.find((section) =>
      section.groups.some((group) =>
        group.children?.some((page) => page.canonical === pagePath.value),
      ),
    ),
  );

  const currentGroup = computed(() =>
    currentSection.value?.groups.find((group) =>
      group.children?.some((page) => page.canonical === pagePath.value),
    ),
  );

  // Previous and next stay inside the section, in sidebar order.
  const surround = computed(() => {
    const pages = (currentSection.value?.groups ?? []).flatMap(
      (group) => group.children ?? [],
    );
    const index = pages.findIndex((page) => page.canonical === pagePath.value);

    // The overview of an area leads everywhere; it has no previous or next.
    if (index === -1 || pagePath.value === currentSection.value?.hub) {
      return [];
    }

    return [pages[index - 1] ?? null, pages[index + 1] ?? null];
  });

  return {
    // Every page, with its title in the language being read when it has one.
    items,
    sections,
    navigation,
    currentSection,
    currentGroup,
    surround,
  };
}
