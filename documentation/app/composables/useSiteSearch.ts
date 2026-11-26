import MiniSearch from "minisearch";

/**
 * The site search.
 *
 * Every section of every page is one thing to find, and the tour and the
 * straight answers are in it too. What makes it good is the ranking: a word
 * in a title counts for much more than the same word somewhere in a
 * paragraph, a page counts for more than a section deep inside one, and a
 * typo or half a word still finds what was meant.
 */

interface Section {
  // Where it is: the page, with the anchor of the section when it has one.
  id: string;
  title: string;
  // The headings above it, outermost first.
  titles: string[];
  level: number;
  content: string;
}

interface Entry extends Omit<Section, "id"> {
  // One page can be in here many times over, so where it is does not do as
  // its key.
  key: number;
  to: string;
  trail: string;
}

export interface SearchResult extends Section {
  snippets: { title?: string; content?: string };
}

// No more than this many results from one page: a long page that mentions
// the word in every section should not push every other page off the list.
const PER_PAGE = 3;

const SNIPPET_BEFORE = 40;
const SNIPPET_LENGTH = 160;

// Words that are in every question and say nothing about it. Left out, so
// "is it safe" looks for "safe". Not "on" and "off": here those mean something.
const FILLER = new Set(
  "a an and are be can do does how i is it my of or that the this to what".split(
    " ",
  ),
);

// The filler words of the languages written without spaces, from their
// corpus. Not those of
// the other languages: their lists have words like "aan" and "uit" in them,
// which mean on and off here, and the English list works for them.
const STOPWORDS = import.meta.glob<string>(
  "../../translations/corpus/*/stopwords.txt",
  { query: "?raw", import: "default" },
);

/** The words left out of the index and out of what is typed. */
async function fillerOf(language: string): Promise<Set<string>> {
  const load =
    isWrittenWithoutSpaces(language) &&
    STOPWORDS[`../../translations/corpus/${language}/stopwords.txt`];
  if (!load) {
    return FILLER;
  }

  const words = (await load())
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));

  return new Set([...FILLER, ...words]);
}

const processTermWith = (filler: Set<string>) => (term: string) => {
  const word = term.toLowerCase();
  return filler.has(word) ? null : word;
};

const escapeForRegExp = (text: string) =>
  text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Mark the words that matched, for the palette to show in cyan. */
function mark(text: string, words: string[]): string | undefined {
  if (!words.length) {
    return undefined;
  }

  const pattern = new RegExp(
    `(${words
      .sort((a, b) => b.length - a.length)
      .map(escapeForRegExp)
      .join("|")})`,
    "giu",
  );
  const marked = text.replace(pattern, "<mark>$1</mark>");
  return marked === text ? undefined : marked;
}

/** The part of the text around the first word that matched. */
function around(text: string, words: string[]): string {
  const lower = text.toLowerCase();
  const first = words
    .map((word) => lower.indexOf(word.toLowerCase()))
    .filter((index) => index !== -1)
    .sort((a, b) => a - b)[0];

  const start = Math.max((first ?? 0) - SNIPPET_BEFORE, 0);
  const cut = text.slice(start, start + SNIPPET_LENGTH).trim();
  return `${start > 0 ? "…" : ""}${cut}${start + SNIPPET_LENGTH < text.length ? "…" : ""}`;
}

/**
 * The marketing pages are not Markdown, so they are added by hand. In the
 * language being read, where their text is translated.
 */
async function marketingSections(
  language: string,
  fill: (text: string) => string,
): Promise<Section[]> {
  const [tours, answers] = await Promise.all([
    queryTours(language),
    queryAnswers(language),
  ]);

  const tourSections = tours.flatMap((tour) => {
    const path = tourPath(tour.stem);
    return [
      {
        id: path,
        title: tour.hero.title,
        titles: [],
        level: 1,
        content: fill(`${tour.description} ${tour.hero.description}`),
      },
      ...tour.sections.map((section) => ({
        id: path,
        title: section.title,
        titles: [tour.hero.title],
        level: 2,
        content: fill(
          [
            section.description,
            ...section.features.map(
              (feature) => `${feature.title}. ${feature.description}`,
            ),
          ].join(" "),
        ),
      })),
    ];
  });

  const answerSections = (answers?.groups ?? []).flatMap((group) =>
    group.questions.map((question) => ({
      id: "/straight-answers",
      title: question.question,
      titles: [answers!.title],
      level: 2,
      content: question.answer,
    })),
  );

  return [...tourSections, ...answerSections];
}

