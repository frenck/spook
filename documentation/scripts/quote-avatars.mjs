/**
 * The avatars next to the quotes on the home page.
 *
 *   npm run quote-avatars              # fetch the ones that are missing
 *   npm run quote-avatars -- --refresh # fetch them all again
 *
 * Every quote in content/data/quotes.yml names where its author's avatar is.
 * This keeps a small copy of each in public/images/quotes/, so a visitor's
 * browser never calls the forum, GitHub or Mastodon, and an avatar that
 * changes or disappears there does not break the page.
 *
 * It fetches through the Chrome on this machine: the Home Assistant forum
 * turns plain HTTP clients away.
 */
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import sharp from "sharp";
import { parse } from "yaml";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const folder = join(root, "public", "images", "quotes");
const refresh = process.argv.includes("--refresh");

// The same name app/components/home/HomeQuotes.vue looks for.
const fileName = (quote) =>
  `${`${quote.platform}-${quote.author}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")}.webp`;

const { quotes } = parse(
  readFileSync(join(root, "content", "data", "quotes.yml"), "utf-8"),
);
mkdirSync(folder, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();
const wanted = new Set();

for (const quote of quotes) {
  if (!quote.avatar) {
    continue;
  }
  const file = fileName(quote);
  wanted.add(file);
  if (existsSync(join(folder, file)) && !refresh) {
    continue;
  }

  const response = await page.goto(quote.avatar);
  if (!response?.ok()) {
    console.warn(`No avatar for ${quote.author}: ${response?.status()}`);
    continue;
  }
  await sharp(await response.body())
    .resize(96, 96, { fit: "cover" })
    .webp({ quality: 82 })
    .toFile(join(folder, file));
  console.log(`${quote.author} → ${file}`);
}
await browser.close();

// An avatar no quote uses anymore goes too.
for (const file of readdirSync(folder)) {
  if (!wanted.has(file)) {
    rmSync(join(folder, file));
    console.log(`removed ${file}`);
  }
}
