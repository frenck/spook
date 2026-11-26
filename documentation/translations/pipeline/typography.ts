/**
 * The spaces a language wants around its punctuation, put in by the machine.
 *
 * French puts a non-breaking space before `:`, `;`, `!` and `?`, and inside
 * « guillemets ». A model forgets that now and then, and a person typing a
 * fix never sees the difference between the two spaces. So the assembler
 * does it, from `corpus/<language>/typography.yml`. A language without that
 * file is left alone.
 *
 * It works on masked text: code blocks, links, URLs and component props are
 * tokens by then, so they cannot be touched. Inline code is skipped here.
 */
import { parse } from "yaml";

import { corpus } from "./config.ts";

export interface Typography {
  /** The marks that take a non-breaking space before them. */
  before: string[];
  /** Pairs of quotes that take a non-breaking space inside them. */
  inside: [string, string][];
}

const NO_BREAK = "\u00a0";
const INLINE_CODE = /(`+)(?!`)(.*?[^`])\1(?!`)/g;

// Already a non-breaking space of some width: the translator chose it.
const SPACES = new Set([NO_BREAK, "\u202f"]);

// A mark only counts as punctuation when the sentence goes on after it, or
// ends, or another mark follows (`?!`). `08:00`, `:term[` and `![image]`
// have something else right behind.
const AFTER = /^($|[\s*_)\]"'»|.,])/;

// Lines that are not prose: a component and its props, a lone token, the
// dashes under a table header.
const COMPONENT = /^\s*:+[a-z]/;
const LONE_TOKEN = /^\s*⟦[A-Z]+\d+⟧\s*$/;
const TABLE_RULE = /^\s*\|(\s*:?-+:?\s*\|)+\s*$/;
const IMAGE_ALT = /!\[[^\]]*\]/g;

/** The rules of a language, or nothing when it has none. */
export function typographyFor(lang: string): Typography | undefined {
  const file = parse(corpus(lang, "typography.yml")) as {
    non_breaking_space?: { before?: string[]; inside?: [string, string][] };
  } | null;
  const rules = file?.non_breaking_space;
  if (!rules) {
    return undefined;
  }

  return { before: rules.before ?? [], inside: rules.inside ?? [] };
}

/** What one line is typeset with. */
interface Context {
  rules: Typography;
  /** The labels the line has to keep exactly as Home Assistant has them. */
  labels: string[];
  /** The English section, to tell English that was kept from French. */
  english: string;
}

/**
 * Whether the mark after `before` belongs to English the translation kept as
 * it is: a name like "Boo!", or a dialog quoted the way it reads. The word
 * before the mark, and the mark, are in the English section as they are.
 * Only asked when there is no space at all before the mark: a translator
 * who typed a space wrote French.
 */
function keptEnglish(before: string, mark: string, english: string): boolean {
  const word = before.split(/\s+/).at(-1)!;
  return word.length > 0 && english.includes(word + mark);
}

/** Put the spaces in one stretch of prose, without code in it. */
function prose(text: string, context: Context): string {
  const { rules, english } = context;
  let result = "";

  for (let index = 0; index < text.length; index++) {
    const character = text[index]!;
    const previous = result.at(-1);

    const rest = text.slice(index + 1);
    const punctuation =
      AFTER.test(rest) || rules.before.includes(rest[0] ?? "");
    if (rules.before.includes(character) && punctuation) {
      // A plain space is swapped, a missing one is added. At the start of a
      // line, or right after another mark (`?!`), there is nothing to do.
      if (previous === " ") {
        result = result.slice(0, -1) + NO_BREAK;
      } else if (
        previous !== undefined &&
        !SPACES.has(previous) &&
        !rules.before.includes(previous) &&
        !keptEnglish(result, character, english)
      ) {
        result += NO_BREAK;
      }
      result += character;
      continue;
    }

    const closing = rules.inside.some(([, close]) => close === character);
    if (closing && previous !== undefined && !SPACES.has(previous)) {
      result = (previous === " " ? result.slice(0, -1) : result) + NO_BREAK;
    }
    result += character;

    const opening = rules.inside.some(([open]) => open === character);
    if (opening && index + 1 < text.length && !SPACES.has(text[index + 1]!)) {
      result += NO_BREAK;
      if (text[index + 1] === " ") {
        index++;
      }
    }
  }

  return result;
}

/** Where a pattern matches in a line, as start and end. */
function spans(line: string, pattern: RegExp): [number, number][] {
  return [...line.matchAll(pattern)].map((match) => [
    match.index,
    match.index + match[0].length,
  ]);
}

/**
 * Put the spaces in one line of prose. Inline code, labels and the alt text
 * of an image are left alone: code is code, a label is what Home Assistant
 * shows on screen, bold or not, and alt text is a prop like any other.
 */
function typesetLine(line: string, context: Context): string {
  const kept = [
    ...spans(line, INLINE_CODE),
    ...spans(line, IMAGE_ALT),
    ...context.labels.flatMap((label) =>
      spans(line, new RegExp(escape(label), "g")),
    ),
  ].sort((a, b) => a[0] - b[0]);

  let result = "";
  let from = 0;
  for (const [start, end] of kept) {
    if (start < from) {
      continue;
    }

    result += prose(line.slice(from, start), context) + line.slice(start, end);
    from = end;
  }

  return result + prose(line.slice(from), context);
}

/**
 * Put the spaces in a masked section: its front matter values, or its body.
 *
 * `english` is the English section it was translated from, and `labels` the
 * label translations of the glossary, kept as they are. Only the ones with a
 * mark in them matter, so only those are looked for.
 */
export function typeset(
  masked: string,
  kind: "frontmatter" | "body",
  rules: Typography | undefined,
  english: string,
  labels: string[] = [],
): string {
  if (!rules) {
    return masked;
  }

  const marks = [...rules.before, ...rules.inside.flat()];
  const context = {
    rules,
    english,
    labels: labels.filter((label) =>
      marks.some((mark) => label.includes(mark)),
    ),
  };
  return masked
    .split("\n")
    .map((line) => {
      if (kind === "frontmatter") {
        // `title: ...`: the key and its colon are YAML, the value is prose.
        const pair = line.match(/^([a-z_.]+: )(.*)$/);
        return pair ? pair[1] + typesetLine(pair[2]!, context) : line;
      }

      if (
        COMPONENT.test(line) ||
        LONE_TOKEN.test(line) ||
        TABLE_RULE.test(line)
      ) {
        return line;
      }

      return typesetLine(line, context);
    })
    .join("\n");
}

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
