/**
 * The translation pipeline, as commands.
 *
 *   npm run translate -- glossary [--lang nl] [--ha <site-packages>]
 *   npm run translate -- status   [--lang nl]
 *   npm run translate -- sync     --lang nl [--page <path>] [--dry-run] [--full]
 *   npm run translate -- verify   [--lang nl]
 *   npm run translate -- export   --lang nl --page <path> [--all] [--work <dir>]
 *   npm run translate -- export   --lang nl --page <path> --from-output [--section <id>]... [--work <dir>]
 *   npm run translate -- import   --lang nl --page <path> [--model <name>] [--work <dir>]
 *   npm run translate -- normalize --lang fr [--page <path>]
 *
 * `<path>` is a page under `content/`, like `09.guides/02.updating.md`, a
 * data file like `data/answers.yml`, or `locale` for the site's own strings.
 *
 * `sync` asks a model. `export` and `import` are the same run with a person
 * as the translator: export writes the masked sections to a work directory,
 * import reads the translation back and puts it through the same checks.
 * With `--from-output`, export starts from the translation that is on disk,
 * so a person changes the words they want and imports the rest unchanged.
 * `normalize` runs every translated section through the assembler again,
 * for a typography rule that is new.
 */
import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import { parseArgs } from "node:util";

import { assemble, outputPath, plan } from "./assemble.ts";
import type { Plan, Translation } from "./assemble.ts";
import {
  active,
  CONTENT,
  CORPUS,
  files,
  language,
  OUTPUT,
  pages,
  settings,
} from "./config.ts";
import {
  assembleData,
  dataUnits,
  maskData,
  planData,
  unmaskData,
} from "./data.ts";
import { build } from "./glossary.ts";
import { readBundle, remask, writeBundle } from "./remask.ts";
import { segment } from "./segment.ts";
import { skeleton, verifyPage } from "./verify.ts";

const { values: flags, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    lang: { type: "string" },
    page: { type: "string" },
    ha: { type: "string" },
    work: { type: "string" },
    model: { type: "string", default: "manual" },
    "dry-run": { type: "boolean", default: false },
    full: { type: "boolean", default: false },
    all: { type: "boolean", default: false },
    "from-output": { type: "boolean", default: false },
    section: { type: "string", multiple: true },
  },
});

function languages(): string[] {
  if (flags.lang) {
    return [language(flags.lang).code];
  }
  return active(settings().languages).map((entry) => entry.code);
}

function oneLanguage(): string {
  if (!flags.lang) {
    throw new Error("This command needs --lang, like --lang nl.");
  }
  return language(flags.lang).code;
}

/** A page is a Markdown file under `content/`. Anything else is data. */
function isData(unit: string): string | undefined {
  if (unit === "locale") {
    return unit;
  }
  return unit.startsWith("data/") ? unit.slice("data/".length) : undefined;
}

function onePage(): string {
  const page = flags.page;
  if (!page) {
    throw new Error(
      "This command needs --page, like --page 09.guides/02.updating.md.",
    );
  }
  if (isData(page)) {
    return page;
  }
  if (!existsSync(join(CONTENT, page))) {
    throw new Error(`There is no page ${page} under documentation/content/.`);
  }
  return page;
}

function workDirectory(lang: string): string {
  return join(flags.work ?? join(tmpdir(), "spook-translate"), lang);
}

function sha(text: string): string {
  return createHash("sha256").update(text).digest("hex").slice(0, 16);
}

function glossaryCommand(): void {
  for (const lang of languages()) {
    const built = build(lang, flags.ha);
    const path = join(CORPUS, lang, "glossary.generated.yml");
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, built.yaml);

    const count = Object.keys(built.labels).length;
    console.log(
      `${lang}: ${count} labels matched, ${built.unmatched.length} bold strings without a match.`,
    );
    console.log(`  sources: ${JSON.stringify(built.sources)}`);
    if (built.sources.frontend !== "included") {
      console.log(
        "  Home Assistant's frontend strings were not found, so its buttons and menus have no match.",
        "\n  Point --ha at a site-packages directory that has hass_frontend and homeassistant in it.",
      );
    }
  }
}

