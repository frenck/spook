/**
 * Put translated sections back into a page, and remember what they came from.
 *
 * Every translated page has a lock file next to it. Per section it holds a
 * hash of everything the translation depends on: the English text, the
 * glossary entries the section uses, the pinned corrections, and the corpus
 * version. Same hash: the bytes already on disk are kept, and no model sees
 * the section. That is what keeps a page from being reworded when one
 * sentence somewhere else changed.
 */
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { parse } from "yaml";

import {
  CONTENT,
  corpus,
  OUTPUT,
  REPORT_URL,
  settings,
  today,
} from "./config.ts";
import { closeEmphasis } from "./emphasis.ts";
import { glossary, used } from "./glossary.ts";
import type { Glossary, Used } from "./glossary.ts";
import { segment, unmask } from "./segment.ts";
import { typeset, typographyFor } from "./typography.ts";
import type { Section } from "./segment.ts";
import { changedUnknown, verifyPage, verifySection } from "./verify.ts";
import type { Rules } from "./verify.ts";

export interface LockEntry {
  id: string;
  /** Hash of all the translation depends on. Empty when not translated. */
  hash: string;
  /** Hash of the English section alone. */
  source: string;
  /** The glossary entries the section used, English to translation. */
  glossary: Record<string, string>;
  /** The model that wrote it, or how it was made when no model did. */
  model: string;
  date: string;
}

export interface Lock {
  "//": string;
  source: string;
  language: string;
  sections: LockEntry[];
}

interface Correction {
  page: string;
  section?: string;
  source: string;
  translation: string;
}

export interface Planned {
  section: Section;
  hash: string;
  used: Used;
  rules: Rules;
  /** The bytes on disk, when the section is translated and unchanged. */
  kept?: string;
  entry?: LockEntry;
  /**
   * The translation on disk and its lock entry, also when it is behind the
   * English. Without a notice, for the front matter.
   *
   * `reusable` when it is still a translation of this section as it is now:
   * unchanged, or behind only because glossary entries it used went away.
   * Anything else (other English, a glossary word that changed, a new
   * correction, a new corpus version) needs a translator.
   *
   * `sameEnglish` when the English is what it was, whatever happened to the
   * glossary. A start for a translator who edits the words, see
   * `export --from-output`, not something to write back as it is.
   */
  previous?: {
    text: string;
    entry: LockEntry;
    reusable: boolean;
    sameEnglish: boolean;
  };
}

export interface Plan {
  lang: string;
  page: string;
  english: string;
  sections: Planned[];
  /** Every label translation of the glossary: typography leaves them alone. */
  labels: string[];
}

export interface Translation {
  /** The translated section, still masked. */
  masked: string;
  model: string;
}

export interface Result {
  /** The page as it is, or would be, written. */
  text: string;
  /** Its lock file, as it is, or would be, written. */
  lock: Lock;
  written: boolean;
  errors: string[];
  /** Bold strings without a glossary entry, and whether they stayed. */
  unknown: { label: string; kept: boolean }[];
  untranslated: string[];
}

function sha(...parts: unknown[]): string {
  return createHash("sha256")
    .update(JSON.stringify(parts))
    .digest("hex")
    .slice(0, 16);
}

export function outputPath(lang: string, page: string): string {
  return join(OUTPUT, lang, "content", page);
}

export function lockPath(lang: string, page: string): string {
  return outputPath(lang, page).replace(/\.md$/, ".lock.json");
}

function readLock(lang: string, page: string): Lock | undefined {
  const path = lockPath(lang, page);
  return existsSync(path)
    ? (JSON.parse(readFileSync(path, "utf8")) as Lock)
    : undefined;
}

/** The lines every generated file opens with. */
export function notice(source: string): string[] {
  return [
    "GENERATED FILE. Do not edit: the next translation run overwrites it.",
    `Translated by a machine from ${source}.`,
    "Something wrong? Report it, and it is fixed in what the machine works from:",
    `${REPORT_URL} (see documentation/translations/corpus/README.md).`,
  ];
}

