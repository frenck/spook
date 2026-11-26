/**
 * The model calls: one to translate a section, one to review it.
 *
 * Everything the model is told comes from the corpus. The instructions, the
 * voice, the style guide and the examples of a language are the same for
 * every section, so they go first and are cached. What differs per section
 * (its glossary entries, its pinned corrections, the text) goes last.
 *
 * The model never gets the last word: `verify.ts` checks what comes back,
 * and a section that fails is asked for once more, with the reasons.
 */
import Anthropic from "@anthropic-ai/sdk";

import { corpus, language, settings } from "./config.ts";
import type { Planned } from "./assemble.ts";
import { verifySection } from "./verify.ts";

export class MissingKey extends Error {
  constructor() {
    super(
      [
        "ANTHROPIC_API_KEY is not set, so there is no model to translate with.",
        "Set it and run again. Everything else works without one:",
        "  glossary, verify, sync --dry-run, export and import.",
      ].join("\n"),
    );
  }
}

/** A section the model would not, or could not, finish. */
export class Unfinished extends Error {}

let shared: Anthropic | undefined;

function client(): Anthropic {
  if (!process.env.ANTHROPIC_API_KEY) {
    throw new MissingKey();
  }
  shared ??= new Anthropic();
  return shared;
}

/** What is the same for every section of a language. Cached by the API. */
export function systemPrompt(
  lang: string,
  task: "translate" | "review",
): string {
  const { name } = language(lang);
  return [
    corpus("prompt", `${task}.md`).replaceAll("{language}", name),
    "# The voice, for every language",
    corpus("style", "_shared.md"),
    `# Style guide: ${name}`,
    corpus(lang, "style.md"),
    "# Never translated",
    corpus("do-not-translate.yml"),
    `# Jokes: ${name}`,
    corpus(lang, "jokes.yml"),
    `# Examples of good translations: ${name}`,
    corpus(lang, "examples.md"),
  ].join("\n\n");
}

function pairs(entries: Record<string, string>): string {
  return Object.entries(entries)
    .map(([english, translation]) => `- ${english} => ${translation}`)
    .join("\n");
}

/** What differs per section. */
export function sectionPrompt(
  page: string,
  planned: Planned,
  previous?: string,
  problems: string[] = [],
): string {
  const parts = [`Page: ${page}`, `Section: ${planned.section.id}`];

  if (Object.keys(planned.used.labels).length) {
    parts.push(
      "Labels. Bold text that matches the left side becomes exactly the right side, in bold:",
      pairs(planned.used.labels),
    );
  }
  if (planned.used.unknown.length) {
    parts.push(
      "Bold text nobody has a label for. Keep it in English when it is something on the screen. Translate it when it is emphasis:",
      planned.used.unknown.map((label) => `- ${label}`).join("\n"),
    );
  }
  if (Object.keys(planned.used.terms).length) {
    parts.push("Terms. Use these words:", pairs(planned.used.terms));
  }
  if (planned.rules.corrections.length) {
    parts.push(
      "Pinned. The translation has to contain these sentences as written:",
      planned.rules.corrections.map((line) => `- ${line}`).join("\n"),
    );
  }
  if (previous) {
    parts.push(
      "The translation this section had before the English changed. Keep every sentence whose English did not change:",
      `<previous>\n${previous}\n</previous>`,
    );
  }
  if (problems.length) {
    parts.push(
      "Your last answer failed these checks. Fix exactly these:",
      problems.map((problem) => `- ${problem}`).join("\n"),
    );
  }

  parts.push(`<section>\n${planned.section.masked}\n</section>`);
  return parts.join("\n\n");
}

async function ask(
  model: string,
  system: string,
  user: string,
): Promise<string> {
  const stream = client().messages.stream({
    model,
    max_tokens: 32000,
    thinking: { type: "adaptive" },
    output_config: { effort: settings().models.effort },
    system: [
      { type: "text", text: system, cache_control: { type: "ephemeral" } },
    ],
    messages: [{ role: "user", content: user }],
  });
  const message = await stream.finalMessage();

  // A refusal or a cut-off answer is a failed section: keep what was there.
  if (message.stop_reason !== "end_turn") {
    throw new Unfinished(`the model stopped with "${message.stop_reason}"`);
  }

  return message.content
    .flatMap((block) => (block.type === "text" ? [block.text] : []))
    .join("");
}

function sectionOf(answer: string): string {
  const tagged = answer.match(/<section>\n?([\s\S]*?)\n?<\/section>/);
  return tagged ? tagged[1]! : answer.trim();
}

export interface Outcome {
  masked?: string;
  model: string;
  /** Why there is no translation, or what the reviewer still doubts. */
  notes: string[];
}

/**
 * Translate one section: ask, check, ask once more when a check fails, then
 * let the reviewer read it. Returns no translation when it cannot be trusted.
 */
export async function translateSection(
  lang: string,
  page: string,
  planned: Planned,
  previous?: string,
): Promise<Outcome> {
  const { models } = settings();
  const system = systemPrompt(lang, "translate");
  const notes: string[] = [];

  let masked: string | undefined;
  let problems: string[] = [];

  try {
    for (let attempt = 0; attempt < 2; attempt++) {
      const answer = await ask(
        models.translate,
        system,
        sectionPrompt(page, planned, previous, problems),
      );
      masked = sectionOf(answer);
      problems = verifySection(planned.section, masked, planned.rules);
      if (!problems.length) {
        break;
      }
    }

    if (problems.length || masked === undefined) {
      return { model: models.translate, notes: problems };
    }

    // The second reader: a different model, with a different question.
    const verdict = await ask(
      models.review,
      systemPrompt(lang, "review"),
      [
        `<english>\n${planned.section.masked}\n</english>`,
        `<translation>\n${masked}\n</translation>`,
      ].join("\n\n"),
    );
    if (!/^OK\b/.test(verdict.trim())) {
      const retry = sectionOf(
        await ask(
          models.translate,
          system,
          sectionPrompt(page, planned, masked, [
            `A reviewer read your translation and says:\n${verdict.trim()}`,
          ]),
        ),
      );
      if (!verifySection(planned.section, retry, planned.rules).length) {
        masked = retry;
      }
      notes.push(`reviewer flagged this section: ${verdict.trim()}`);
    }
  } catch (error) {
    if (error instanceof MissingKey) {
      throw error;
    }
    if (error instanceof Unfinished) {
      return { model: models.translate, notes: [error.message] };
    }
    if (error instanceof Anthropic.RateLimitError) {
      return {
        model: models.translate,
        notes: ["rate limited, try again later"],
      };
    }
    if (error instanceof Anthropic.APIError) {
      return {
        model: models.translate,
        notes: [`the API answered ${error.status}: ${error.message}`],
      };
    }
    throw error;
  }

  return { masked, model: models.translate, notes };
}

/** Translate loose strings, like the site's own interface text. */
export async function translateStrings(
  lang: string,
  file: string,
  masked: string,
  problems: string[] = [],
): Promise<string> {
  const parts = [
    `File: ${file}`,
    "These are separate strings, one per line. Keep every line, its token at the start, and anything in {braces}.",
  ];
  if (problems.length) {
    parts.push(
      "Your last answer failed these checks. Fix exactly these:",
      problems.map((problem) => `- ${problem}`).join("\n"),
    );
  }
  parts.push(`<section>\n${masked}\n</section>`);

  return sectionOf(
    await ask(
      settings().models.translate,
      systemPrompt(lang, "translate"),
      parts.join("\n\n"),
    ),
  );
}
