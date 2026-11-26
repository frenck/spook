import { defineContentConfig, defineCollection, z } from "@nuxt/content";
import { fileURLToPath } from "node:url";
import { collectionCode, TRANSLATED_LANGUAGES } from "./shared/utils/languages";

const docsSchema = z.object({
  links: z
    .array(
      z.object({
        label: z.string(),
        icon: z.string(),
        to: z.string(),
        target: z.string().optional(),
      }),
    )
    .optional(),
  // A reference page, shown as an index to filter rather than one long
  // page: what one entry on it is called, or the glossary. Every entry
  // stays a `##` heading in the Markdown.
  reference: z.enum(["action", "trigger", "condition", "glossary"]).optional(),
});

const translatedDocs = Object.fromEntries(
  TRANSLATED_LANGUAGES.map(({ code }) => [
    `docs_${collectionCode(code)}`,
    defineCollection({
      type: "page",
      source: {
        cwd: fileURLToPath(
          new URL(`./translations/output/${code}/content`, import.meta.url),
        ),
        // Only the pages. Next to each sits a lock file of the pipeline.
        include: "**/*.md",
      },
      schema: docsSchema,
    }),
  ]),
);

// The tour: the text of each part, and what goes with it.
const tourSchema = z.object({
  // Where it comes in the overview of the tour.
  order: z.number(),
  title: z.string(),
  description: z.string(),
  hero: z.object({
    headline: z.string(),
    title: z.string(),
    description: z.string(),
    screenshot: z.string(),
    alt: z.string(),
  }),
  sections: z.array(
    z.object({
      headline: z.string(),
      title: z.string(),
      description: z.string(),
      screenshot: z.string(),
      alt: z.string(),
      features: z.array(
        z.object({
          title: z.string(),
          description: z.string(),
          icon: z.string(),
        }),
      ),
    }),
  ),
  // Where to go next: the cards at the bottom, into the docs.
  more: z.object({
    title: z.string(),
    links: z.array(
      z.object({
        title: z.string(),
        description: z.string(),
        icon: z.string(),
        to: z.string(),
      }),
    ),
  }),
});

// The straight answers, by group.
const answersSchema = z.object({
  title: z.string(),
  description: z.string(),
  groups: z.array(
    z.object({
      title: z.string(),
      icon: z.string(),
      questions: z.array(
        z.object({
          question: z.string(),
          answer: z.string(),
          link: z.object({ label: z.string(), to: z.string() }).optional(),
        }),
      ),
    }),
  ),
});

const translatedData = Object.fromEntries(
  TRANSLATED_LANGUAGES.flatMap(({ code }) => {
    // Only the data. The pages and the lock files of the pipeline sit in
    // the same directory.
    const cwd = fileURLToPath(
      new URL(`./translations/output/${code}`, import.meta.url),
    );

    return [
      [
        `tour_${collectionCode(code)}`,
        defineCollection({
          type: "data",
          source: { cwd, include: "data/tour/*.yml" },
          schema: tourSchema,
        }),
      ],
      [
        `answers_${collectionCode(code)}`,
        defineCollection({
          type: "data",
          source: { cwd, include: "data/answers.yml" },
          schema: answersSchema,
        }),
      ],
    ];
  }),
);

export default defineContentConfig({
  collections: {
    landing: defineCollection({
      type: "page",
      source: "index.md",
    }),
    docs: defineCollection({
      type: "page",
      source: {
        include: "**",
        exclude: ["index.md", "data/**"],
      },
      schema: docsSchema,
    }),
    // The same pages in another language: machine translations, made by the
    // pipeline in `translations/`. A page keeps the `path` of its English
    // original, so `/nl/automation` is `/automation` in `docs_nl`.
    ...translatedDocs,
    // Small pieces of Markdown for pages that are not themselves Markdown,
    // like the code example on the home page. They are highlighted at build
    // time, the same way as every code block in the docs.
    snippets: defineCollection({
      type: "page",
      source: "data/snippets/**",
    }),
    // Videos, articles and podcasts about Spook, for the media page.
    media: defineCollection({
      type: "data",
      source: "data/media.yml",
      schema: z.object({
        videos: z.array(
          z.object({
            title: z.string(),
            author: z.string(),
            youtube: z.string(),
            language: z.string().length(2),
            date: z.string(),
            // Seconds into the video where Spook comes up, when it is not
            // the whole video.
            start: z.number().optional(),
          }),
        ),
        articles: z.array(
          z.object({
            title: z.string(),
            author: z.string(),
            url: z.string().url(),
            language: z.string().length(2),
            date: z.string(),
            // The page's own preview (OpenGraph) image, kept as a local copy
            // under public/ so it does not rot or ping a third party.
            image: z.string().optional(),
          }),
        ),
        podcasts: z.array(
          z.object({
            title: z.string(),
            show: z.string(),
            url: z.string().url(),
            language: z.string().length(2),
            date: z.string(),
            image: z.string().optional(),
            note: z.string().optional(),
          }),
        ),
      }),
    }),
    // The tour: one page per part of the toolbox, to show what it does before
    // the docs explain how. `{repairs}` and the like in the text are filled
    // in with the counts from the docs.
    tour: defineCollection({
      type: "data",
      source: "data/tour/*.yml",
      schema: tourSchema,
    }),
    // The questions people ask before they install, with honest answers.
    answers: defineCollection({
      type: "data",
      source: "data/answers.yml",
      schema: answersSchema,
    }),
    // Both in another language. The same files under the same names, so a
    // part of the tour has the same `stem` in every language.
    ...translatedData,
    // Blueprints by others that use what Spook adds, checked by hand.
    blueprints: defineCollection({
      type: "data",
      source: "data/blueprints.yml",
      schema: z.object({
        blueprints: z.array(
          z.object({
            title: z.string(),
            author: z.string(),
            url: z.string().url(),
            import: z.string().url().optional(),
            kind: z.enum(["automation", "script", "template"]),
            date: z.string(),
            uses: z.array(z.string()),
            summary: z.string(),
            outdated: z.string().optional(),
          }),
        ),
      }),
    }),
    // What people say about Spook, word for word, each with a link to where
    // they said it. A quote without a source does not go on the site.
    quotes: defineCollection({
      type: "data",
      source: "data/quotes.yml",
      schema: z.object({
        quotes: z.array(
          z.object({
            quote: z.string(),
            author: z.string(),
            platform: z.enum([
              "reddit",
              "forum",
              "github",
              "mastodon",
              "bluesky",
              "x",
              "youtube",
              "blog",
              "hacker-news",
            ]),
            url: z.string().url(),
            date: z.string().optional(),
            // The language it was written in, when not English. Such a quote
            // shows on the site in that language only, never translated.
            language: z.string().optional(),
            // Where the author's picture is. The site shows a local copy.
            avatar: z.string().url().optional(),
          }),
        ),
      }),
    }),
  },
});
