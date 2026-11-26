/**
 * The glossary: which words a translation has to use.
 *
 * The docs put what Home Assistant shows on screen in bold, like
 * `**Add action**`. A reader has to find that exact label in their own
 * language, so a translator does not get to pick a word for it. This looks
 * every bold string up in the strings Spook and Home Assistant ship, and
 * writes down the one label the product shows.
 *
 * Two files per language come together here:
 * - `glossary.generated.yml`, built by `build` below. Never edited.
 * - `glossary.yml`, by hand: prose terms, and overrides with a reason.
 */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { parse, stringify } from "yaml";

import { CONTENT, corpus, files, pages, REPOSITORY } from "./config.ts";
import { segment } from "./segment.ts";

type Origin = "spook" | "frontend" | "core" | "composite" | "override";

export interface Label {
  translation: string;
  source: Origin;
  key?: string;
  /** Other translations Home Assistant has for the same English string. */
  alternatives?: string[];
  reason?: string;
}

export interface Glossary {
  labels: Record<string, Label>;
  terms: Record<string, string>;
}

export interface Unmatched {
  label: string;
  uses: number;
  first: string;
}

interface Entry {
  origin: Origin;
  key: string;
  english: string;
  translation: string;
}

const GHOST = " 👻";

/**
 * The name of one of Spook's actions as Home Assistant shows it: with the
 * ghost. Spook adds it only where the translation does not have one already,
 * and some translators put it in themselves (Chinese does, in every name).
 */
function withGhost(name: string, ghost: string | undefined): string {
  return ghost && !name.includes(GHOST.trim()) ? `${name}${GHOST}` : name;
}
const INLINE_CODE = /(`+)(?!`)(.*?[^`])\1(?!`)/g;
const BOLD = /\*\*([^*\n]+)\*\*/g;

/** Every bold string in a piece of masked prose. */
export function bold(masked: string): string[] {
  const prose = masked.replace(INLINE_CODE, "");
  return [...prose.matchAll(BOLD)].map((match) => match[1]!.trim());
}

/**
 * Bold that ends a thought is emphasis, not a label: `**How to fix it:**`.
 * No button ends in a colon or a full stop.
 */
export function isEmphasis(text: string): boolean {
  return /[:.!?]$/.test(text) || /^[^\p{L}\p{N}+]/u.test(text);
}

function flatten(
  value: unknown,
  prefix: string,
  into: Map<string, string>,
): Map<string, string> {
  if (typeof value === "string") {
    into.set(prefix, value);
  } else if (value && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      flatten(child, prefix ? `${prefix}.${key}` : key, into);
    }
  }
  return into;
}

function strings(file: string, prefix: string): Map<string, string> {
  return flatten(JSON.parse(readFileSync(file, "utf8")), prefix, new Map());
}

function pair(
  origin: Origin,
  english: Map<string, string>,
  translated: Map<string, string>,
): Entry[] {
  const entries: Entry[] = [];
  for (const [key, value] of english) {
    const translation = translated.get(key);
    if (translation) {
      entries.push({ origin, key, english: value, translation });
    }
  }
  return entries;
}

/** Where Home Assistant's own strings are, if they are on this machine. */
export function findHomeAssistant(given?: string): string | undefined {
  const candidates = [given, process.env.SPOOK_HA_STRINGS];

  const lib = join(REPOSITORY, ".venv", "lib");
  if (existsSync(lib)) {
    for (const python of readdirSync(lib)) {
      candidates.push(join(lib, python, "site-packages"));
    }
  }

  return candidates.find(
    (candidate) =>
      candidate && existsSync(join(candidate, "homeassistant", "components")),
  );
}

function homeAssistantVersion(root: string): string {
  const file = join(root, "homeassistant", "const.py");
  if (!existsSync(file)) {
    return "unknown";
  }

  const text = readFileSync(file, "utf8");
  const part = (name: string) =>
    text.match(
      new RegExp(`^${name}_VERSION: Final = "?([^"\\n]+)"?`, "m"),
    )?.[1];
  return `${part("MAJOR")}.${part("MINOR")}.${part("PATCH")}`;
}

