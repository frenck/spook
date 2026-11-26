/**
 * Screenshots of Spook in a real, current Home Assistant, for the website.
 *
 * A manual run, not part of CI. `npm run screenshots` starts run.ts, which
 * runs this once per language, each with a Home Assistant of its own.
 *
 * Every shot is taken in light and in dark, and written to
 * public/images/screenshots/<language>/<light|dark>/<name>.webp.
 */
import { defineConfig } from "@playwright/test";
import { BASE_URL, LANGUAGE } from "./home-assistant";

const themes = ["light", "dark"] as const;

export default defineConfig({
  testDir: ".",
  testMatch: "shots.spec.ts",
  globalSetup: "./setup.ts",
  globalTeardown: "./teardown.ts",
  outputDir: ".state/results",

  timeout: 60_000,
  expect: { timeout: 20_000 },
  fullyParallel: true,
  reporter: [["list"]],

  use: {
    baseURL: BASE_URL,
    // The Chrome installed on the machine, so a Playwright update never
    // means downloading another browser first.
    channel: "chrome",
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 2,
    // The time zone of the home, so a time in an automation reads the way it
    // is written.
    timezoneId: "Europe/Amsterdam",
    reducedMotion: "reduce",
  },

  projects: themes.map((theme) => ({
    name: `${LANGUAGE} ${theme}`,
    metadata: { language: LANGUAGE, theme },
    use: { colorScheme: theme, locale: LANGUAGE },
  })),
});
