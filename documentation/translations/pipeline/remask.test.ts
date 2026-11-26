import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { assemble, lockPath, outputPath, plan } from "./assemble.ts";
import type { Translation } from "./assemble.ts";
import { files, OUTPUT, settings, today } from "./config.ts";
import { glossary } from "./glossary.ts";
import { readBundle, remask, writeBundle } from "./remask.ts";

const translated = settings().languages.flatMap(({ code }) =>
  files(join(OUTPUT, code, "content"), ".md").map(
    (page) => [code, page] as const,
  ),
);

/** What `export --from-output` and then `import` do, without the files. */
function roundTrip(
  lang: string,
  page: string,
  edit: (id: string, masked: string) => string = (_id, masked) => masked,
) {
  const planned = plan(lang, page);
  const bundle = writeBundle(
    new Map([...remask(planned)].map(([id, masked]) => [id, edit(id, masked)])),
  );

  const translations = new Map<string, Translation>();
  for (const [id, masked] of readBundle(bundle, planned)) {
    translations.set(id, { masked, model: "manual" });
  }

  return assemble(planned, translations, { write: false });
}

test("there are translated pages to round-trip", () => {
  assert.ok(translated.length > 0);
});

for (const [lang, page] of translated) {
  test(`${lang}/${page} comes back byte for byte from export --from-output`, () => {
    const result = roundTrip(lang, page);

    assert.deepEqual(result.errors, []);
    assert.deepEqual(result.untranslated, []);
    assert.equal(result.text, readFileSync(outputPath(lang, page), "utf8"));
    assert.equal(
      `${JSON.stringify(result.lock, null, 2)}\n`,
      readFileSync(lockPath(lang, page), "utf8"),
    );
  });
}

test("a word changed in the work file comes through, and only there", () => {
  const lang = "fr";
  const page = "01.getting-started/03.usage.md";
  const planned = plan(lang, page);
  const [id] = [...remask(planned)].find(([, masked]) =>
    masked.includes("Quand quelque chose cloche"),
  )!;

  const result = roundTrip(lang, page, (section, masked) =>
    section === id
      ? masked.replace("Quand quelque chose cloche", "Quand ça coince")
      : masked,
  );
  assert.deepEqual(result.errors, []);

  const disk = readFileSync(outputPath(lang, page), "utf8");
  assert.equal(
    result.text,
    disk.replace("Quand quelque chose cloche", "Quand ça coince"),
  );

  // The edited section is new work; every other section keeps who wrote it.
  const before = JSON.parse(readFileSync(lockPath(lang, page), "utf8")) as {
    sections: { id: string; model: string; date: string }[];
  };
  for (const entry of result.lock.sections) {
    const old = before.sections.find((section) => section.id === entry.id)!;
    if (entry.id === id) {
      assert.equal(entry.model, "manual");
      assert.equal(entry.date, today());
    } else {
      assert.deepEqual(entry, old);
    }
  }
});

test("asking for a section the page does not have is an error", () => {
  const [lang, page] = translated[0]!;
  assert.throws(
    () => remask(plan(lang, page), ["no-such-section"]),
    /no section "no-such-section"/,
  );
});

test("a section behind only because a glossary term went away is handed out", () => {
  const lang = "es";
  const page = "04.enhanced-integrations/03.automation.md";
  const terms = glossary(lang);
  const section = plan(lang, page, terms).sections.find(
    ({ used }) => "automation" in used.terms,
  )!;
  const id = section.section.id;

  // Removed: same words, nothing to translate, so remask may bring it back.
  const { automation: _removed, ...rest } = terms.terms;
  const removed = plan(lang, page, { ...terms, terms: rest });
  const behind = removed.sections.find(({ section }) => section.id === id)!;
  assert.equal(behind.kept, undefined);
  assert.equal(behind.previous?.reusable, true);
  assert.ok(remask(removed).has(id));

  // Changed: the old word is wrong now, and a translator has to see it.
  const changed = plan(lang, page, {
    ...terms,
    terms: { ...terms.terms, automation: "rutina" },
  });
  assert.equal(
    changed.sections.find(({ section }) => section.id === id)!.previous
      ?.reusable,
    false,
  );
  assert.ok(!remask(changed).has(id));
  assert.throws(
    () => remask(changed, [id]),
    /no translation of the current English and corpus/,
  );
});