interface Sources {
  entries: Entry[];
  description: Record<string, string>;
}

function load(lang: string, homeAssistant?: string): Sources {
  const entries: Entry[] = [];
  const description: Record<string, string> = {};

  // Spook itself, and the helpers it ships as integrations of their own.
  const components = join(REPOSITORY, "custom_components");
  const spook = files(components, "en.json").filter((file) =>
    file.includes("translations"),
  );
  for (const file of spook) {
    const translated = join(components, dirname(file), `${lang}.json`);
    if (existsSync(translated)) {
      const prefix = file.split("/").at(-3)!;
      entries.push(
        ...pair(
          "spook",
          strings(join(components, file), prefix),
          strings(translated, prefix),
        ),
      );
    }
  }
  description.spook = "custom_components/**/translations";

  if (!homeAssistant) {
    description.home_assistant = "not found";
    return { entries, description };
  }

  description.home_assistant = homeAssistantVersion(homeAssistant);

  const core = join(homeAssistant, "homeassistant", "components");
  for (const domain of readdirSync(core).sort()) {
    const english = join(core, domain, "translations", "en.json");
    const translated = join(core, domain, "translations", `${lang}.json`);
    if (existsSync(english) && existsSync(translated)) {
      const prefix = `component.${domain}`;
      entries.push(
        ...pair("core", strings(english, prefix), strings(translated, prefix)),
      );
    }
  }

  // The frontend ships its strings in pieces, one directory per panel.
  const frontend = join(
    homeAssistant,
    "hass_frontend",
    "static",
    "translations",
  );
  const pieces = files(frontend, ".json").filter((file) =>
    /(^|\/)en-[0-9a-f]{32}\.json$/.test(file),
  );
  for (const piece of pieces) {
    const directory = join(frontend, dirname(piece));
    const translated = readdirSync(directory).find((name) =>
      new RegExp(`^${lang}-[0-9a-f]{32}\\.json$`).test(name),
    );
    if (translated) {
      entries.push(
        ...pair(
          "frontend",
          strings(join(frontend, piece), ""),
          strings(join(directory, translated), ""),
        ),
      );
    }
  }
  description.frontend = pieces.length ? "included" : "not found";

  return { entries, description };
}

/** Pick the translation Home Assistant uses most for an English string. */
function pick(hits: Entry[]): Label {
  const counts = new Map<string, number>();
  for (const hit of hits) {
    counts.set(hit.translation, (counts.get(hit.translation) ?? 0) + 1);
  }

  // `ui.common.*` is what Home Assistant itself reuses everywhere, so it
  // wins. After that the most used one, and the key decides a tie.
  const ranked = [...hits].sort(
    (a, b) =>
      Number(b.key.startsWith("ui.common.")) -
        Number(a.key.startsWith("ui.common.")) ||
      counts.get(b.translation)! - counts.get(a.translation)! ||
      a.key.localeCompare(b.key),
  );

  const best = ranked[0]!;
  const alternatives = [...counts.keys()].filter(
    (translation) => translation !== best.translation,
  );
  return {
    translation: best.translation,
    source: best.origin,
    key: best.key,
    ...(alternatives.length ? { alternatives: alternatives.sort() } : {}),
  };
}