function statusCommand(): void {
  for (const lang of languages()) {
    let translated = 0;
    let stale = 0;
    for (const page of pages()) {
      if (!existsSync(outputPath(lang, page))) {
        continue;
      }
      translated++;
      const todo = plan(lang, page).sections.filter(
        (section) => section.kept === undefined,
      );
      if (todo.length) {
        stale++;
        console.log(
          `${lang}  ${page}: ${todo.length} section(s) behind the English (${todo.map((section) => section.section.id).join(", ")})`,
        );
      }
    }
    console.log(
      `${lang}: ${translated} of ${pages().length} pages translated, ${stale} behind the English.`,
    );
  }

  if (!flags.lang) {
    for (const entry of settings().languages) {
      if (entry.status === "planned") {
        console.log(`${entry.code}: planned, the corpus only.`);
      }
    }
  }
}

async function syncCommand(): Promise<void> {
  const lang = oneLanguage();
  const units = flags.page
    ? [onePage()]
    : [
        ...pages(),
        ...dataUnits().map((unit) =>
          unit === "locale" ? unit : `data/${unit}`,
        ),
      ];

  const plans = units.flatMap((unit) =>
    isData(unit) ? [] : [plan(lang, unit)],
  );
  const data = units.flatMap((unit) => {
    const name = isData(unit);
    return name ? [planData(lang, name)] : [];
  });

  const sections = plans.reduce(
    (total, page) =>
      total +
      page.sections.filter((section) => section.kept === undefined).length,
    0,
  );
  const strings = data.reduce(
    (total, file) =>
      total + file.strings.filter((string) => string.kept === undefined).length,
    0,
  );
  console.log(
    `${lang}: ${sections} section(s) in ${plans.length} page(s) and ${strings} string(s) in ${data.length} data file(s) to translate.`,
  );

  if (flags["dry-run"]) {
    for (const page of plans) {
      const todo = page.sections.filter(
        (section) => section.kept === undefined,
      );
      if (todo.length) {
        console.log(
          `  ${page.page}: ${todo.map((section) => section.section.id).join(", ")}`,
        );
      }
    }
    for (const file of data) {
      const todo = file.strings.filter((string) => string.kept === undefined);
      if (todo.length) {
        console.log(`  ${file.unit}: ${todo.length} string(s)`);
      }
    }
    return;
  }

  // A careless change to a hash would send the whole site to the model.
  const budget = settings().budget_sections;
  if (sections > budget && !flags.full) {
    throw new Error(
      `That is more than the budget of ${budget} sections in languages.yml. Run with --full when you mean it.`,
    );
  }

  const { translateSection, translateStrings } = await import("./translate.ts");
  let failed = 0;

  for (const page of plans) {
    const todo = page.sections.filter((section) => section.kept === undefined);
    if (!todo.length) {
      continue;
    }

    const previous = existsSync(outputPath(lang, page.page))
      ? new Map(
          segment(
            readFileSync(outputPath(lang, page.page), "utf8"),
          ).sections.map((section) => [section.id, section.masked]),
        )
      : new Map<string, string>();

    const translations = new Map<string, Translation>();
    const outcomes = await Promise.all(
      todo.map((section) =>
        translateSection(
          lang,
          page.page,
          section,
          previous.get(section.section.id),
        ),
      ),
    );
    outcomes.forEach((outcome, index) => {
      const id = todo[index]!.section.id;
      if (outcome.masked !== undefined) {
        translations.set(id, { masked: outcome.masked, model: outcome.model });
      }
      for (const note of outcome.notes) {
        console.log(`  ${page.page} [${id}] ${note}`);
      }
    });

    const result = assemble(page, translations, { write: true });
    report(page.page, result.written, result.errors, result.untranslated);
    failed += result.written ? 0 : 1;
  }

  for (const file of data) {
    const masked = maskData(file);
    if (!masked) {
      continue;
    }
    const answer = await translateStrings(lang, file.unit, masked);
    const result = assembleData(
      file,
      unmaskData(file, answer),
      settings().models.translate,
      { write: true },
    );
    report(file.unit, result.written, result.errors, result.untranslated);
    failed += result.written ? 0 : 1;
  }

  if (failed) {
    process.exitCode = 1;
  }
}

