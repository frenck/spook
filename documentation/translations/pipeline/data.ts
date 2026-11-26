/**
 * Translate the text in data files: the YAML behind the tour and the straight
 * answers, and the site's own interface strings in `locales/en.json`.
 *
 * These are loose strings, not pages. Each one is its own unit: it has its
 * own hash in the lock file, and one that did not change is copied from the
 * file on disk. Everything that is not text (icons, links, screenshot names,
 * the shape of the file) is carried over from the English file as it is.
 */
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { parse, parseDocument } from "yaml";

import {
  CONTENT,
  DATA_FILES,
  DATA_TEXT_KEYS,
  files,
  LOCALE,
  OUTPUT,
  settings,
  today,
} from "./config.ts";
import { notice, rulesFor } from "./assemble.ts";
import { typeset, typographyFor } from "./typography.ts";

type Path = (string | number)[];

export interface DataString {
  /** Where it is in the file, like `groups.0.questions.2.answer`. */
  id: string;
  path: Path;
  english: string;
  hash: string;
  /** The translation on disk, when the English did not change. */
  kept?: string;
}

export interface DataPlan {
  lang: string;
  /** `locale`, or a path under `content/data/` like `tour/repairs.yml`. */
  unit: string;
  source: string;
  english: string;
  strings: DataString[];
}

interface DataLock {
  "//": string;
  source: string;
  language: string;
  strings: Record<string, { hash: string; model: string; date: string }>;
}

const EMOJI = /\p{Extended_Pictographic}/gu;
const PLACEHOLDER = /\{[^}]*\}|@:[\w.]+/g;

/** The data files that get translated, next to the pages. */
export function dataUnits(): string[] {
  const data = files(join(CONTENT, "data"), ".yml").filter((file) =>
    DATA_FILES.some((pattern) => pattern.test(file)),
  );
  return [...data, ...(existsSync(LOCALE) ? ["locale"] : [])];
}

function sourceOf(unit: string): string {
  return unit === "locale" ? LOCALE : join(CONTENT, "data", unit);
}

function outputOf(lang: string, unit: string): string {
  return unit === "locale"
    ? join(OUTPUT, lang, "locale.json")
    : join(OUTPUT, lang, "data", unit);
}

function lockOf(lang: string, unit: string): string {
  return outputOf(lang, unit).replace(/\.(json|yml)$/, ".lock.json");
}

function walk(
  value: unknown,
  path: Path,
  textOnly: boolean,
  into: Path[],
): void {
  if (typeof value === "string") {
    const key = path.at(-1);
    if (!textOnly || DATA_TEXT_KEYS.includes(String(key))) {
      into.push(path);
    }
  } else if (Array.isArray(value)) {
    value.forEach((child, index) =>
      walk(child, [...path, index], textOnly, into),
    );
  } else if (value && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      if (key !== "//") {
        walk(child, [...path, key], textOnly, into);
      }
    }
  }
}

function at(data: unknown, path: Path): unknown {
  return path.reduce<unknown>(
    (current, key) =>
      current && typeof current === "object"
        ? (current as Record<string | number, unknown>)[key]
        : undefined,
    data,
  );
}

function read(file: string): unknown {
  const text = readFileSync(file, "utf8");
  return file.endsWith(".json") ? JSON.parse(text) : parse(text);
}

function sha(...parts: unknown[]): string {
  return createHash("sha256")
    .update(JSON.stringify(parts))
    .digest("hex")
    .slice(0, 16);
}

/** Work out which strings of a data file have to be translated. */
export function planData(lang: string, unit: string): DataPlan {
  const source = sourceOf(unit);
  const english = readFileSync(source, "utf8");
  const data = read(source);

  const output = outputOf(lang, unit);
  const translated = existsSync(output) ? read(output) : undefined;
  const lock = existsSync(lockOf(lang, unit))
    ? (JSON.parse(readFileSync(lockOf(lang, unit), "utf8")) as DataLock)
    : undefined;

  const paths: Path[] = [];
  walk(data, [], unit !== "locale", paths);

  const version = settings().corpus_version;
  const strings = paths.map((path): DataString => {
    const id = path.join(".");
    const value = at(data, path) as string;
    const hash = sha(value, version);
    const kept = at(translated, path);
    const unchanged =
      lock?.strings[id]?.hash === hash && typeof kept === "string";
    return { id, path, english: value, hash, ...(unchanged ? { kept } : {}) };
  });

  return { lang, unit, source, english, strings };
}

/** The strings that need a translation, one per line behind a token. */
export function maskData(plan: DataPlan): string {
  return plan.strings
    .flatMap((string, index) =>
      string.kept === undefined
        ? [`⟦S${index + 1}⟧ ${string.english.replaceAll("\n", " ⏎ ")}`]
        : [],
    )
    .join("\n");
}