function lookup(label: string, entries: Entry[]): Label | undefined {
  for (const origin of ["spook", "frontend", "core"] as const) {
    const hits = entries.filter(
      (entry) => entry.origin === origin && entry.english === label,
    );
    if (hits.length) {
      return pick(hits);
    }
  }

  // The docs write the plus of a button with it: `+ Add integration`.
  if (label.startsWith("+ ")) {
    const found = lookup(label.slice(2), entries);
    return found && { ...found, translation: `+ ${found.translation}` };
  }

  // The start of a repair title, like `Unknown entities used in`, where
  // Spook's own string goes on with `: {automation}`.
  const repairTitles = entries.filter(
    (entry) =>
      entry.origin === "spook" &&
      /^: \{[a-z_]+\}$/.test(entry.english.slice(label.length)) &&
      entry.english.startsWith(label) &&
      /: \{[a-z_]+\}$/.test(entry.translation),
  );
  // French puts a (non-breaking) space before the colon: `dans : {automation}`.
  // That space belongs to the colon, not to the title.
  const starts = new Set(
    repairTitles.map((entry) =>
      entry.translation.replace(/\s*: \{[a-z_]+\}$/, ""),
    ),
  );
  if (starts.size === 1) {
    return {
      translation: [...starts][0]!,
      source: "spook",
      key: repairTitles[0]!.key,
    };
  }

  // An action shows as `Automation: Snooze 👻`: the name of the integration,
  // the name of the action, and the ghost Spook adds to its own.
  const composite = label.match(/^([^:]+): (.+?)( 👻)?$/);
  if (!composite) {
    return undefined;
  }

  const [, integration, action, ghost] = composite;
  const titles = entries.filter(
    (entry) =>
      entry.origin === "core" &&
      /^component\.[^.]+\.title$/.test(entry.key) &&
      entry.english === integration,
  );
  if (!titles.length) {
    return untranslatedIntegration(integration!, action!, ghost, entries);
  }

  const title = pick(titles);
  const domain = title.key!.split(".")[1]!;
  const names = entries.filter(
    (entry) =>
      entry.english === action &&
      (ghost
        ? entry.origin === "spook" &&
          new RegExp(`\\.services\\.${domain}_[^.]+\\.name$`).test(entry.key)
        : new RegExp(`^component\\.${domain}\\.services\\.[^.]+\\.name$`).test(
            entry.key,
          )),
  );
  if (!names.length) {
    return undefined;
  }

  const name = pick(names);
  return {
    translation: `${title.translation}: ${withGhost(name.translation, ghost)}`,
    source: "composite",
    key: `${title.key} + ${name.key}`,
  };
}

/**
 * An action of an integration that has no translated title, like
 * `Home Assistant Core Integration: Create a floor 👻`. Home Assistant shows
 * the name from the integration's manifest there, in English in every
 * language, followed by the translated name of the action:
 * `Home Assistant Core Integration: Maak een verdieping 👻`.
 *
 * Only for Spook's own actions (with the ghost), and only when the name of
 * the action has one translation: without the domain from a title, a name
 * that two integrations share would be a guess.
 */
function untranslatedIntegration(
  integration: string,
  action: string,
  ghost: string | undefined,
  entries: Entry[],
): Label | undefined {
  if (!ghost) {
    return undefined;
  }

  const names = entries.filter(
    (entry) =>
      entry.origin === "spook" &&
      entry.english === action &&
      /\.services\.[^.]+\.name$/.test(entry.key),
  );
  const translations = new Set(names.map((entry) => entry.translation));
  if (translations.size !== 1) {
    return undefined;
  }

  return {
    translation: `${integration}: ${withGhost([...translations][0]!, GHOST)}`,
    source: "composite",
    key: names[0]!.key,
  };
}

/** Every bold string in the English docs, with how often and where first. */
function labelsInDocs(): Map<string, { uses: number; first: string }> {
  const found = new Map<string, { uses: number; first: string }>();
  for (const page of pages()) {
    const text = readFileSync(join(CONTENT, page), "utf8");
    for (const section of segment(text).sections) {
      for (const label of bold(section.masked)) {
        if (isEmphasis(label)) {
          continue;
        }
        const seen = found.get(label) ?? { uses: 0, first: page };
        seen.uses++;
        found.set(label, seen);
      }
    }
  }
  return found;
}

