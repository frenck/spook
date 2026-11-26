import assert from "node:assert/strict";
import { test } from "node:test";

import { typeset, typographyFor } from "./typography.ts";
import type { Typography } from "./typography.ts";

const FRENCH: Typography = {
  before: [":", ";", "!", "?"],
  inside: [["«", "»"]],
};

// Written out, so a test failure shows where the space went.
const NBSP = " ";
const show = (text: string) => text.replaceAll(NBSP, "⍽");

function body(text: string, english = "", labels: string[] = []): string {
  return show(typeset(text, "body", FRENCH, english, labels));
}

test("French has rules, and a language without a file has none", () => {
  assert.deepEqual(typographyFor("fr"), FRENCH);
  assert.equal(typographyFor("nl"), undefined);
  assert.equal(typeset("Klaar ?", "body", undefined, ""), "Klaar ?");
});

test("a plain space before a mark becomes a non-breaking one", () => {
  assert.equal(body("Prêt ? Oui !"), "Prêt⍽? Oui⍽!");
  assert.equal(body("Ceci ; cela : rien."), "Ceci⍽; cela⍽: rien.");
});

test("a missing space is added", () => {
  assert.equal(body("Prêt? Oui!"), "Prêt⍽? Oui⍽!");
  assert.equal(body("**Remarque:** lisez."), "**Remarque⍽:** lisez.");
});

test("a space that is already non-breaking, narrow or not, stays", () => {
  assert.equal(body(`Prêt${NBSP}?`), "Prêt⍽?");
  assert.equal(body("Prêt ?"), "Prêt ?");
});

test("guillemets get the space inside", () => {
  assert.equal(body("« oui »"), "«⍽oui⍽»");
  assert.equal(body("«oui»"), "«⍽oui⍽»");
});

test("a colon that is not punctuation stays", () => {
  assert.equal(body("À 08:00, ou à 8:30."), "À 08:00, ou à 8:30.");
  assert.equal(
    body("Une :term[pièce]⟦T1⟧ et ![une image](⟦L1⟧)"),
    "Une :term[pièce]⟦T1⟧ et ![une image](⟦L1⟧)",
  );
  assert.equal(
    body("Allez dans **Paramètres** > **Système**."),
    "Allez dans **Paramètres** > **Système**.",
  );
  assert.equal(body("Quoi?!"), "Quoi⍽?!");
});

test("code, components, tokens and image alt text are left alone", () => {
  assert.equal(
    body("Mettez `mode: single` ici."),
    "Mettez `mode: single` ici.",
  );
  assert.equal(
    body('::screenshot{⟦P1⟧ alt="Le menu : ouvert ?"}'),
    '::screenshot{⟦P1⟧ alt="Le menu : ouvert ?"}',
  );
  assert.equal(body("⟦CODE1⟧"), "⟦CODE1⟧");
  assert.equal(body("![Prêt ?](⟦L1⟧)"), "![Prêt ?](⟦L1⟧)");
  assert.equal(body("| :--- | ---: |"), "| :--- | ---: |");
});

test("in the front matter, only the values", () => {
  assert.equal(
    show(
      typeset(
        "title: Prêt ?\ndescription: Ceci: cela",
        "frontmatter",
        FRENCH,
        "",
      ),
    ),
    "title: Prêt⍽?\ndescription: Ceci⍽: cela",
  );
});

test("English the translation kept, and labels, keep their own marks", () => {
  // "Boo!" is the name of an action: it is in the English as it is.
  assert.equal(body("### Boo!", "### Boo!\n"), "### Boo!");
  // A label is what Home Assistant shows, colon and all.
  assert.equal(
    body("Sélectionnez **Automatisation: Mettre en veille**.", "", [
      "Automatisation: Mettre en veille",
    ]),
    "Sélectionnez **Automatisation: Mettre en veille**.",
  );
  // A typed space is French, even before a word the English has too.
  assert.equal(body("Boo !", "Boo!"), "Boo⍽!");
});
