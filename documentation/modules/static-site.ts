import { defineNuxtModule, useLogger } from "@nuxt/kit";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, relative } from "node:path";

const logger = useLogger("static-site");

// What nuxt-agent-discovery says at the top of `sitemap.md`. True on a
// server it runs on, not on GitHub Pages: that has no content negotiation,
// so `Accept: text/markdown` gets the HTML.
const SITEMAP_PROMISE = /^> Markdown index of every page on .*$/m;

/** The top of `sitemap.md`, saying only what the static site does. */
export function honestSitemap(markdown: string, hostname: string): string {
  return markdown.replace(
    SITEMAP_PROMISE,
    `> Markdown index of every page on ${hostname}. Every link is the Markdown of a page. The same file is also at the address of the page with \`.md\` added: \`/automation.md\` for \`/automation\`.`,
  );
}

/** A redirect page, with a canonical link to where it sends people. */
export function withCanonical(html: string, href: string): string {
  return html.replace("<head>", `<head><link rel="canonical" href="${href}">`);
}

/** Every file below a directory, by its path in it. */
function filesIn(directory: string): string[] {
  return readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => relative(directory, join(entry.parentPath, entry.name)));
}

/**
 * What the site needs to be on GitHub Pages, done to the built files once
 * every page is written. Pages serves files and nothing else: no headers,
 * no redirects, no content negotiation.
 *
 * - The Markdown of every page next to it, `/automation.md`, and not only
 *   under `/raw`. Agents try that address, and `sitemap.md` says it is
 *   there. What it said about `Accept: text/markdown` is taken out.
 * - No `200.html`. Nuxt writes it as a fallback for hosts that use one;
 *   Pages uses `404.html`. Served as an ordinary page, it would be the app
 *   shell, without a title, at an address nobody links to.
 * - The old addresses (`/features`) are a page that sends you on. Search
 *   engines get a canonical link to where.
 */
export default defineNuxtModule({
  meta: { name: "static-site" },
  setup(_options, nuxt) {
    if (nuxt.options.dev) {
      return;
    }

    const site = (nuxt.options as { site?: { url?: string } }).site?.url;
    if (!site) {
      throw new Error("[static-site] needs `site.url` in `nuxt.config.ts`.");
    }

    nuxt.hook("nitro:init", (nitro) => {
      nitro.hooks.hook("prerender:done", () => {
        const output = nitro.options.output.publicDir;

        rmSync(join(output, "200.html"), { force: true });

        const raw = join(output, "raw");
        if (existsSync(raw)) {
          for (const file of filesIn(raw)) {
            const copy = join(output, file);
            if (existsSync(copy)) {
              logger.warn(
                `\`/${file}\` exists already, so the Markdown copy of it stays under \`/raw\` only.`,
              );
              continue;
            }

            mkdirSync(dirname(copy), { recursive: true });
            copyFileSync(join(raw, file), copy);
          }
        }

        const sitemap = join(output, "sitemap.md");
        if (existsSync(sitemap)) {
          const before = readFileSync(sitemap, "utf-8");
          const after = honestSitemap(before, new URL(site).hostname);
          if (after === before) {
            logger.warn(
              "The top of `sitemap.md` changed in nuxt-agent-discovery, check what it promises now.",
            );
          }

          writeFileSync(sitemap, after);
        }

        for (const [route, rule] of Object.entries(nitro.options.routeRules)) {
          const to = rule.redirect?.to;
          const page = join(output, `${route}.html`);
          if (!to || route.includes("*") || !existsSync(page)) {
            continue;
          }

          writeFileSync(
            page,
            withCanonical(readFileSync(page, "utf-8"), new URL(to, site).href),
          );
        }
      });
    });
  },
});
