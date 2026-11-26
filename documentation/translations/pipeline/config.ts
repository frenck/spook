/**
 * Where everything lives, and what `languages.yml` says.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const PIPELINE = dirname(fileURLToPath(import.meta.url));

export const TRANSLATIONS = dirname(PIPELINE);
export const DOCUMENTATION = dirname(TRANSLATIONS);
export const REPOSITORY = dirname(DOCUMENTATION);

export const CONTENT = join(DOCUMENTATION, "content");
export const CORPUS = join(TRANSLATIONS, "corpus");
export const OUTPUT = join(TRANSLATIONS, "output");
export const LOCALE = join(DOCUMENTATION, "locales", "en.json");

/** Where a reader, or a contributor, reports a problem with a translation. */
export const REPORT_URL = "https://github.com/frenck/spook/issues/new/choose";

/**
 * The data files with text in them, and which of their keys hold that text.
 * Everything else in these files (icons, links, screenshot names) is kept.
 */
export const DATA_FILES = [/^answers\.yml$/, /^tour\/[^/]+\.yml$/];
export const DATA_TEXT_KEYS = [
  "title",
  "description",
  "headline",
  "question",
  "answer",
  "label",
  "alt",
];

export interface Language {
  code: string;
  name: string;
  /**
   * `planned` has a corpus and nothing else: no command touches it unless it
   * is named with --lang. `off` is a language that was stopped.
   */
  status: "planned" | "pilot" | "live" | "off";
}

export interface Settings {
  /**
   * Raise this to retranslate everything: after a big change to the style
   * guide or the prompt. Small corpus edits only reach new and changed
   * sections.
   */
  corpus_version: number;
  models: {
    translate: string;
    review: string;
    effort: "low" | "medium" | "high" | "xhigh" | "max";
  };
  /** A run that would send more sections than this stops, unless forced. */
  budget_sections: number;
  languages: Language[];
}

export function settings(): Settings {
  return parse(readFileSync(join(CORPUS, "languages.yml"), "utf8")) as Settings;
}

/** The languages a command works on when it is not given --lang. */
export function active(languages: Language[]): Language[] {
  return languages.filter(
    (entry) => entry.status === "pilot" || entry.status === "live",
  );
}

export function language(code: string): Language {
  const found = settings().languages.find((entry) => entry.code === code);
  if (!found) {
    const known = settings()
      .languages.map((entry) => entry.code)
      .join(", ");
    throw new Error(`Unknown language "${code}". languages.yml has: ${known}.`);
  }
  return found;
}

/** Read a corpus file, or nothing when the language does not have it yet. */
export function corpus(...path: string[]): string {
  const file = join(CORPUS, ...path);
  return existsSync(file) ? readFileSync(file, "utf8") : "";
}

/** Every file under a directory, as paths relative to it, sorted. */
export function files(directory: string, extension: string): string[] {
  if (!existsSync(directory)) {
    return [];
  }

  const walk = (current: string): string[] =>
    readdirSync(current).flatMap((name) => {
      const path = join(current, name);
      if (statSync(path).isDirectory()) {
        return walk(path);
      }
      return name.endsWith(extension) ? [relative(directory, path)] : [];
    });

  return walk(directory).sort();
}

/**
 * The English pages, as paths relative to `content/`.
 *
 * The same set as the `docs` collection in `content.config.ts`: the landing
 * page is a page of its own kind, and `data/` holds data, not pages.
 */
export function pages(): string[] {
  return files(CONTENT, ".md").filter(
    (page) => page !== "index.md" && !page.startsWith("data/"),
  );
}

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}