function report(
  unit: string,
  written: boolean,
  errors: string[],
  untranslated: string[],
): void {
  if (written) {
    const rest = untranslated.length
      ? `, ${untranslated.length} part(s) still English: ${untranslated.join(", ")}`
      : "";
    console.log(`  ${unit}: written${rest}`);
    return;
  }

  console.log(`  ${unit}: NOT written, ${errors.length} check(s) failed`);
  for (const error of errors) {
    console.log(`    ${error}`);
  }
}

function verifyCommand(): void {
  let failed = 0;
  let checked = 0;

  for (const lang of languages()) {
    for (const page of files(join(OUTPUT, lang, "content"), ".md")) {
      checked++;
      const source = join(CONTENT, page);
      if (!existsSync(source)) {
        failed++;
        console.log(
          `${lang}  ${page}: there is no English page for it any more`,
        );
        continue;
      }

      const english = readFileSync(source, "utf8");
      const translated = readFileSync(outputPath(lang, page), "utf8");
      const errors = verifyPage(english, translated);

      const expected = skeleton(segment(english));
      const found = skeleton(segment(translated));
      const stale = plan(lang, page).sections.some(
        (section) => section.kept === undefined,
      );
      // A page that is behind the English differs for a good reason. `status`
      // lists those, and the next sync brings them back in line.
      if (!stale && expected.join("\n") !== found.join("\n")) {
        const index = expected.findIndex((fact, at) => fact !== found[at]);
        errors.push(
          `the structure differs from the English: expected "${expected[index]}", found "${found[index]}"`,
        );
      }

      if (errors.length) {
        failed++;
        console.log(`${lang}  ${page}:`);
        for (const error of errors) {
          console.log(`    ${error}`);
        }
      }
    }
  }

  console.log(`${checked} translated page(s) checked, ${failed} failed.`);
  if (failed) {
    process.exitCode = 1;
  }
}

function bundlePath(lang: string, unit: string, suffix: string): string {
  return join(
    workDirectory(lang),
    `${unit.replace(/\.(md|yml)$/, "")}.${suffix}`,
  );
}

