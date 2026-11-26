/**
 * The screenshots, one language at a time.
 *
 * Every language gets a Home Assistant of its own, onboarded in that
 * language, so the names Home Assistant translates itself come out right,
 * next to the names of the home in seed/names/<language>.yml. One at a
 * time: they all use the same container and port.
 *
 *   npm run screenshots                     # English
 *   LANGUAGES=en,nl,de npm run screenshots  # one after the other
 *   KEEP=1 npm run screenshots              # leave the last one running
 *
 * Anything after `--` goes to Playwright, like `-- -g repair` for only
 * the repair shots.
 */
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

const languages = (process.env.LANGUAGES ?? "en")
  .split(",")
  .map((language) => language.trim())
  .filter(Boolean);

const failed: string[] = [];

for (const [index, language] of languages.entries()) {
  const last = index === languages.length - 1;
  const started = Date.now();
  console.log(`\n👻 ${language}: ${index + 1} of ${languages.length}\n`);

  const run = spawnSync(
    "npx",
    [
      "playwright",
      "test",
      "--config",
      join(here, "playwright.config.ts"),
      ...process.argv.slice(2),
    ],
    {
      stdio: "inherit",
      env: {
        ...process.env,
        SCREENSHOTS_LANGUAGE: language,
        // Only the last one stays, the next language replaces the others.
        KEEP: last ? (process.env.KEEP ?? "") : "",
      },
    },
  );

  const minutes = ((Date.now() - started) / 60_000).toFixed(1);
  console.log(`\n👻 ${language}: done in ${minutes} minutes\n`);
  // One shot that fails in one language is no reason to skip the others.
  if (run.status !== 0) {
    failed.push(language);
  }
}

if (failed.length) {
  console.error(`👻 Shots failed in: ${failed.join(", ")}`);
  process.exit(1);
}
