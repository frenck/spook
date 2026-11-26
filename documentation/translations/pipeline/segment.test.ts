import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { CONTENT, pages } from "./config.ts";
import { headings, segment, splitFrontMatter, unmask } from "./segment.ts";

const PAGE = `---
title: A page
description: What it is about.
navigation:
  title: Short
path: /a-page
---

Intro with :term[entities]{to="entity"} and :term[Home Assistant].

## First {#kept}

A [link](/somewhere#anchor) and \`code: true\`.

| Name          | Value |
| ------------- | ----- |
| :term[Action] | 👻    |

## Again

\`\`\`yaml
## not a heading
key: value
\`\`\`

## Again

::screenshot{name="shot" alt="What it shows."}
Caption.

::
`;

test("every English page survives masking byte for byte", () => {
  assert.ok(pages().length > 50);

  for (const page of pages()) {
    const text = readFileSync(join(CONTENT, page), "utf8");
    const { sections } = segment(text);

    assert.equal(
      sections.map((section) => section.source).join(""),
      text,
      `${page}: the sections do not add up to the page`,
    );
    assert.equal(
      sections
        .map((section) => unmask(section.masked, section, "identity"))
        .join(""),
      text,
      `${page}: masking and unmasking changed the page`,
    );
  }
});

test("code, link targets and component props are masked", () => {
  const masked = segment(PAGE)
    .sections.map((section) => section.masked)
    .join("\n");

  assert.ok(!masked.includes("/somewhere#anchor"));
  assert.ok(!masked.includes("key: value"));
  assert.ok(!masked.includes('name="shot"'));
  assert.ok(masked.includes('alt="What it shows."'));
  assert.ok(masked.includes("`code: true`"), "inline code stays readable");
  assert.ok(!masked.includes("path:"), "only text keys of the front matter");
});

test("a section is named after its English anchor", () => {
  const ids = segment(PAGE).sections.map((section) => section.id);
  assert.deepEqual(ids, ["frontmatter", "intro", "kept", "again", "again-1"]);
});

test("a heading inside a code block is not a heading", () => {
  const found = headings(splitFrontMatter(PAGE).body).map(({ id }) => id);
  assert.deepEqual(found, ["kept", "again", "again-1"]);
});

test("a translated page gets the English anchors and glossary keys", () => {
  const { sections } = segment(PAGE);
  const translated = sections
    .map((section) => {
      const text = section.masked
        .replace("## First", "## Eerste")
        .replaceAll("## Again", "## Opnieuw")
        .replace(":term[entities]", ":term[entiteiten]")
        .replace(":term[Action]", ":term[Actie met een lange naam]")
        .replace("title: A page", "title: 'Een pagina: met dubbele punt'")
        .replace('alt="What it shows."', 'alt="Wat je ziet."');
      return unmask(text, section, "translated");
    })
    .join("");

  // The explicit anchor stays, repeats get the suffix the English has.
  assert.ok(translated.includes("## Eerste {#kept}\n"));
  assert.ok(translated.includes("## Opnieuw {#again}\n"));
  assert.ok(translated.includes("## Opnieuw {#again-1}\n"));
  assert.deepEqual(
    headings(splitFrontMatter(translated).body).map(({ id }) => id),
    headings(splitFrontMatter(PAGE).body).map(({ id }) => id),
  );

  // A term keeps pointing at the English glossary entry.
  assert.ok(translated.includes(':term[entiteiten]{to="entity"}'));
  assert.ok(translated.includes(':term[Home Assistant]{to="home assistant"}'));

  // Everything that is not text came back as it was.
  assert.ok(translated.includes("[link](/somewhere#anchor)"));
  assert.ok(translated.includes("```yaml\n## not a heading\nkey: value\n```"));
  assert.ok(
    translated.includes('::screenshot{name="shot" alt="Wat je ziet."}'),
  );
  assert.ok(translated.includes("path: /a-page\n"));

  // A changed table is lined up again: every row has its pipes in the
  // same columns, with the emoji counted as two wide.
  const rows = translated.split("\n").filter((line) => line.startsWith("|"));
  assert.equal(rows.length, 3);
  assert.ok(rows[2]!.includes(':term[Actie met een lange naam]{to="action"}'));
  assert.equal(new Set(rows.map((row) => row.indexOf("|", 2))).size, 1);
  // The ghost is two columns wide, and two UTF-16 units long.
  assert.equal(rows[2]!.length, rows[0]!.length);
});

test("a front matter value that needs quotes gets them", () => {
  const [frontMatter] = segment(PAGE).sections;
  const restored = unmask(
    frontMatter!.masked.replace("A page", "Een pagina: en meer"),
    frontMatter!,
    "translated",
  );

  assert.ok(restored.includes('title: "Een pagina: en meer"\n'));
  assert.ok(restored.includes("description: What it is about.\n"));
});