function exportCommand(): void {
  const lang = oneLanguage();
  const unit = onePage();
  const english = bundlePath(lang, unit, "en.md");
  mkdirSync(dirname(english), { recursive: true });

  const data = isData(unit);
  if (data && flags["from-output"]) {
    throw new Error(
      "--from-output works on pages. For a data file, name the strings with --section <key>.",
    );
  }
  if (data) {
    const planned = planData(lang, data);

    // A string that is up to date is not handed out, unless it is named:
    // `--section home.titleEnd` hands it out with its current translation
    // filled in, to change a word without touching the English.
    const named = flags.section ?? [];
    const unknown = named.filter(
      (id) => !planned.strings.some((string) => string.id === id),
    );
    if (unknown.length) {
      throw new Error(`${unit} has no string ${unknown.join(", ")}.`);
    }

    const current = new Map<string, string>();
    for (const string of planned.strings) {
      if (named.includes(string.id) && string.kept !== undefined) {
        current.set(string.id, string.kept);
        delete string.kept;
      }
    }

    writeFileSync(english, `${maskData(planned)}\n`);
    writeFileSync(
      bundlePath(lang, unit, "export.json"),
      JSON.stringify({ source: sha(planned.english) }),
    );
    if (current.size) {
      writeFileSync(
        bundlePath(lang, unit, `${lang}.md`),
        `${planned.strings
          .flatMap((string, index) =>
            current.has(string.id)
              ? [
                  `⟦S${index + 1}⟧ ${current.get(string.id)!.replaceAll("\n", " ⏎ ")}`,
                ]
              : [],
          )
          .join("\n")}\n`,
      );
    }
    console.log(`Exported the strings of ${unit} to ${english}`);
    console.log(
      `Write the translation to ${bundlePath(lang, unit, `${lang}.md`)}`,
    );
    return;
  }

  const planned = plan(lang, unit);
  const fromOutput = flags["from-output"]
    ? remask(planned, flags.section, { forEditing: true })
    : undefined;
  const todo = planned.sections.filter(({ section, kept }) =>
    fromOutput
      ? fromOutput.has(section.id)
      : flags.section
        ? flags.section.includes(section.id)
        : flags.all || kept === undefined,
  );

  writeFileSync(
    english,
    writeBundle(
      new Map(todo.map(({ section }) => [section.id, section.masked])),
    ),
  );

  // The translation as it is: change what needs changing, keep the rest.
  if (fromOutput) {
    writeFileSync(
      bundlePath(lang, unit, `${lang}.md`),
      writeBundle(fromOutput),
    );
  }

  // What the translator needs next to the text: the labels that are not
  // theirs to choose, and the words the glossary has.
  const context = todo.flatMap(({ section, used }) => {
    const lines = [
      ...Object.entries(used.labels).map(
        ([label, translation]) => `- label **${label}** => **${translation}**`,
      ),
      ...used.unknown.map(
        (label) =>
          `- bold without a label: **${label}** (on screen: keep. Emphasis: translate.)`,
      ),
      ...Object.entries(used.terms).map(
        ([term, translation]) => `- term ${term} => ${translation}`,
      ),
    ];
    return lines.length ? [`## ${section.id}`, ...lines, ""] : [];
  });
  writeFileSync(bundlePath(lang, unit, "context.md"), context.join("\n"));

  writeFileSync(
    bundlePath(lang, unit, "export.json"),
    JSON.stringify({
      source: sha(planned.english),
      sections: todo.map(({ section }) => section.id),
    }),
  );

  console.log(
    `Exported ${todo.length} of ${planned.sections.length} section(s) of ${unit} to ${english}`,
  );
  console.log(
    fromOutput
      ? `The current translation is in ${bundlePath(lang, unit, `${lang}.md`)}. Edit it there.`
      : `Write the translation to ${bundlePath(lang, unit, `${lang}.md`)}`,
  );
}

/** Read the translated bundle: one file, or parts named `<lang>.1.md`. */
function readWork(lang: string, unit: string): string {
  const directory = dirname(bundlePath(lang, unit, "x"));
  const stem = basename(bundlePath(lang, unit, lang));
  const parts = readdirSync(directory)
    .filter((name) =>
      new RegExp(`^${stem.replace(/\./g, "\\.")}(\\.\\d+)?\\.md$`).test(name),
    )
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  if (!parts.length) {
    throw new Error(
      `There is no translation at ${bundlePath(lang, unit, `${lang}.md`)}.`,
    );
  }
  return parts
    .map((name) => readFileSync(join(directory, name), "utf8"))
    .join("\n");
}

