/**
 * The names in the home of the screenshots, in the language of the run.
 *
 * They live in seed/names/<language>.yml, with English as the fallback for
 * any name a language does not have (yet). The seed refers to them as
 * ${light.living_room_lamp}; the shots look them up with `names(language)`.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const here = dirname(fileURLToPath(import.meta.url));
const folder = join(here, "seed", "names");

// The parts of a names file that are not entities. Everything else is a
// domain, with object IDs under it.
const NOT_ENTITIES = new Set([
  "home",
  "area",
  "floor",
  "label",
  "category",
  "user",
  "blueprints",
  "dashboard",
  "examples",
  "search",
]);

const PLACEHOLDER = /\$\{([\w.-]+)\}/g;

function load(language: string): Record<string, any> {
  const file = join(folder, `${language}.yml`);
  return existsSync(file) ? (parse(readFileSync(file, "utf-8")) ?? {}) : {};
}

function dig(tree: Record<string, any>, path: string): unknown {
  return path.split(".").reduce<any>((branch, key) => branch?.[key], tree);
}

/** Every entity the names are for, like `light.living_room_lamp`. */
export function entityIds(): string[] {
  return Object.entries(load("en"))
    .filter(([domain]) => !NOT_ENTITIES.has(domain))
    .flatMap(([domain, objects]) =>
      Object.keys(objects).map((objectId) => `${domain}.${objectId}`),
    );
}

/** Every area of the home, by ID. */
export function areaIds(): string[] {
  return Object.keys(load("en").area);
}

export function names(language: string) {
  const own = load(language);
  const english = load("en");

  /** The name at a path, like `area.attic`, in this language or English. */
  function name(path: string): string {
    const found = dig(own, path) ?? dig(english, path);
    if (typeof found !== "string") {
      throw new Error(`No name for ${path} in seed/names/en.yml`);
    }
    return found;
  }

  /**
   * The seed with the names filled in. With `asIds`, an entity gets its
   * object ID as its name instead, like `movie_night`: Home Assistant makes
   * the entity ID out of the name an entity first has, so this way the ID
   * is the same in every language. The real names follow after.
   */
  function fill(text: string, { asIds = false } = {}): string {
    return text.replace(PLACEHOLDER, (_, path: string) => {
      const value = path === "language" ? language : textFor(path, asIds);
      // Always inside double quotes, in JSON and in YAML alike, and both read
      // a JSON string the same way.
      return JSON.stringify(value).slice(1, -1);
    });
  }

  function textFor(path: string, asIds: boolean): string {
    const [domain, objectId, field] = path.split(".");
    const isEntityName =
      !NOT_ENTITIES.has(domain) && (field === undefined || field === "name");
    return asIds && isEntityName ? objectId : name(path);
  }

  /** A word to search for, only in this language. */
  function search(topic: string): string | undefined {
    return own.search?.[topic];
  }

  return { name, fill, search };
}
