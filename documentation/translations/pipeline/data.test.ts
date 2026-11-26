import assert from "node:assert/strict";
import { test } from "node:test";

import {
  assembleData,
  dataUnits,
  maskData,
  planData,
  unmaskData,
} from "./data.ts";
import { MissingKey, systemPrompt, translateStrings } from "./translate.ts";

test("the text of a data file goes out and comes back by its place", () => {
  for (const unit of dataUnits()) {
    const planned = planData("nl", unit);
    const todo = planned.strings.filter((string) => string.kept === undefined);
    const back = unmaskData(planned, maskData(planned));

    assert.equal(back.size, todo.length, unit);
    for (const string of todo) {
      assert.equal(
        back.get(string.id),
        string.english,
        `${unit}: ${string.id}`,
      );
    }
  }
});

test("only text is taken from a data file, never an icon or a link", () => {
  const planned = planData("nl", "answers.yml");

  assert.ok(planned.strings.length > 10);
  for (const string of planned.strings) {
    assert.doesNotMatch(String(string.path.at(-1)), /^(icon|to|screenshot)$/);
    assert.doesNotMatch(string.english, /^i-mdi-/);
  }
});

test("a string that lost its placeholder is not written", () => {
  const planned = planData("nl", "tour/repairs.yml");
  const victim = planned.strings.find((string) =>
    /\{[a-z]+\}/.test(string.english),
  )!;
  const translations = new Map(
    planned.strings.map((string) => [string.id, string.english]),
  );
  translations.set(victim.id, victim.english.replace(/\{[a-z]+\}/, "veel"));

  const result = assembleData(planned, translations, "test", { write: false });
  assert.equal(result.written, false);
  assert.match(result.errors.join("\n"), /placeholders differ/);
});

test("without a key the model path says so, and says what still works", async () => {
  const key = process.env.ANTHROPIC_API_KEY;
  delete process.env.ANTHROPIC_API_KEY;
  try {
    await assert.rejects(
      translateStrings("nl", "locale", "⟦S1⟧ Search"),
      (error: Error) =>
        error instanceof MissingKey &&
        /ANTHROPIC_API_KEY is not set/.test(error.message),
    );
  } finally {
    if (key !== undefined) {
      process.env.ANTHROPIC_API_KEY = key;
    }
  }
});

test("the prompt carries the corpus of the language", () => {
  const prompt = systemPrompt("nl", "translate");

  assert.match(prompt, /into Dutch/);
  assert.match(prompt, /Never "u" or "uw"/);
  assert.match(prompt, /"Home Assistant" in full/);
  assert.doesNotMatch(prompt, /\{language\}/);
  assert.match(systemPrompt("de", "review"), /Never "Sie" or "Ihr"/);
});
