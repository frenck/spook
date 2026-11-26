/**
 * The structural checks: is the translation still the same page?
 *
 * None of this judges the language. It proves that what must not change did
 * not change: the code, the links, the components, the anchors, the labels
 * Home Assistant shows. A translation that fails is not written.
 */
import { parse } from "yaml";

import { literalStrong } from "./emphasis.ts";
import { bold } from "./glossary.ts";
import {
  cells,
  FRONT_MATTER_TEXT,
  frontMatterValues,
  headings,
  segment,
  splitFrontMatter,
  TEXT_PROPS,
  TOKEN,
} from "./segment.ts";
import type { Page, Section } from "./segment.ts";

export interface Rules {
  /** English label to the label the product shows in this language. */
  labels: Record<string, string>;
  /** Names that are written the same in every language. */
  keep: string[];
  /** Patterns a translation never contains, as regular expressions. */
  never: string[];
  /** Hashtag jokes with a local version: `#English` to `#Local`. */
  hashtags: Record<string, string>;
  /** Pinned translations this section has to contain. */
  corrections: string[];
}

const INLINE_CODE = /(`+)(?!`)(.*?[^`])\1(?!`)/g;
const EMOJI = /\p{Extended_Pictographic}/gu;
const HASHTAG = /#[A-Za-z][A-Za-z0-9]+/g;

function sorted(values: Iterable<string>): string {
  return [...values].sort().join("\n");
}

function count(haystack: string[], needle: string): number {
  return haystack.filter((value) => value === needle).length;
}

/** What kind of line this is. Two pages with the same kinds line up. */
function kind(line: string): string {
  if (!line.trim()) {
    return "blank";
  }

  const heading = line.match(/^(#{2,6}) /);
  if (heading) {
    return `heading ${heading[1]!.length}`;
  }

  if (/^⟦(CODE|H)\d+⟧$/.test(line)) {
    return line;
  }

  const component = line.match(/^(\s*:+[a-z][a-z0-9-]*)(\{(⟦P\d+⟧)?.*\})?\s*$/);
  if (component) {
    const props = TEXT_PROPS.filter((prop) =>
      new RegExp(`\\s${prop}="[^"]*"`).test(component[2] ?? ""),
    );
    return `component ${component[1]} ${component[3] ?? ""} ${props.join(",")}`;
  }

  if (/^\s*:+\s*$/.test(line)) {
    return `close ${line.trimEnd()}`;
  }

  if (/^\s*\|/.test(line)) {
    const row = cells(line);
    const rule = row.every((cell) => /^:?-+:?$/.test(cell));
    return `table ${row.length}${rule ? " rule" : ""}`;
  }

  const item = line.match(/^(\s*)([-*+]|\d+\.) /);
  if (item) {
    return `item ${item[1]!.length} ${item[2]}`;
  }

  return `text ${line.match(/^\s*/)![0].length}`;
}

function prose(masked: string): string {
  return masked.replace(INLINE_CODE, "").replace(TOKEN, "");
}

function verifyFrontMatter(section: Section, translated: string): string[] {
  const errors: string[] = [];
  const english = frontMatterValues(section.masked);
  const values = frontMatterValues(translated);

  for (const key of english.keys()) {
    if (!values.get(key)) {
      errors.push(`front matter: "${key}" is missing or empty`);
    }
  }
  for (const key of values.keys()) {
    if (!english.has(key)) {
      errors.push(`front matter: "${key}" is not in the English page`);
    }
  }

  // The site cuts a description at the first `: ` in some places, and a
  // second line would not be a description any more.
  const description = values.get("description");
  if (description?.includes(": ")) {
    errors.push('front matter: "description" contains a colon and a space');
  }
  if (translated.split("\n").length !== section.masked.split("\n").length) {
    errors.push("front matter: every key takes exactly one line");
  }

  return errors;
}

/** Check one translated section against its English one. Both masked. */
// A Chinese, Japanese or Korean character says what takes a few Latin
// letters, so natural Chinese is about a third of the English in characters.
const WIDE_CHARACTER =
  /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/gu;

/**
 * How long a text is, for comparing it with the English: a Chinese,
 * Japanese or Korean character counts as two letters.
 */
export function textLength(text: string): number {
  return text.length + (text.match(WIDE_CHARACTER)?.length ?? 0);
}

export function verifySection(
  section: Section,
  translated: string,
  rules: Rules,
): string[] {
  const errors: string[] = [];
  const english = section.masked;

  if (section.kind === "frontmatter") {
    errors.push(...verifyFrontMatter(section, translated));
  } else {
    // Tokens: every one back, exactly once, and nothing made up.
    const expected = [...english.matchAll(TOKEN)].map((match) => match[0]);
    const found = [...translated.matchAll(TOKEN)].map((match) => match[0]);
    if (sorted(expected) !== sorted(found)) {
      const missing = expected.filter((token) => !found.includes(token));
      const extra = found.filter(
        (token) => count(found, token) > count(expected, token),
      );
      errors.push(
        `tokens differ: missing ${missing.join(" ") || "none"}, extra or repeated ${[...new Set(extra)].join(" ") || "none"}`,
      );
    }
    if (/⟦(?![A-Z]+\d+⟧)|(?<!⟦[A-Z]+\d+)⟧/.test(translated)) {
      errors.push("a token is damaged");
    }

    // Links: the same targets, in the same order.
    const targets = (text: string) =>
      [...text.matchAll(/\]\((⟦L\d+⟧)\)/g)].map(
        (match) => section.tokens[match[1]!] ?? match[1]!,
      );
    if (targets(english).join("\n") !== targets(translated).join("\n")) {
      errors.push("links differ in number, order or target");
    }

    // Terms: each `:term[text]` keeps its token right behind it.
    const terms = (text: string) =>
      [...text.matchAll(/:term\[[^\]]+\]⟦T\d+⟧/g)].length;
    if (terms(translated) !== Object.keys(section.terms).length) {
      errors.push("a :term[...] lost its text or its token");
    }

    // Shape: the same kind of thing on every line. This covers headings,
    // list items, table rows and columns, components and code blocks.
    const englishLines = english.split("\n");
    const lines = translated.split("\n");
    if (englishLines.length !== lines.length) {
      errors.push(
        `${lines.length} lines where the English has ${englishLines.length}: a paragraph, list item or blank line was added or dropped`,
      );
    } else {
      englishLines.forEach((line, index) => {
        if (kind(line) !== kind(lines[index]!)) {
          errors.push(
            `line ${index + 1} is "${kind(lines[index]!)}" where the English is "${kind(line)}"`,
          );
        }
      });
    }

    // Inline code: the same spans, byte for byte. Order may differ.
    const code = (text: string) =>
      sorted([...text.matchAll(INLINE_CODE)].map((match) => match[0]));
    if (code(english) !== code(translated)) {
      errors.push("inline code differs from the English");
    }

    // Length: a translation at 40% or 250% of the source is wrong.
    if (english.length > 200) {
      const ratio = textLength(translated) / english.length;
      if (ratio < 0.4 || ratio > 2.5) {
        errors.push(
          `length is ${Math.round(ratio * 100)}% of the English section`,
        );
      }
    }
  }

  // Labels: what Home Assistant shows, exactly as it shows it.
  const englishBold = bold(english);
  const translatedBold = bold(translated);
  for (const [label, translation] of Object.entries(rules.labels)) {
    const needed = count(englishBold, label);
    if (needed && count(translatedBold, translation) < needed) {
      errors.push(
        `label **${label}** has to be **${translation}**, ${needed} time(s)`,
      );
    }
  }

  // Names: the same in every language.
  const englishProse = prose(english);
  const translatedProse = prose(translated);
  for (const name of rules.keep) {
    if (englishProse.includes(name) && !translatedProse.includes(name)) {
      errors.push(`"${name}" is gone, it is never translated`);
    }
  }

  for (const pattern of rules.never) {
    const expression = new RegExp(pattern, "u");
    const hit = translatedProse.match(expression);
    if (hit && !expression.test(englishProse)) {
      errors.push(`"${hit[0]}" is not allowed here (rule: ${pattern})`);
    }
  }

  // Emoji: the same ones, as often.
  const emoji = (text: string) => sorted(text.match(EMOJI) ?? []);
  if (emoji(english) !== emoji(translated)) {
    errors.push("emoji differ from the English");
  }

  // Hashtags: kept as written, unless jokes.yml has a local one.
  for (const hashtag of englishProse.match(HASHTAG) ?? []) {
    const local = rules.hashtags[hashtag] ?? hashtag;
    if (!translatedProse.includes(local)) {
      errors.push(`hashtag ${hashtag} has to stay ${local}`);
    }
  }

  for (const correction of rules.corrections) {
    if (!translated.includes(correction)) {
      errors.push(`pinned correction is missing: "${correction}"`);
    }
  }

  return errors;
}

/** Bold strings without a glossary entry that did not stay English. */
export function changedUnknown(
  section: Section,
  translated: string,
  unknown: string[],
): string[] {
  const found = bold(translated);
  return unknown.filter((label) => !found.includes(label));
}

function withoutText(frontMatter: string): unknown {
  const data = (parse(frontMatter.replace(/^---\n|---\n$/g, "")) ??
    {}) as Record<string, unknown>;

  for (const key of FRONT_MATTER_TEXT) {
    const path = key.split(".");
    let parent: Record<string, unknown> | undefined = data;
    for (const part of path.slice(0, -1)) {
      parent = parent?.[part] as Record<string, unknown> | undefined;
    }
    if (parent && typeof parent === "object") {
      delete parent[path.at(-1)!];
    }
  }

  return data;
}

/** Check a whole translated page against the English page it came from. */
export function verifyPage(english: string, translated: string): string[] {
  const errors: string[] = [];
  const source = splitFrontMatter(english);
  const output = splitFrontMatter(translated);

  if (/[⟦⟧]/.test(translated)) {
    errors.push("a mask token is left in the page");
  }

  try {
    const expected = JSON.stringify(withoutText(source.frontMatter));
    if (JSON.stringify(withoutText(output.frontMatter)) !== expected) {
      errors.push("front matter differs outside of the translated keys");
    }
  } catch (error) {
    errors.push(`front matter does not parse: ${(error as Error).message}`);
  }

  const anchors = (body: string) =>
    headings(body)
      .map((heading) => `${heading.level} ${heading.id}`)
      .join("\n");
  if (anchors(source.body) !== anchors(output.body)) {
    errors.push("the anchors differ from the English page");
  }

  // Bold and italic that Markdown does not close show their asterisks.
  // Counted per section against the English, which has a few on purpose.
  const translatedSections = new Map(
    segment(translated).sections.map((section) => [section.id, section]),
  );
  for (const section of segment(english).sections) {
    const match = translatedSections.get(section.id);
    if (section.kind !== "body" || !match) {
      continue;
    }

    const expected = literalStrong(section.source);
    const found = literalStrong(match.source);
    if (found > expected) {
      errors.push(
        `[${section.id}] ${found} literal ** or __ where the English has ${expected}: bold or italic that does not close`,
      );
    }
  }

  return errors;
}

/**
 * What a page is made of, apart from its text: the kind of every line, with
 * the code, link targets, component props and glossary keys filled back in.
 * A page and its translation have the same skeleton.
 */
export function skeleton(page: Page): string[] {
  const facts: string[] = [];

  for (const section of page.sections) {
    if (section.kind === "frontmatter") {
      facts.push(
        `front matter: ${[...frontMatterValues(section.masked).keys()]}`,
      );
      continue;
    }

    const resolve = (text: string) =>
      text.replace(TOKEN, (token) => {
        if (token.startsWith("⟦T")) {
          return `{${section.terms[token]?.key}}`;
        }
        const value = section.tokens[token] ?? token;
        return token.startsWith("⟦P")
          ? TEXT_PROPS.reduce(
              (line, prop) =>
                line.replace(new RegExp(`([{\\s]${prop}=")[^"]*"`), '$1"'),
              value,
            )
          : value;
      });

    for (const line of section.masked.split("\n")) {
      const tokens = (line.match(TOKEN) ?? []).filter(
        (token) => !token.startsWith("⟦T"),
      );
      facts.push(
        [kind(line).replace(TOKEN, ""), ...tokens.map(resolve)].join(" | "),
      );
    }

    const code = [...section.masked.matchAll(INLINE_CODE)].map(
      (match) => match[0],
    );
    const terms = Object.values(section.terms).map((term) => term.key);
    facts.push(`code: ${sorted(code)}`, `terms: ${sorted(terms)}`);
  }

  return facts;
}