function importCommand(): void {
  const lang = oneLanguage();
  const unit = onePage();
  const exported = JSON.parse(
    readFileSync(bundlePath(lang, unit, "export.json"), "utf8"),
  ) as { source: string; sections?: string[] };
  const bundle = readWork(lang, unit);

  const data = isData(unit);
  if (data) {
    const planned = planData(lang, data);
    if (sha(planned.english) !== exported.source) {
      throw new Error(`${unit} changed since the export. Export it again.`);
    }
    const result = assembleData(
      planned,
      unmaskData(planned, bundle),
      flags.model!,
      {
        write: !flags["dry-run"],
      },
    );
    report(unit, result.written, result.errors, result.untranslated);
    process.exitCode = result.errors.length ? 1 : 0;
    return;
  }

  const planned: Plan = plan(lang, unit);
  if (sha(planned.english) !== exported.source) {
    throw new Error(`${unit} changed since the export. Export it again.`);
  }

  const translations = new Map<string, Translation>();
  for (const [id, masked] of readBundle(bundle, planned)) {
    translations.set(id, { masked, model: flags.model! });
  }

  const missing = planned.sections.filter(
    (section) =>
      section.kept === undefined && !translations.has(section.section.id),
  );
  if (missing.length) {
    throw new Error(
      `The translation misses section(s): ${missing.map((section) => section.section.id).join(", ")}.`,
    );
  }

  const result = assemble(planned, translations, { write: !flags["dry-run"] });
  report(unit, result.written, result.errors, result.untranslated);

  const labels = planned.sections.reduce(
    (total, section) => total + Object.keys(section.used.labels).length,
    0,
  );
  console.log(`  ${labels} bold label(s) set from the glossary.`);
  const unknown = new Map(
    result.unknown.map((entry) => [entry.label, entry.kept]),
  );
  for (const [label, kept] of unknown) {
    console.log(
      `  bold without a glossary entry: **${label}** (${kept ? "kept in English" : "translated"})`,
    );
  }

  process.exitCode = result.errors.length ? 1 : 0;
}

/**
 * Run every translated section of a page through the assembler again, as it
 * is on disk. Nothing is translated: what changes is what the assembler adds
 * on its own, like the spaces of `typography.yml`.
 */
function normalizeCommand(): void {
  const lang = oneLanguage();
  const units = flags.page ? [onePage()] : pages();
  let changed = 0;
  let failed = 0;

  for (const page of units) {
    if (isData(page) || !existsSync(outputPath(lang, page))) {
      continue;
    }

    const planned = plan(lang, page);
    const masked = remask(planned);

    // A section behind the English would go in as English: that is for a
    // sync to fix, with a translator, not for this.
    const behind = planned.sections.filter(
      ({ section, kept }) => kept === undefined && !masked.has(section.id),
    );
    if (behind.length) {
      console.log(
        `  ${page}: skipped, behind the English (${behind.map(({ section }) => section.id).join(", ")})`,
      );
      continue;
    }

    const translations = new Map<string, Translation>();
    for (const [id, text] of masked) {
      const entry = planned.sections.find(({ section }) => section.id === id);
      translations.set(id, {
        masked: text,
        model: entry!.previous!.entry.model,
      });
    }

    const before = readFileSync(outputPath(lang, page), "utf8");
    const result = assemble(planned, translations, {
      write: !flags["dry-run"],
    });
    if (result.errors.length) {
      failed++;
      report(page, false, result.errors, result.untranslated);
    } else if (result.text !== before) {
      changed++;
      console.log(
        `  ${page}: ${flags["dry-run"] ? "would change" : "written"}`,
      );
    }
  }

  console.log(`${lang}: ${changed} page(s) changed, ${failed} failed.`);
  if (failed) {
    process.exitCode = 1;
  }
}

const commands: Record<string, () => void | Promise<void>> = {
  glossary: glossaryCommand,
  status: statusCommand,
  sync: syncCommand,
  verify: verifyCommand,
  export: exportCommand,
  import: importCommand,
  normalize: normalizeCommand,
};

const command = commands[positionals[0] ?? ""];
if (!command) {
  console.error(
    `Usage: npm run translate -- <${Object.keys(commands).join("|")}> [options]`,
  );
  console.error("See the top of documentation/translations/pipeline/cli.ts.");
  process.exit(2);
}

try {
  await command();
} catch (error) {
  console.error((error as Error).message);
  process.exit(1);
}
