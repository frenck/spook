import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { assemble, lockPath, notice, outputPath, plan } from "./assemble.ts";
import type { Lock } from "./assemble.ts";
import { CONTENT, files, OUTPUT, settings } from "./config.ts";
import { segment } from "./segment.ts";
import { skeleton } from "./verify.ts";

const translated = settings().languages.flatMap(({ code }) =>
  files(join(OUTPUT, code, "content"), ".md").map(
    (page) => [code, page] as const,
  ),
);

test("there are translated pages to test with", () => {
  assert.ok(translated.length > 0);
});

for (const [lang, page] of translated) {
  test(`${lang}/${page} is rebuilt from what is on disk, byte for byte`, () => {
    const planned = plan(lang, page);
    const stale = planned.sections.filter(
      (section) => section.kept === undefined,
    );

    // An unchanged section is never sent to a model, and never changes.
    if (!stale.length) {
      const result = assemble(planned, new Map(), { write: false });
      assert.deepEqual(result.errors, []);
      assert.deepEqual(result.untranslated, []);
      assert.equal(result.text, readFileSync(outputPath(lang, page), "utf8"));
    }
  });

  test(`${lang}/${page} is marked as generated and has a lock file`, () => {
    const text = readFileSync(outputPath(lang, page), "utf8");
    const [first] = notice(`documentation/content/${page}`);
    assert.ok(text.startsWith(`---\n# ${first}\n`));

    assert.ok(existsSync(lockPath(lang, page)));
    const lock = JSON.parse(readFileSync(lockPath(lang, page), "utf8")) as Lock;
    assert.equal(Object.keys(lock)[0], "//");
    assert.equal(lock.source, `documentation/content/${page}`);

    const ids = segment(text).sections.map((section) => section.id);
    assert.deepEqual(
      lock.sections.map((section) => section.id),
      ids,
    );
    for (const section of lock.sections) {
      assert.ok(section.model && section.date && section.source);
    }
  });

  test(`${lang}/${page} has the structure of the English page`, () => {
    const planned = plan(lang, page);
    if (planned.sections.some((section) => section.kept === undefined)) {
      return;
    }

    const english = readFileSync(join(CONTENT, page), "utf8");
    const text = readFileSync(outputPath(lang, page), "utf8");
    assert.deepEqual(skeleton(segment(text)), skeleton(segment(english)));
  });
}

test("a section whose English changed is the only one to translate again", () => {
  const [lang, page] = translated[0]!;
  const planned = plan(lang, page);
  const before = planned.sections.filter(
    (section) => section.kept !== undefined,
  );

  // Stand in for an edit of the English: another hash for one section.
  const changed = before.at(-1)!;
  const edited = {
    ...planned,
    sections: planned.sections.map((section) =>
      section === changed
        ? { ...section, kept: undefined, entry: undefined }
        : section,
    ),
  };

  const result = assemble(edited, new Map(), { write: false });
  assert.deepEqual(result.untranslated, [changed.section.id]);

  // Everything before the changed section is still what is on disk.
  const disk = readFileSync(outputPath(lang, page), "utf8");
  const unchanged = before
    .slice(0, -1)
    .map((section) => section.kept)
    .join("");
  assert.ok(
    result.text.replace(/^---\n(# .*\n){4}/, "---\n").startsWith(unchanged),
  );
  assert.ok(disk.replace(/^---\n(# .*\n){4}/, "---\n").startsWith(unchanged));
});
