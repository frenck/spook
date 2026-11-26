import assert from "node:assert/strict";
import { test } from "node:test";

import { active } from "./config.ts";
import type { Language } from "./config.ts";
import { bold, build, isEmphasis, used } from "./glossary.ts";
import type { Glossary } from "./glossary.ts";

const GLOSSARY: Glossary = {
  labels: {
    Settings: { translation: "Instellingen", source: "frontend" },
    "Automation: Snooze 👻": {
      translation: "Automatisering: Snoozen 👻",
      source: "composite",
    },
  },
  terms: { automation: "automatisering", "entity ID": "entiteit-ID" },
};

test("bold strings are found, but not inside inline code", () => {
  const text = "Go to **Settings** > **About**, not `**kwargs**`.";
  assert.deepEqual(bold(text), ["Settings", "About"]);
});

test("bold that ends a thought is emphasis, not a label", () => {
  assert.ok(isEmphasis("How to fix it:"));
  assert.ok(isEmphasis("New actions."));
  assert.ok(isEmphasis("🎉 Spook is here 🎉"));
  assert.ok(!isEmphasis("Add action"));
  assert.ok(!isEmphasis("+ Add integration"));
});

test("a section uses the labels and terms that are in it", () => {
  const found = used(
    "Open **Settings**, pick an Automation and select **Automation: Snooze 👻** or **Something else**. **Mind this:** no `entity ID` here.",
    GLOSSARY,
  );

  assert.deepEqual(found.labels, {
    Settings: "Instellingen",
    "Automation: Snooze 👻": "Automatisering: Snoozen 👻",
  });
  assert.deepEqual(found.unknown, ["Something else"]);
  assert.deepEqual(found.terms, { automation: "automatisering" });
});

test("a planned language is only touched when it is named", () => {
  const languages: Language[] = [
    { code: "nl", name: "Dutch", status: "pilot" },
    { code: "de", name: "German", status: "live" },
    { code: "fr", name: "French", status: "planned" },
    { code: "xx", name: "Stopped", status: "off" },
  ];

  assert.deepEqual(
    active(languages).map((entry) => entry.code),
    ["nl", "de"],
  );
});

test("a language code with a region or a script finds Spook's strings", () => {
  // Spook ships pt-BR.json and zh-Hans.json. The code is the file name.
  for (const lang of ["pt-BR", "zh-Hans"]) {
    const built = build(lang);
    const fromSpook = Object.values(built.labels).filter(
      (label) => label.source === "spook",
    );

    assert.ok(fromSpook.length > 100, `${lang}: ${fromSpook.length} labels`);
  }
});

test("the start of a repair title loses the space French puts before the colon", () => {
  // Spook's French says `… utilisées dans : {automation}`, with a
  // non-breaking space before the colon. The label is the start, without it.
  const label = build("fr").labels["Unknown entities used in"];

  assert.ok(label, "the label is matched");
  assert.equal(label.translation, label.translation.trim());
});
