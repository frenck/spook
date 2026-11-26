/**
 * How the site search cuts text into words, in every language.
 *
 * Shared with the tests, so it has no Nuxt in it.
 */

// `automation.snooze` and `create_area` are found by their parts as well.
const splitOnNonLetters = (text: string) =>
  text.split(/[^\p{L}\p{N}]+/u).filter(Boolean);

// Languages written without spaces between words. Splitting on what is not
// a letter finds no words in them: a whole Chinese sentence would be one
// "word". The browser knows where their words end, so it is asked.
const WITHOUT_SPACES = new Set(["zh", "ja", "th", "lo", "km", "my"]);

// A word in one of those scripts.
const UNSPACED_SCRIPT =
  /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Thai}\p{Script=Lao}\p{Script=Khmer}\p{Script=Myanmar}]/u;

/** Whether a language is written without spaces between its words. */
export function isWrittenWithoutSpaces(language: string): boolean {
  return WITHOUT_SPACES.has(language.split("-")[0]!);
}

/** How a language is cut into words, for the index and for what is typed. */
export function searchTokenizer(language: string): (text: string) => string[] {
  if (
    !isWrittenWithoutSpaces(language) ||
    typeof Intl.Segmenter !== "function"
  ) {
    return splitOnNonLetters;
  }

  const segmenter = new Intl.Segmenter(language, { granularity: "word" });

  // The words the browser finds, each cut further the usual way: Chinese
  // text has `automation.snooze` in it too.
  return (text: string) =>
    [...segmenter.segment(text)]
      .filter((segment) => segment.isWordLike)
      .flatMap((segment) => splitOnNonLetters(segment.segment));
}

/**
 * Whether a word also finds the longer words it is the start of. Not one
 * letter: "o" would find everything. One Chinese character is a word of its
 * own, and the start of many more: 自 finds 自动.
 */
export function searchByPrefix(term: string): boolean {
  return term.length > 1 || UNSPACED_SCRIPT.test(term);
}

/**
 * How many typos a word may have and still be found. Short words none: "on"
 * is not "or". Chinese words none at all: they are one to three characters,
 * and one character off is another word.
 */
export function searchTypos(term: string): number | false {
  if (UNSPACED_SCRIPT.test(term)) {
    return false;
  }

  return term.length > 6 ? 2 : term.length > 3 ? 1 : false;
}