// The notice is four comment lines. Comments of the English page come after.
const NOTICE = /^---\n(# .*\n){4}/;

/** The rules a translation of this language has to keep. */
export function rulesFor(lang: string): Omit<Rules, "labels" | "corrections"> {
  const doNotTranslate = (parse(corpus("do-not-translate.yml")) ?? {}) as {
    keep?: string[];
    never?: Record<string, string[]>;
  };
  const jokes = (parse(corpus(lang, "jokes.yml")) ?? {}) as {
    hashtags?: Record<string, string>;
  };

  return {
    keep: doNotTranslate.keep ?? [],
    never: [
      ...(doNotTranslate.never?.all ?? []),
      ...(doNotTranslate.never?.[lang] ?? []),
    ],
    hashtags: jokes.hashtags ?? {},
  };
}

function corrections(lang: string): Correction[] {
  const file = (parse(corpus(lang, "corrections.yml")) ?? {}) as {
    corrections?: Correction[];
  };
  return file.corrections ?? [];
}

/** Work out, per section of a page, whether it has to be translated. */
export function plan(lang: string, page: string, terms?: Glossary): Plan {
  const english = readFileSync(join(CONTENT, page), "utf8");
  const from = terms ?? glossary(lang);
  const shared = rulesFor(lang);
  const pinned = corrections(lang).filter((entry) => entry.page === page);
  const version = settings().corpus_version;

  const lock = readLock(lang, page);
  const existing = existsSync(outputPath(lang, page))
    ? new Map(
        segment(readFileSync(outputPath(lang, page), "utf8")).sections.map(
          (section) => [section.id, section.source],
        ),
      )
    : new Map<string, string>();

  const sections = segment(english).sections.map((section): Planned => {
    const uses = used(section.masked, from);
    const applies = pinned.filter(
      (entry) =>
        (!entry.section || entry.section === section.id) &&
        section.source.includes(entry.source),
    );
    const hash = sha(section.source, uses.labels, uses.terms, applies, version);

    const entry = lock?.sections.find((found) => found.id === section.id);
    const onDisk = existing.get(section.id);
    const kept =
      section.kind === "frontmatter"
        ? onDisk?.replace(NOTICE, "---\n")
        : onDisk;
    const unchanged = entry?.hash === hash && kept !== undefined;

    // Whether the hash this section had is that of the same English with
    // the glossary entries it had back then: only the glossary changed.
    const sameEnglish = (): boolean => {
      const old = Object.entries(entry?.glossary ?? {});

      // A removed label would land with the terms, and the hash would not
      // match: that only errs on the side of translating again.
      const bold = new Set(Object.keys(uses.labels));
      const labels = Object.fromEntries(old.filter(([key]) => bold.has(key)));
      const terms = Object.fromEntries(old.filter(([key]) => !bold.has(key)));
      return (
        entry?.hash === sha(section.source, labels, terms, applies, version)
      );
    };

    // All that happened is that glossary entries it used were removed: the
    // same words, minus the missing ones.
    const removedOnly = (): boolean => {
      const now = { ...uses.labels, ...uses.terms };
      return (
        Object.entries(now).every(
          ([key, value]) => entry?.glossary[key] === value,
        ) && sameEnglish()
      );
    };

    return {
      section,
      hash,
      used: uses,
      rules: {
        ...shared,
        labels: uses.labels,
        corrections: applies.map((entry) => entry.translation),
      },
      ...(unchanged ? { kept, entry } : {}),
      ...(entry?.hash && kept !== undefined
        ? {
            previous: {
              text: kept,
              entry,
              reusable: unchanged || removedOnly(),
              sameEnglish: unchanged || sameEnglish(),
            },
          }
        : {}),
    };
  });

  return {
    lang,
    page,
    english,
    sections,
    labels: Object.values(from.labels).map((label) => label.translation),
  };
}

/**
 * Build the translated page from kept and new sections, check it, write it.
 *
 * A section without a translation goes in as English, so the page has every
 * anchor either way, and is picked up again by the next run.
 */
export function assemble(
  planned: Plan,
  translations: Map<string, Translation>,
  options: { write: boolean },
): Result {
  const source = `documentation/content/${planned.page}`;
  const errors: string[] = [];
  const unknown: Result["unknown"] = [];
  const untranslated: string[] = [];
  const parts: string[] = [];
  const entries: LockEntry[] = [];

  const typography = typographyFor(planned.lang);

  for (const {
    section,
    hash,
    used: uses,
    rules,
    kept,
    entry,
    previous,
  } of planned.sections) {
    const translation = translations.get(section.id);
    let text: string;

    if (translation) {
      // Emphasis first: typography puts a space before a colon that this
      // may just have moved out of a bold span.
      const masked = typeset(
        closeEmphasis(translation.masked, section.kind, planned.labels),
        section.kind,
        typography,
        section.source,
        planned.labels,
      );
      const problems = verifySection(section, masked, rules);
      errors.push(...problems.map((problem) => `[${section.id}] ${problem}`));

      const changed = changedUnknown(section, masked, uses.unknown);
      unknown.push(
        ...uses.unknown.map((label) => ({
          label,
          kept: !changed.includes(label),
        })),
      );

      text = unmask(masked, section, "translated");

      // The words on disk, handed back as they were: whoever wrote them still
      // did, and when. The spaces typography puts in do not make it new.
      const same =
        previous !== undefined &&
        unmask(translation.masked, section, "translated") === previous.text;
      entries.push({
        id: section.id,
        hash,
        source: sha(section.source),
        glossary: { ...uses.labels, ...uses.terms },
        model: same ? previous.entry.model : translation.model,
        date: same ? previous.entry.date : today(),
      });
    } else if (kept !== undefined && entry) {
      text = kept;
      entries.push(entry);
    } else {
      untranslated.push(section.id);
      text = unmask(section.masked, section, "translated");
      entries.push({
        id: section.id,
        hash: "",
        source: sha(section.source),
        glossary: {},
        model: "none: still English",
        date: today(),
      });
    }

    if (section.kind === "frontmatter") {
      const comment = notice(source)
        .map((line) => `# ${line}\n`)
        .join("");
      text = text.replace(/^---\n/, `---\n${comment}`);
    }
    parts.push(text);
  }

  const text = parts.join("");
  if (!errors.length) {
    errors.push(...verifyPage(planned.english, text));
  }

  const lock: Lock = {
    "//": notice(source).join(" "),
    source,
    language: planned.lang,
    sections: entries,
  };

  const written = options.write && !errors.length;
  if (written) {
    const path = outputPath(planned.lang, planned.page);
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, text);
    writeFileSync(
      lockPath(planned.lang, planned.page),
      `${JSON.stringify(lock, null, 2)}\n`,
    );
  }

  return { text, lock, written, errors, unknown, untranslated };
}
