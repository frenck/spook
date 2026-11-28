/**
 * Fails when the dashboard bundle gets too big to load on every page.
 *
 * Every user downloads the entry on every page, whether a dashboard of
 * theirs uses Spook or not. What an element loads later with `import()`
 * lands in a chunk of its own and does not count here: it only loads when
 * that element is on screen.
 *
 * Run it after `npm run build`.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const BUDGET_IN_KB = 30;

const entry = fileURLToPath(
  new URL(
    "../../custom_components/spook/static/dashboard/spook.js",
    import.meta.url,
  ),
);

let source: Buffer;
try {
  source = readFileSync(entry);
} catch {
  console.error(`No dashboard bundle at ${entry}. Run npm run build first.`);
  process.exit(1);
}

const sizeInKb = gzipSync(source, { level: 9 }).length / 1024;
const summary = `spook.js is ${sizeInKb.toFixed(2)} KB gzipped, the budget is ${BUDGET_IN_KB} KB`;

if (sizeInKb > BUDGET_IN_KB) {
  console.error(
    `${summary}. Move what is heavy behind an import() in the element that needs it.`,
  );
  process.exit(1);
}

console.log(`${summary}.`);
