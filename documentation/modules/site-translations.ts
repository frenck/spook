import { addTemplate, addTypeTemplate, defineNuxtModule } from "@nuxt/kit";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { TRANSLATED_LANGUAGES } from "../shared/utils/languages";

/** Every Markdown file below a directory. */
function markdownIn(directory: string): string[] {
  if (!existsSync(directory)) {
    return [];
  }

  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) {
      return markdownIn(path);
    }

    return name.endsWith(".md") ? [path] : [];
  });
}

/** Every data file below a directory, by its path in it: `tour/repairs.yml`. */
function dataIn(directory: string, prefix = ""): string[] {
  if (!existsSync(directory)) {
    return [];
  }

  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) {
      return dataIn(path, `${prefix}${name}/`);
    }

    return name.endsWith(".yml") ? [`${prefix}${name}`] : [];
  });
}

/**
 * The pages that are not Markdown, and when they exist in a language: when
 * their text does. The home page is in the site's own words, the tour and
 * the straight answers in the data files under `content/data/`.
 */
function marketingPages(
  hasLocale: boolean,
  data: string[],
  englishTours: string[],
): string[] {
  const tours = data
    .filter((file) => file.startsWith("tour/"))
    .map((file) => file.replace(/^tour\/(.*)\.yml$/, "/tour/$1"));
  const wholeTour = englishTours.every((file) => data.includes(file));

  return [
    ...(hasLocale ? ["/"] : []),
    ...(wholeTour && tours.length ? ["/tour"] : []),
    ...tours,
    ...(data.includes("answers.yml") ? ["/straight-answers"] : []),
  ];
}

/** Where the site serves a page: the `path` in its front matter. */
function pathOf(file: string): string | undefined {
  return readFileSync(file, "utf-8").match(/^path:\s*(\S+)\s*$/m)?.[1];
}

/**
 * Tell the site what exists in which language.
 *
 * Not every page is translated, and not every screenshot is made in every
 * language. The site has to know before it renders a link or a picture:
 * a link to a page without a translation goes to the English one, and a
 * missing screenshot shows the English one.
 *
 * It is a list made while the site is built, so it costs the reader nothing.
 */
export default defineNuxtModule({
  meta: { name: "site-translations" },
  setup(_options, nuxt) {
    const root = nuxt.options.rootDir;

    const pages: Record<string, string[]> = {};
    const data: Record<string, string[]> = {};
    const screenshots: Record<string, string[]> = {};

    const englishTours = dataIn(join(root, "content", "data")).filter((file) =>
      file.startsWith("tour/"),
    );

    for (const { code } of TRANSLATED_LANGUAGES) {
      const output = join(root, "translations", "output", code);

      data[code] = dataIn(join(output, "data")).sort();
      pages[code] = [
        ...markdownIn(join(output, "content"))
          .map(pathOf)
          .filter((path): path is string => !!path),
        ...marketingPages(
          existsSync(join(output, "locale.json")),
          data[code],
          englishTours,
        ),
      ].sort();

      const shots = join(
        root,
        "public",
        "images",
        "screenshots",
        code,
        "light",
      );
      screenshots[code] = existsSync(shots)
        ? readdirSync(shots)
            .filter((name) => name.endsWith(".webp"))
            .map((name) => name.replace(/\.webp$/, ""))
            .sort()
        : [];
    }

    // Nothing on an English page links to its translation as a plain link
    // (the language menu is a menu), so the build is told about these pages.
    nuxt.options.nitro.prerender ??= {};
    nuxt.options.nitro.prerender.routes = [
      ...(nuxt.options.nitro.prerender.routes ?? []),
      ...Object.entries(pages).flatMap(([code, paths]) =>
        paths.map((path) => `/${code}${path}`),
      ),
    ];

    // The pages that are not Markdown are Vue files, at one address each.
    // Their translations are the same files, at the same address behind the
    // language. The docs do not need this: their catch-all route already
    // takes `/nl/automation`.
    const languages = TRANSLATED_LANGUAGES.map(({ code }) => code).join("|");
    nuxt.hook("pages:extend", (routes) => {
      const marketing = routes.filter((route) =>
        ["/", "/tour", "/tour/:slug()", "/straight-answers"].includes(
          route.path,
        ),
      );

      for (const route of marketing) {
        routes.push({
          ...route,
          name: `${route.name}-translated`,
          path: `/:language(${languages})${route.path === "/" ? "" : route.path}`,
        });
      }
    });

    addTemplate({
      filename: "site-translations.mjs",
      getContents: () =>
        [
          `export const translatedPages = ${JSON.stringify(pages)};`,
          `export const translatedData = ${JSON.stringify(data)};`,
          `export const localizedScreenshots = ${JSON.stringify(screenshots)};`,
        ].join("\n"),
    });

    addTypeTemplate({
      filename: "types/site-translations.d.ts",
      getContents: () =>
        [
          `declare module "#build/site-translations.mjs" {`,
          `  export const translatedPages: Record<string, string[]>;`,
          `  export const translatedData: Record<string, string[]>;`,
          `  export const localizedScreenshots: Record<string, string[]>;`,
          `}`,
        ].join("\n"),
    });
  },
});
