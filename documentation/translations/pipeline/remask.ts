/**
 * Turn a translated page back into what the translator worked on.
 *
 * `export --from-output` uses this: the work files come out with the current
 * translation in them, masked with the tokens of the English section, so a
 * person can change a word in twenty sections and `import` them, without
 * translating anything again. `normalize` uses it to run every section of a
 * page through the assembler once more, after a typography rule changed.
 *
 * The translated page is masked on its own, so its tokens are numbered in
 * the order the translation has them. Each one is matched to the English
 * token that stands for the same thing: the same link, code block or term,
 * or the same component with other text in its props. Then the result is
 * unmasked against the English section, and has to give the bytes that are
 * on disk. When it does not, nothing is handed out.
 */
import { readFileSync } from "node:fs";

import { outputPath } from "./assemble.ts";
import type { Plan } from "./assemble.ts";
import { segment, TEXT_PROPS, TOKEN, unmask } from "./segment.ts";
import type { Section } from "./segment.ts";

// The notice a generated page opens with, which the English does not have.
const NOTICE = /^---\n(# .*\n){4}/;

const MARKER = /^@@@ section (\S+) @@@$/;

/** What a token stands for, the same in the English and the translation. */
function identity(section: Section, name: string, kind: string): string {
  if (kind === "T") {
    return `T|${section.terms[name]?.key}`;
  }

  // A component line has translated text in its props: leave that out.
  if (kind === "P") {
    const props = new RegExp(`([{\\s](${TEXT_PROPS.join("|")}))="[^"]*"`, "g");
    return `P|${section.tokens[name]?.replace(props, '$1=""')}`;
  }

  return `${kind}|${section.tokens[name]}`;
}

/** The masked text of one translated section, with the English tokens. */
export function remaskSection(english: Section, translated: Section): string {
  const expected =
    english.kind === "frontmatter"
      ? translated.source.replace(NOTICE, "---\n")
      : translated.source;

  let masked = translated.masked;
  if (english.kind === "body") {
    // The English tokens, queued per thing they stand for. The same link
    // twice in a section is two tokens with the same identity.
    const queues = new Map<string, string[]>();
    for (const [name, kind] of english.masked.matchAll(TOKEN)) {
      const key = identity(english, name, kind!);
      queues.set(key, [...(queues.get(key) ?? []), name]);
    }

    masked = translated.masked.replace(TOKEN, (name, kind: string) => {
      const match = queues.get(identity(translated, name, kind))?.shift();
      if (!match) {
        throw new Error(
          `[${english.id}] the translation has ${name}, and the English section has nothing it matches.`,
        );
      }
      return match;
    });
  }

  if (unmask(masked, english, "translated") !== expected) {
    throw new Error(
      `[${english.id}] the translation on disk does not come back the same once masked.`,
    );
  }

  return masked;
}

/**
 * The masked translation of a page, per section, from what is on disk.
 *
 * `only` names the sections to hand out; without it, every section that
 * has a translation. A section that is still English has none.
 *
 * `forEditing` also hands out a section that is behind only because the
 * glossary changed: the words are what a translator edits, and the import
 * writes the section against the glossary as it is now.
 */
export function remask(
  planned: Plan,
  only?: string[],
  { forEditing = false } = {},
): Map<string, string> {
  const path = outputPath(planned.lang, planned.page);
  const translated = new Map(
    segment(readFileSync(path, "utf8")).sections.map((section) => [
      section.id,
      section,
    ]),
  );

  const masked = new Map<string, string>();
  for (const { section, previous } of planned.sections) {
    if (only && !only.includes(section.id)) {
      continue;
    }

    // Still English, or a translation of something else than the section is
    // now: handing that out would bring an old translation back as new.
    const onDisk = translated.get(section.id);
    const usable = forEditing ? previous?.sameEnglish : previous?.reusable;
    if (!onDisk || !usable) {
      if (only) {
        throw new Error(
          `${planned.page} [${section.id}] has no translation of the current English and corpus to start from.`,
        );
      }
      continue;
    }

    masked.set(section.id, remaskSection(section, onDisk));
  }

  for (const id of only ?? []) {
    if (!planned.sections.some(({ section }) => section.id === id)) {
      throw new Error(`${planned.page} has no section "${id}".`);
    }
  }

  return masked;
}

/** The work file a translator gets: every section after its marker. */
export function writeBundle(sections: Map<string, string>): string {
  return [...sections]
    .map(([id, masked]) => `@@@ section ${id} @@@\n${masked}\n`)
    .join("");
}

/** Keep the blank lines around a section the way the English has them. */
export function fit(translated: string, english: string): string {
  const leading = english.match(/^\n*/)![0];
  const trailing = english.match(/\n*$/)![0];
  return leading + translated.replace(/^\n+|\n+$/g, "") + trailing;
}

/** Read a work file back: the masked text per section, fitted to the page. */
export function readBundle(bundle: string, planned: Plan): Map<string, string> {
  const sections = new Map<string, string>();
  let current: string | undefined;
  let lines: string[] = [];

  const close = () => {
    if (!current) {
      return;
    }

    const section = planned.sections.find(
      (entry) => entry.section.id === current,
    );
    if (!section) {
      throw new Error(
        `The translation has a section "${current}" the page does not have.`,
      );
    }
    sections.set(current, fit(lines.join("\n"), section.section.masked));
  };

  for (const line of bundle.split("\n")) {
    const marker = line.match(MARKER);
    if (marker) {
      close();
      current = marker[1]!;
      lines = [];
    } else {
      lines.push(line);
    }
  }
  close();

  return sections;
}
