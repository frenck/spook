import {
  addTemplate,
  addTypeTemplate,
  defineNuxtModule,
  useLogger,
} from "@nuxt/kit";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

/**
 * When each file was last changed, from `git log` output made with
 * `--format=%x00%cI --name-only`: every commit is a NUL, its date, and the
 * files it touched. Newest first, so the first date seen for a file is the
 * one that counts.
 */
export function parseGitLog(output: string): Record<string, string> {
  const dates: Record<string, string> = {};

  for (const commit of output.split("\0").slice(1)) {
    const [date, ...files] = commit.split("\n");
    for (const file of files) {
      if (file && !(file in dates)) {
        dates[file] = date!.trim();
      }
    }
  }

  return dates;
}

/**
 * The date of the last commit that changed each file below `directory`, by
 * its path in there. One `git log` for all of them.
 *
 * Nothing at all when that can't be told: outside a Git checkout, or in a
 * shallow clone, where every file would get the date of the one commit
 * there is. A file nobody committed yet has no date either.
 */
export function lastChanged(directory: string): Record<string, string> {
  const git = (...args: string[]) =>
    execFileSync("git", args, {
      cwd: directory,
      encoding: "utf-8",
      maxBuffer: 64 * 1024 * 1024,
      stdio: ["ignore", "pipe", "ignore"],
    });

  try {
    if (git("rev-parse", "--is-shallow-repository").trim() === "true") {
      return {};
    }

    return parseGitLog(
      git("log", "--format=%x00%cI", "--name-only", "--relative", "--", "."),
    );
  } catch {
    return {};
  }
}

/**
 * When each docs page last changed, as `#build/page-dates.mjs`: the commit
 * date of its Markdown file, by the file's path in `content/`. That is
 * `stem.extension` of a page, the same path its "Edit this page" link uses.
 *
 * Search engines and assistants use it to tell a fresh page from a stale
 * one, so it is the date the text changed. Never the date of the build: that
 * would make every page look new every time, and teach them to ignore it.
 */
export default defineNuxtModule({
  meta: { name: "page-dates" },
  setup(_options, nuxt) {
    const content = fileURLToPath(new URL("../content", import.meta.url));
    const dates = lastChanged(content);

    if (!Object.keys(dates).length && !nuxt.options.dev) {
      useLogger("page-dates").warn(
        "No Git history for `content/` (not committed yet, or a shallow clone), so the pages go without a date.",
      );
    }

    addTemplate({
      filename: "page-dates.mjs",
      getContents: () => `export default ${JSON.stringify(dates)};`,
    });

    addTypeTemplate({
      filename: "types/page-dates.d.ts",
      getContents: () =>
        [
          'declare module "#build/page-dates.mjs" {',
          "  const dates: Record<string, string>;",
          "  export default dates;",
          "}",
        ].join("\n"),
    });
  },
});