/** Read translated lines back, by their token. */
export function unmaskData(
  plan: DataPlan,
  masked: string,
): Map<string, string> {
  const found = new Map<string, string>();
  for (const line of masked.split("\n")) {
    const match = line.match(/^⟦S(\d+)⟧ (.*)$/);
    const string = match && plan.strings[Number(match[1]) - 1];
    if (string) {
      found.set(string.id, match[2]!.trim().replaceAll(" ⏎ ", "\n"));
    }
  }
  return found;
}

function verifyString(
  english: string,
  translated: string,
  never: string[],
  keep: string[],
): string[] {
  const errors: string[] = [];
  const same = (pattern: RegExp) =>
    (english.match(pattern) ?? []).sort().join(" ") ===
    (translated.match(pattern) ?? []).sort().join(" ");

  if (!translated) {
    errors.push("is empty");
  }
  if (!same(PLACEHOLDER)) {
    errors.push("placeholders differ from the English");
  }
  if (!same(EMOJI)) {
    errors.push("emoji differ from the English");
  }
  if (/[⟦⟧]/.test(translated)) {
    errors.push("a mask token is left in it");
  }
  if (
    (english.match(/\|/g) ?? []).length !==
    (translated.match(/\|/g) ?? []).length
  ) {
    errors.push("the number of plural forms differs");
  }
  for (const name of keep) {
    if (english.includes(name) && !translated.includes(name)) {
      errors.push(`"${name}" is gone, it is never translated`);
    }
  }
  for (const pattern of never) {
    const expression = new RegExp(pattern, "u");
    const hit = translated.match(expression);
    if (hit && !expression.test(english)) {
      errors.push(`"${hit[0]}" is not allowed here (rule: ${pattern})`);
    }
  }

  return errors;
}

export interface DataResult {
  written: boolean;
  errors: string[];
  untranslated: string[];
}

/** Write the translated data file, with the strings that pass the checks. */
export function assembleData(
  plan: DataPlan,
  translations: Map<string, string>,
  model: string,
  options: { write: boolean },
): DataResult {
  const { never, keep } = rulesFor(plan.lang);
  const typography = typographyFor(plan.lang);
  const errors: string[] = [];
  const untranslated: string[] = [];
  const lock: DataLock["strings"] = {};
  const previous = existsSync(lockOf(plan.lang, plan.unit))
    ? (JSON.parse(
        readFileSync(lockOf(plan.lang, plan.unit), "utf8"),
      ) as DataLock)
    : undefined;

  const values = new Map<string, string>();
  for (const string of plan.strings) {
    const offered = translations.get(string.id);
    if (offered !== undefined) {
      const translation = typeset(offered, "body", typography, string.english);
      const problems = verifyString(string.english, translation, never, keep);
      errors.push(...problems.map((problem) => `[${string.id}] ${problem}`));
      values.set(string.id, translation);
      lock[string.id] = { hash: string.hash, model, date: today() };
    } else if (string.kept !== undefined) {
      values.set(string.id, string.kept);
      lock[string.id] = previous!.strings[string.id]!;
    } else {
      untranslated.push(string.id);
    }
  }

  const written = options.write && !errors.length;
  if (!written) {
    return { written, errors, untranslated };
  }

  const source =
    plan.unit === "locale"
      ? "documentation/locales/en.json"
      : `documentation/content/data/${plan.unit}`;
  const output = outputOf(plan.lang, plan.unit);
  mkdirSync(dirname(output), { recursive: true });

  if (plan.unit === "locale") {
    const data = JSON.parse(plan.english) as Record<string, unknown>;
    for (const string of plan.strings) {
      const parent = at(data, string.path.slice(0, -1)) as Record<
        string,
        unknown
      >;
      parent[string.path.at(-1)!] = values.get(string.id) ?? string.english;
    }
    writeFileSync(
      output,
      `${JSON.stringify({ "//": notice(source).join(" "), ...data }, null, 2)}\n`,
    );
  } else {
    const document = parseDocument(plan.english);
    for (const string of plan.strings) {
      document.setIn(string.path, values.get(string.id) ?? string.english);
    }
    const comment = notice(source)
      .map((line) => `# ${line}\n`)
      .join("");
    writeFileSync(output, `${comment}\n${document.toString({ lineWidth: 0 })}`);
  }

  const file: DataLock = {
    "//": notice(source).join(" "),
    source,
    language: plan.lang,
    strings: lock,
  };
  writeFileSync(
    lockOf(plan.lang, plan.unit),
    `${JSON.stringify(file, null, 2)}\n`,
  );

  return { written, errors, untranslated };
}