/**
 * The pages of the docs, by section, in a language. A page that was never
 * translated is in there in English: better found in English than not at all.
 */
async function docsSections(language: string): Promise<Section[]> {
  const english = (await queryCollectionSearchSections("docs")) as Section[];
  if (language === DEFAULT_LANGUAGE) {
    return english;
  }

  const translated = (await queryCollectionSearchSections(
    `docs_${collectionCode(language)}` as "docs",
  )) as Section[];

  return [
    ...translated,
    ...english.filter((section) => !isTranslated(section.id, language)),
  ];
}

export function useSiteSearch() {
  const { language, localTo } = useSiteLanguage();

  // The tour writes `{actions}` and the like where a count goes, and fills
  // them in on the page. The search shows the same text, so it fills them in
  // too. Asked for here, while the component is set up, and awaited later.
  const counting = useSpookCounts();

  const status = ref<"idle" | "pending" | "ready">("idle");
  let index: MiniSearch<Entry> | undefined;

  // Another language is another index. The next search builds it.
  watch(language, () => {
    index = undefined;
    status.value = "idle";
  });

  // Built in the browser, the first time somebody opens the search. Nobody
  // who only reads a page pays for it.
  async function build() {
    if (status.value !== "idle") {
      return;
    }
    status.value = "pending";

    const counts = await counting;
    const fill = (text: string) =>
      text.replace(/\{(\w+)\}/g, (placeholder, key: string) => {
        const value = counts.value[key as keyof typeof counts.value];
        return value === undefined ? placeholder : String(value);
      });

    const [docs, marketing, filler] = await Promise.all([
      docsSections(language.value),
      marketingSections(language.value, fill),
      fillerOf(language.value),
    ]);

    index = new MiniSearch<Entry>({
      idField: "key",
      fields: ["title", "trail", "content"],
      storeFields: ["to", "title", "titles", "level", "content"],
      tokenize: searchTokenizer(language.value),
      processTerm: processTermWith(filler),
      searchOptions: {
        boost: { title: 6, trail: 2 },
        // Half a word finds it, and so does a word with a typo in it.
        prefix: searchByPrefix,
        fuzzy: searchTypos,
        // A page is a better answer than a paragraph somewhere inside one.
        boostDocument: (_key, _term, stored) =>
          stored?.level === 1 ? 1.5 : stored?.level === 2 ? 1.15 : 1,
      },
    });

    index.addAll(
      [...docs, ...marketing].map(({ id, ...section }, key) => ({
        ...section,
        key,
        to: id,
        trail: section.titles.join(" "),
      })),
    );
    status.value = "ready";
  }

  async function search(
    term: string,
    options: { limit?: number } = {},
  ): Promise<SearchResult[]> {
    await build();
    if (!index) {
      return [];
    }

    // Every word has to be there. Only when that finds nothing at all, any
    // of them will do: better a near miss than an empty list.
    let found = index.search(term, { combineWith: "AND" });
    if (!found.length) {
      found = index.search(term, { combineWith: "OR" });
    }

    // Exactly what was typed, as a title, goes first whatever the scores say.
    const typed = term.trim().toLowerCase();
    found.sort(
      (a, b) =>
        Number(b.title.toLowerCase() === typed) -
          Number(a.title.toLowerCase() === typed) || b.score - a.score,
    );

    const perPage = new Map<string, number>();
    const results: SearchResult[] = [];

    for (const hit of found) {
      const page = (hit.to as string).split("#")[0]!;
      const count = perPage.get(page) ?? 0;
      if (count >= PER_PAGE) {
        continue;
      }
      perPage.set(page, count + 1);

      // What matched in the text, which for a typo is not what was typed.
      const words = [...new Set([...hit.terms, ...hit.queryTerms])];
      const content = around(hit.content as string, words);

      results.push({
        id: localTo(hit.to as string),
        title: hit.title as string,
        // Without the title of the page: the palette already names the page
        // a result is on, by its shorter name from the menu.
        titles: (hit.titles as string[]).slice(1),
        level: hit.level as number,
        content,
        snippets: {
          title: mark(hit.title as string, words),
          content: mark(content, words),
        },
      });

      if (results.length >= (options.limit ?? 12)) {
        break;
      }
    }

    return results;
  }

  return { search, status, build };
}
