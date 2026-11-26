import assert from "node:assert/strict";
import { test } from "node:test";

import { segment, unmask } from "./segment.ts";
import type { Section } from "./segment.ts";
import { textLength, verifyPage, verifySection } from "./verify.ts";
import type { Rules } from "./verify.ts";

const ENGLISH = `---
title: Snooze
description: Turn an automation off for a while.
path: /snooze
---

## How to use it

Spook adds this to :term[Home Assistant]. It is marked with a 👻.

1. Select **Add action**.
2. Search for \`snooze\`, then read [the guide](/guide).

::note
Not for the faint of heart. _#BobTheBuilder_

::
`;

const RULES: Rules = {
  labels: { "Add action": "Actie toevoegen" },
  keep: ["Spook", "Home Assistant"],
  never: ["[—–]", "\\b[Kk]lik"],
  hashtags: {},
  corrections: [],
};

const page = segment(ENGLISH);
const section = page.sections.find((found) => found.id === "how-to-use-it")!;
const frontMatter = page.sections[0]!;

const GOOD = section.masked
  .replace("How to use it", "Zo gebruik je het")
  .replace(
    "Spook adds this to :term[Home Assistant]⟦T1⟧. It is marked with a 👻.",
    "Spook voegt dit toe aan :term[Home Assistant]⟦T1⟧. Het is gemarkeerd met een 👻.",
  )
  .replace("Select **Add action**.", "Selecteer **Actie toevoegen**.")
  .replace(
    "Search for `snooze`, then read [the guide]",
    "Zoek naar `snooze`, en lees daarna [de gids]",
  )
  .replace("Not for the faint of heart.", "Niet voor bange mensen.");

function problems(translated: string, from: Section = section): string {
  return verifySection(from, translated, RULES).join("\n");
}

test("a faithful translation passes", () => {
  assert.equal(problems(GOOD), "");
  assert.ok(GOOD.includes("Zo gebruik je het"));
});

test("the untranslated section passes everything but its label", () => {
  assert.match(problems(section.masked), /^label \*\*Add action\*\*/);
});

const BROKEN: [string, (text: string) => string, RegExp][] = [
  ["a dropped link", (text) => text.replace("(⟦L1⟧)", ""), /tokens differ/],
  [
    "a link target typed out",
    (text) => text.replace("⟦L1⟧", "/gids"),
    /tokens differ/,
  ],
  [
    "a term without its token",
    (text) => text.replace("]⟦T1⟧", "]"),
    /tokens differ/,
  ],
  [
    "a damaged token",
    (text) => text.replace("⟦T1⟧", "⟦T1"),
    /tokens differ|damaged/,
  ],
  [
    "translated inline code",
    (text) => text.replace("`snooze`", "`sluimer`"),
    /inline code differs/,
  ],
  [
    "a dropped step",
    (text) => text.replace(/\n2\. .*/, ""),
    /lines where the English has/,
  ],
  [
    "a heading turned into text",
    (text) => text.replace("## Zo", "Zo"),
    /line 1 is "text 0"/,
  ],
  [
    "a renamed component",
    (text) => text.replace("::note", "::tip"),
    /is "component ::tip/,
  ],
  [
    "an invented label",
    (text) => text.replace("**Actie toevoegen**", "**Voeg actie toe**"),
    /has to be \*\*Actie toevoegen\*\*/,
  ],
  [
    "a translated name",
    (text) => text.replaceAll("Home Assistant", "Thuisassistent"),
    /"Home Assistant" is gone/,
  ],
  [
    "a dash as punctuation",
    (text) => text.replace("toe aan", "toe — aan"),
    /"—" is not allowed/,
  ],
  [
    "click instead of select",
    (text) => text.replace("Selecteer", "Klik op"),
    /"Klik" is not allowed/,
  ],
  ["a lost emoji", (text) => text.replace(" 👻", ""), /emoji differ/],
  [
    "a translated hashtag",
    (text) => text.replace("#BobTheBuilder", "#BobDeBouwer"),
    /hashtag #BobTheBuilder/,
  ],
];

for (const [name, damage, expected] of BROKEN) {
  test(`verify catches ${name}`, () => {
    const broken = damage(GOOD);
    assert.notEqual(broken, GOOD, "the test did not break anything");
    assert.match(problems(broken), expected);
  });
}

test("a hashtag with a local version has to use it", () => {
  const rules = { ...RULES, hashtags: { "#BobTheBuilder": "#BobDeBouwer" } };
  const local = GOOD.replace("#BobTheBuilder", "#BobDeBouwer");

  assert.deepEqual(verifySection(section, local, rules), []);
  assert.match(verifySection(section, GOOD, rules).join("\n"), /#BobDeBouwer/);
});

test("a pinned correction has to be in the translation", () => {
  const rules = { ...RULES, corrections: ["Niet voor watjes."] };
  assert.match(
    verifySection(section, GOOD, rules).join("\n"),
    /pinned correction is missing/,
  );
});

test("a description stays one line without a colon and a space", () => {
  const good = "title: Snoozen\ndescription: Zet een automatisering even uit.";
  assert.equal(problems(good, frontMatter), "");

  assert.match(
    problems(good.replace("Zet", "Kort: zet"), frontMatter),
    /colon and a space/,
  );
  assert.match(
    problems(good.replace("description: ", "description:"), frontMatter),
    /"description" is missing/,
  );
  assert.match(problems("title: Snoozen", frontMatter), /missing or empty/);
});

test("a translated page keeps the anchors and the rest of the front matter", () => {
  const translated = page.sections
    .map((found) =>
      unmask(found === section ? GOOD : found.masked, found, "translated"),
    )
    .join("");

  assert.deepEqual(verifyPage(ENGLISH, translated), []);
  assert.ok(translated.includes("## Zo gebruik je het {#how-to-use-it}"));

  assert.match(
    verifyPage(ENGLISH, translated.replace(" {#how-to-use-it}", "")).join(),
    /anchors differ/,
  );
  assert.match(
    verifyPage(ENGLISH, translated.replace("/snooze", "/snoozen")).join(),
    /front matter differs/,
  );
  assert.match(
    verifyPage(ENGLISH, `${translated}\n⟦L9⟧`).join(),
    /mask token is left/,
  );
});

test("a Chinese character counts as two letters in the length check", () => {
  assert.equal(textLength("Spook"), 5);
  assert.equal(textLength("重启 Home Assistant"), 19);
});

test("bold that Markdown does not close fails, in any language", () => {
  const english = `## Fix it

**How to fix it:** remove the reference. Not that \\*\\*bad word\\*\\*.
`;
  const page = (text: string) => `## 修复 {#fix-it}\n\n${text}\n`;
  const chinese = (fix: string) =>
    page(`${fix}删除引用。不当那种 \\*\\*脏话\\*\\*。`);
  const french = (fix: string) =>
    page(`${fix}supprimez la référence. Pas ce \\*\\*gros mot\\*\\*.`);

  // The English has two literal `**` on purpose: the same two pass.
  assert.deepEqual(verifyPage(english, chinese("**怎么修复**：")), []);
  assert.deepEqual(verifyPage(english, french("**Correction :** ")), []);

  assert.match(
    verifyPage(english, chinese("**怎么修复：**")).join(),
    /\[fix-it\] 4 literal \*\* or __ where the English has 2/,
  );
  assert.match(
    verifyPage(english, french("**Correction :**")).join(),
    /\[fix-it\] 4 literal \*\* or __ where the English has 2/,
  );
});
