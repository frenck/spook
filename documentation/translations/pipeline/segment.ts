/**
 * Cut a page into sections, and hide what a translator must not touch.
 *
 * A section is one `##` or `###` heading and what is under it. The front
 * matter and the text before the first heading are sections of their own.
 * Glue the `source` of every section together and you have the page back,
 * byte for byte: that is what makes an unchanged section safe to leave alone.
 *
 * Masking swaps the parts that must survive as they are (code blocks, link
 * targets, component props) for tokens like `⟦L1⟧`. The translator moves the
 * tokens around with the sentence, and `unmask` puts the real thing back.
 * Inline code stays readable on purpose: `enabled: false` tells a translator
 * more than a token does. The checks in `verify.ts` prove it came back whole.
 */
import { isMap, isScalar, parseDocument, stringify } from "yaml";
import type { Scalar } from "yaml";

import { anchor } from "../../shared/utils/anchor.ts";

/** The front matter keys that hold text for a reader. */
export const FRONT_MATTER_TEXT = [
  "title",
  "description",
  "subtitle",
  "navigation.title",
];

/** The component props that hold text for a reader. */
export const TEXT_PROPS = ["label", "title", "alt"];

export const TOKEN = /⟦([A-Z]+)(\d+)⟧/g;

const FRONT_MATTER = /^---\n([\s\S]*?\n)?---\n/;
const FENCE = /^(\s*)(`{3,}|~{3,})/;
const HEADING = /^(#{2,6}) (.*)$/;
const EXPLICIT = /\s*\{#([a-z0-9-]+)\}\s*$/;
const COMPONENT = /^(\s*)(:+)([a-z][a-z0-9-]*)(\{.*\})?\s*$/;
const TABLE_ROW = /^\s*\|/;
const HTML_LINE = /^\s*<[a-zA-Z/!]/;
const INLINE_CODE = /(`+)(?!`)(.*?[^`])\1(?!`)/g;
const TERM = /:term\[([^\]]*)\](\{[^}]*\})?/g;
const LINK_TARGET = /\]\((<[^>]*>|[^()\s]*)\)(\{[^}\n]*\})?/g;
const BARE_URL = /<?https?:\/\/[^\s)>\]]+>?/g;

export interface Heading {
  level: number;
  /** The anchor the English heading has on the site, `-1` suffix included. */
  id: string;
  /** The ` {#explicit}` the English heading was written with, if any. */
  suffix: string;
}

export interface Term {
  /** The props as written in English, like `{to="entity"}`, or nothing. */
  original: string;
  /** The glossary key the term links to. */
  key: string;
}

export interface Table {
  original: string;
  masked: string;
  indent: string;
}

export interface Section {
  id: string;
  kind: "frontmatter" | "body";
  /** The English bytes of this section. */
  source: string;
  /** What the translator gets. */
  masked: string;
  /** What every token stands for. */
  tokens: Record<string, string>;
  terms: Record<string, Term>;
  headings: Heading[];
  tables: Table[];
}

export interface Page {
  sections: Section[];
}

/**
 * How the tokens go back.
 *
 * `identity` restores the English page exactly as it was written. It exists
 * to prove that masking loses nothing.
 * `translated` writes what a translated page needs on top: the English
 * anchor on every heading, and an explicit glossary key on every term.
 */
export type Mode = "identity" | "translated";

/**
 * What a heading reads as on the page: without term, bold or code markup.
 *
 * The same rule as `anchor` in `tests/documentation_helpers.py`.
 */
function plain(heading: string): string {
  return heading.replace(TERM, "$1").replace(/[`*_]/g, "").trim();
}

/** Call back for every line that is not inside a code block. */
function proseLines(
  lines: string[],
  visit: (line: string, index: number) => void,
): void {
  let fence: string | undefined;
  lines.forEach((line, index) => {
    const marker = line.match(FENCE)?.[2];
    if (fence) {
      if (marker?.startsWith(fence)) {
        fence = undefined;
      }
      return;
    }

    if (marker) {
      fence = marker;
      return;
    }

    visit(line, index);
  });
}

/**
 * Every heading of a Markdown body, with the anchor the site gives it.
 *
 * The same rule as `modules/myst-anchors.ts` and `headings` in
 * `tests/documentation_helpers.py`: an explicit `{#id}` wins, and the second
 * heading with the same anchor gets `-1`.
 */
export function headings(
  body: string,
): { level: number; text: string; id: string }[] {
  const found: { level: number; text: string; id: string }[] = [];
  const seen = new Map<string, number>();

  proseLines(body.split("\n"), (line) => {
    const match = line.match(HEADING);
    if (!match) {
      return;
    }

    const explicit = match[2]!.match(EXPLICIT);
    const text = match[2]!.replace(EXPLICIT, "");
    const slug = explicit ? explicit[1]! : anchor(plain(text));

    const count = seen.get(slug) ?? 0;
    seen.set(slug, count + 1);
    found.push({
      level: match[1]!.length,
      text,
      id: count ? `${slug}-${count}` : slug,
    });
  });

  return found;
}

/** Split a page into its front matter and its body. */
export function splitFrontMatter(text: string): {
  frontMatter: string;
  body: string;
} {
  const match = text.match(FRONT_MATTER);
  const frontMatter = match ? match[0] : "";
  return { frontMatter, body: text.slice(frontMatter.length) };
}

/** Cut a body into chunks that each start at a `##` or `###` heading. */
function chunks(body: string): string[] {
  const lines = body.split("\n");
  const starts: number[] = [];
  proseLines(lines, (line, index) => {
    if (/^#{2,3} /.test(line) && index > 0) {
      starts.push(index);
    }
  });

  const found: string[] = [];
  let from = 0;
  for (const start of [...starts, lines.length]) {
    const last = start === lines.length;
    const chunk = lines.slice(from, start).join("\n") + (last ? "" : "\n");
    if (chunk || !found.length) {
      found.push(chunk);
    }
    from = start;
  }

  return found;
}

/** Split a table row into its cells, without the outer pipes. */
export function cells(row: string): string[] {
  const inner = row.trim().replace(/^\|/, "").replace(/\|$/, "");
  return inner.split(/(?<!\\)\|/).map((cell) => cell.trim());
}

/** Write a table row without its padding. */
function squeeze(row: string): string {
  const squeezed = cells(row).map((cell) =>
    /^:?-+:?$/.test(cell) ? cell.replace(/-+/, "---") : cell,
  );
  return `| ${squeezed.join(" | ")} |`;
}

/** How wide text is in a monospace font: an emoji takes two columns. */
function width(text: string): number {
  let total = 0;
  for (const character of text.replace(/[‍️̀-ͯ]/g, "")) {
    total +=
      /\p{Extended_Pictographic}|[ᄀ-ᅟ⺀-꓏가-힣豈-﫿︰-﹏＀-｠￠-￦]/u.test(
        character,
      )
        ? 2
        : 1;
  }
  return total;
}

/** Line the columns of a table up again. */
function pad(rows: string[], indent: string): string[] {
  const table = rows.map(cells);
  const columns = Math.max(...table.map((row) => row.length));
  const widths = Array.from({ length: columns }, (_, column) =>
    Math.max(
      3,
      ...table.map((row) =>
        /^:?-+:?$/.test(row[column] ?? "") ? 3 : width(row[column] ?? ""),
      ),
    ),
  );

  return table.map((row) => {
    const padded = widths.map((size, column) => {
      const cell = row[column] ?? "";
      if (/^:?-+:?$/.test(cell)) {
        const left = cell.startsWith(":") ? ":" : "";
        const right = cell.endsWith(":") ? ":" : "";
        return left + "-".repeat(size - left.length - right.length) + right;
      }
      return cell + " ".repeat(size - width(cell));
    });
    return `${indent}| ${padded.join(" | ")} |`;
  });
}

class Masker {
  tokens: Record<string, string> = {};
  terms: Record<string, Term> = {};
  private counts = new Map<string, number>();

  token(kind: string, value: string): string {
    const count = (this.counts.get(kind) ?? 0) + 1;
    this.counts.set(kind, count);
    const name = `⟦${kind}${count}⟧`;
    this.tokens[name] = value;
    return name;
  }

  /** Mask the parts of one line of prose that are not text. */
  inline(line: string): string {
    let masked = "";
    let from = 0;

    // Inline code is left as it is, and nothing inside it is looked at.
    for (const code of line.matchAll(INLINE_CODE)) {
      masked += this.prose(line.slice(from, code.index)) + code[0];
      from = code.index + code[0].length;
    }

    return masked + this.prose(line.slice(from));
  }

  private prose(text: string): string {
    return text
      .replace(TERM, (_match, shown: string, props: string | undefined) => {
        const to = props?.match(/\bto="([^"]*)"/)?.[1];
        const name = this.token("T", props ?? "");
        this.terms[name] = {
          original: props ?? "",
          key: to ?? shown.toLowerCase(),
        };
        return `:term[${shown}]${name}`;
      })
      .replace(LINK_TARGET, (match) => `](${this.token("L", match.slice(1))})`)
      .replace(BARE_URL, (match) => this.token("U", match));
  }
}

function maskBody(
  id: string,
  source: string,
  ids: string[],
): Omit<Section, "kind"> {
  const masker = new Masker();
  const found: Heading[] = [];
  const tables: Table[] = [];
  const lines = source.split("\n");
  const masked: string[] = [];

  for (let index = 0; index < lines.length; index++) {
    const line = lines[index]!;

    const fence = line.match(FENCE);
    if (fence) {
      let end = index + 1;
      while (
        end < lines.length &&
        !lines[end]!.trimStart().startsWith(fence[2]!)
      ) {
        end++;
      }
      const block = lines.slice(index, end + 1).join("\n");
      masked.push(masker.token("CODE", block));
      index = end;
      continue;
    }

    const heading = line.match(HEADING);
    if (heading) {
      const suffix = heading[2]!.match(EXPLICIT)?.[0] ?? "";
      const text = heading[2]!.slice(0, heading[2]!.length - suffix.length);
      found.push({ level: heading[1]!.length, id: ids.shift()!, suffix });
      masked.push(`${heading[1]} ${masker.inline(text)}`);
      continue;
    }

    const component = line.match(COMPONENT);
    if (component) {
      const [, indent, colons, name, props] = component;
      if (!props) {
        masked.push(line);
        continue;
      }

      const text = TEXT_PROPS.flatMap((prop) => {
        const value = props.match(new RegExp(`[{\\s]${prop}="([^"]*)"`));
        return value ? [` ${prop}="${value[1]}"`] : [];
      });
      const rest = masker.token("P", line);
      masked.push(`${indent}${colons}${name}{${rest}${text.join("")}}`);
      continue;
    }

    if (TABLE_ROW.test(line)) {
      let end = index;
      while (end + 1 < lines.length && TABLE_ROW.test(lines[end + 1]!)) {
        end++;
      }
      const rows = lines.slice(index, end + 1);
      const squeezed = rows.map((row) => squeeze(masker.inline(row)));
      tables.push({
        original: rows.join("\n"),
        masked: squeezed.join("\n"),
        indent: line.match(/^\s*/)![0],
      });
      masked.push(...squeezed);
      index = end;
      continue;
    }

    if (HTML_LINE.test(line)) {
      masked.push(masker.token("H", line));
      continue;
    }

    masked.push(masker.inline(line));
  }

  return {
    id,
    source,
    masked: masked.join("\n"),
    tokens: masker.tokens,
    terms: masker.terms,
    headings: found,
    tables,
  };
}

function restoreInline(line: string, section: Section, mode: Mode): string {
  return (
    line
      // A link target is masked with its brackets: `(⟦L1⟧)`.
      .replace(/\((⟦L\d+⟧)\)/g, (match, name: string) => {
        return section.tokens[name] ?? match;
      })
      .replace(/⟦T\d+⟧/g, (name) => {
        const term = section.terms[name];
        if (!term) {
          return name;
        }
        return mode === "identity" ? term.original : `{to="${term.key}"}`;
      })
      .replace(/⟦U\d+⟧/g, (name) => section.tokens[name] ?? name)
  );
}

function unmaskBody(translated: string, section: Section, mode: Mode): string {
  const lines = translated.split("\n");
  const restored: string[] = [];
  let heading = 0;
  let table = 0;

  for (let index = 0; index < lines.length; index++) {
    const line = lines[index]!;

    const block = line.match(/^⟦(CODE|H)\d+⟧$/);
    if (block && section.tokens[line] !== undefined) {
      restored.push(section.tokens[line]!);
      continue;
    }

    const title = line.match(HEADING);
    if (title) {
      const english = section.headings[heading++];
      const text = restoreInline(title[2]!, section, mode);
      const id =
        mode === "identity" ? (english?.suffix ?? "") : ` {#${english?.id}}`;
      restored.push(`${title[1]} ${text}${id}`);
      continue;
    }

    const component = line.match(/^\s*:+[a-z][a-z0-9-]*\{(⟦P\d+⟧)(.*)\}\s*$/);
    if (component && section.tokens[component[1]!] !== undefined) {
      let original = section.tokens[component[1]!]!;
      for (const prop of TEXT_PROPS) {
        const value = component[2]!.match(new RegExp(`\\s${prop}="([^"]*)"`));
        if (value) {
          original = original.replace(
            new RegExp(`([{\\s]${prop}=")[^"]*"`),
            (_match, start: string) => `${start}${value[1]}"`,
          );
        }
      }
      restored.push(original);
      continue;
    }

    if (TABLE_ROW.test(line)) {
      let end = index;
      while (end + 1 < lines.length && TABLE_ROW.test(lines[end + 1]!)) {
        end++;
      }
      const rows = lines.slice(index, end + 1);
      const english = section.tables[table++];

      // An untouched table goes back with the padding it was written with.
      if (english && rows.join("\n") === english.masked) {
        restored.push(english.original);
      } else {
        restored.push(
          ...pad(
            rows.map((row) => restoreInline(row, section, mode)),
            english?.indent ?? "",
          ),
        );
      }
      index = end;
      continue;
    }

    restored.push(restoreInline(line, section, mode));
  }

  return restored.join("\n");
}

type FrontMatterNode = { key: string; node: Scalar };

/** Find the scalar a dotted key like `navigation.title` points at. */
function textNodes(frontMatter: string): FrontMatterNode[] {
  const document = parseDocument(frontMatter.replace(/^---\n|---\n$/g, ""));
  const found: FrontMatterNode[] = [];

  for (const key of FRONT_MATTER_TEXT) {
    const node = document.getIn(key.split("."), true);
    if (isScalar(node) && typeof node.value === "string") {
      found.push({ key, node: node as Scalar });
    }
  }

  return found;
}

function maskFrontMatter(source: string): Omit<Section, "kind"> {
  const lines = textNodes(source).map(({ key, node }) => {
    const value = node.value as string;
    if (value.includes("\n")) {
      throw new Error(
        `Front matter key "${key}" spans several lines, which the pipeline does not translate.`,
      );
    }
    return `${key}: ${value}`;
  });

  return {
    id: "frontmatter",
    source,
    masked: lines.join("\n"),
    tokens: {},
    terms: {},
    headings: [],
    tables: [],
  };
}

/** Read `key: value` lines back into a map. */
export function frontMatterValues(masked: string): Map<string, string> {
  const values = new Map<string, string>();
  for (const line of masked.split("\n")) {
    const match = line.match(/^([a-z_.]+): (.*)$/);
    if (match) {
      values.set(match[1]!, match[2]!.trim());
    }
  }
  return values;
}

function unmaskFrontMatter(translated: string, section: Section): string {
  const values = frontMatterValues(translated);
  const offset = "---\n".length;
  let restored = section.source;

  // Back to front, so an earlier position does not move under a later edit.
  const nodes = textNodes(section.source).sort(
    (a, b) => b.node.range![0] - a.node.range![0],
  );
  for (const { key, node } of nodes) {
    const value = values.get(key);
    if (value === undefined || value === node.value) {
      continue;
    }

    const [start, end] = node.range!;
    const scalar = stringify(value, { lineWidth: 0 }).trimEnd();
    restored =
      restored.slice(0, offset + start) + scalar + restored.slice(offset + end);
  }

  return restored;
}

/** Cut a page into sections and mask each of them. */
export function segment(text: string): Page {
  const { frontMatter, body } = splitFrontMatter(text);
  const ids = headings(body).map((heading) => heading.id);
  const sections: Section[] = [];

  if (frontMatter) {
    if (!isMap(parseDocument(frontMatter.slice(4, -4)).contents)) {
      throw new Error("The front matter is not a YAML mapping.");
    }
    sections.push({ kind: "frontmatter", ...maskFrontMatter(frontMatter) });
  }

  const taken = new Set<string>(["frontmatter"]);
  for (const chunk of chunks(body)) {
    const first = chunk.match(/^#{2,3} /) ? ids[0]! : "intro";

    // A section is named after its anchor. Two sections can only share one
    // when a heading has no letters to make an anchor from.
    let id = first || "section";
    for (let count = 1; taken.has(id); count++) {
      id = `${first || "section"}~${count}`;
    }
    taken.add(id);

    sections.push({ kind: "body", ...maskBody(id, chunk, ids) });
  }

  return { sections };
}

/** Put the real thing back where the tokens are. */
export function unmask(
  translated: string,
  section: Section,
  mode: Mode,
): string {
  return section.kind === "frontmatter"
    ? unmaskFrontMatter(translated, section)
    : unmaskBody(translated, section, mode);
}