export interface Built {
  yaml: string;
  labels: Record<string, Label>;
  unmatched: Unmatched[];
  sources: Record<string, string>;
}

/** Build `glossary.generated.yml` for one language. */
export function build(lang: string, homeAssistant?: string): Built {
  const sources = load(lang, findHomeAssistant(homeAssistant));
  const labels: Record<string, Label> = {};
  const unmatched: Unmatched[] = [];

  const pins =
    (
      (parse(corpus(lang, "glossary.yml")) ?? {}) as {
        labels?: Record<string, { key?: string; reason?: string }>;
      }
    ).labels ?? {};

  const inDocs = [...labelsInDocs()].sort(([a], [b]) => a.localeCompare(b));
  for (const [label, { uses, first }] of inDocs) {
    // glossary.yml can pin a label to the one string it is on screen, for
    // when the same English word is translated differently per screen.
    const pin = pins[label];
    const pinned = sources.entries.find((entry) => entry.key === pin?.key);
    const found = pinned
      ? {
          translation: pinned.translation,
          source: pinned.origin,
          key: pinned.key,
          reason: pin!.reason,
        }
      : lookup(label, sources.entries);
    if (found) {
      labels[label] = found;
    } else {
      unmatched.push({ label, uses, first });
    }
  }

  const header = [
    "# GENERATED by `npm run translate -- glossary`. Do not edit this file.",
    "#",
    "# Every bold string in the English docs, looked up in the strings Spook and",
    "# Home Assistant ship. A label that is wrong here is wrong in the product,",
    "# or picked from the wrong place: override it in glossary.yml, with a reason.",
    "#",
    "# `unmatched` are bold strings nothing shows under that exact name. Most are",
    "# emphasis. The rest are labels the English docs got wrong, or a button that",
    "# is not translated yet. They stay English in a translation.",
    "",
  ].join("\n");

  const yaml =
    header +
    stringify(
      { language: lang, sources: sources.description, labels, unmatched },
      { lineWidth: 0 },
    );

  return { yaml, labels, unmatched, sources: sources.description };
}

/** The glossary a translation of this language works from. */
export function glossary(lang: string): Glossary {
  const generated = (parse(corpus(lang, "glossary.generated.yml")) ?? {}) as {
    labels?: Record<string, Label>;
  };
  const byHand = (parse(corpus(lang, "glossary.yml")) ?? {}) as {
    labels?: Record<string, { translation?: string; reason?: string }>;
    terms?: Record<string, string>;
  };

  const labels: Record<string, Label> = { ...(generated.labels ?? {}) };
  for (const [label, override] of Object.entries(byHand.labels ?? {})) {
    // An override that only pins a key is already in the generated file.
    if (!override.translation) {
      continue;
    }
    labels[label] = {
      translation: override.translation,
      source: "override",
      reason: override.reason,
    };
  }

  return { labels, terms: byHand.terms ?? {} };
}

export interface Used {
  /** Bold labels in the section that have one correct translation. */
  labels: Record<string, string>;
  /** Bold strings in the section the glossary does not know. */
  unknown: string[];
  /** Prose terms in the section the glossary has a word for. */
  terms: Record<string, string>;
}

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** What of the glossary a section uses. This is part of its hash. */
export function used(masked: string, from: Glossary): Used {
  const labels: Record<string, string> = {};
  const unknown: string[] = [];

  for (const label of bold(masked)) {
    if (isEmphasis(label)) {
      continue;
    }
    const found = from.labels[label];
    if (found) {
      labels[label] = found.translation;
    } else if (!unknown.includes(label)) {
      unknown.push(label);
    }
  }

  const terms: Record<string, string> = {};
  const prose = masked.replace(INLINE_CODE, "");
  for (const [term, translation] of Object.entries(from.terms)) {
    if (new RegExp(`(^|[^\\p{L}])${escape(term)}`, "iu").test(prose)) {
      terms[term] = translation;
    }
  }

  return { labels, unknown, terms };
}
