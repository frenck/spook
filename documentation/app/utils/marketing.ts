import { translatedData } from "#build/site-translations.mjs";

/**
 * The text of the tour and the straight answers, in a language.
 *
 * They are data files, translated by the pipeline into
 * `translations/output/<language>/data/`, which the site reads as the
 * collections `tour_<language>` and `answers_<language>`. A file that was
 * not translated yet is read in English.
 */
function hasData(language: string, file: string): boolean {
  return (
    language !== DEFAULT_LANGUAGE &&
    (translatedData[language]?.includes(file) ?? false)
  );
}

/** Every part of the tour, in order. */
export async function queryTours(language: string) {
  const english = await queryCollection("tour").order("order", "ASC").all();
  if (!english.some((tour) => hasData(language, tourFile(tour.stem)))) {
    return english;
  }

  // The same file has the same stem in every language: `data/tour/repairs`.
  const translated = new Map(
    (
      await queryCollection(`tour_${collectionCode(language)}` as "tour").all()
    ).map((tour) => [tour.stem, tour]),
  );

  return english.map((tour) => translated.get(tour.stem) ?? tour);
}

/** The straight answers. */
export function queryAnswers(language: string) {
  const collection = hasData(language, "answers.yml")
    ? `answers_${collectionCode(language)}`
    : "answers";

  return queryCollection(collection as "answers").first();
}

/** Where a part of the tour is, by its stem: `data/tour/repairs`. */
export function tourPath(stem: string): string {
  return `/tour/${stem.split("/").pop()}`;
}

function tourFile(stem: string): string {
  return `${stem.replace(/^data\//, "")}.yml`;
}
