import { parseMarkdown } from "@nuxtjs/mdc/runtime";

/**
 * The latest releases of Spook with their notes, for the What's new page.
 *
 * Fetched once while the site is built and saved as a static file, like the
 * stats. When GitHub cannot be reached the list is empty, and the page points
 * at GitHub instead: no release notes beat made-up or stale ones.
 */

interface Release {
  version: string;
  date: string;
  url: string;
  // The notes, already turned from Markdown into what the page renders. Done
  // here, while the site is built: the finished site is static files, with
  // nothing behind it to do this when somebody opens the page.
  notes: unknown;
}

// How many releases the page shows. The rest is one link away, on GitHub.
const SHOWN = 8;

/**
 * Release notes are written for GitHub, and carry things that belong there:
 *
 * - the ask for a star and the rows of ghosts that open and close them;
 * - Frenck's signature, a row of social icons in HTML and a newsletter line,
 *   which on this page would be a column of loose icons;
 * - the list of dependency updates, which no reader of this page needs.
 *
 * What is left starts at the news and ends with "../Frenck".
 */
function forThisPage(notes: string): string {
  return (
    notes
      .replace(/\r\n/g, "\n")
      .replace(/^Enjoying Spook\?.*$/m, "")
      .replace(/^#\s*(?:👻\s*)+$/gm, "")
      // The signature: everything from the icons up to the newsletter line.
      .replace(/\n<p>\s*<a [\s\S]*?<\/p>\s*/g, "\n")
      .replace(
        /^Blogging my personal ramblings.*\n(?:Or subscribe.*\n?)?/gm,
        "",
      )
      // Dependency updates: a heading and its list, up to the next heading.
      .replace(
        /^#{1,3} ⬆️ Dependency updates\n[\s\S]*?(?=^#{1,3} |(?![\s\S]))/gm,
        "",
      )
      // On the page, the version is the heading. What the notes call a
      // heading goes one or two levels down, below it.
      .replace(/^#{1,3} /gm, "### ")
      // Contributor avatars come without a description. They are decoration.
      .replace(/<img (?![^>]*\balt=)/g, '<img alt="" ')
      .trim()
  );
}

export default defineCachedEventHandler(
  async (): Promise<Release[]> => {
    try {
      const data = await $fetch<
        {
          tag_name?: string;
          published_at?: string;
          html_url?: string;
          body?: string;
          draft?: boolean;
          prerelease?: boolean;
        }[]
      >(
        `https://api.github.com/repos/frenck/spook/releases?per_page=${SHOWN}`,
        {
          headers: { Accept: "application/vnd.github+json" },
        },
      );

      const published = data
        .filter((release) => !release.draft && !release.prerelease)
        .filter((release) => release.tag_name && release.published_at);

      return await Promise.all(
        published.map(async (release) => {
          const parsed = await parseMarkdown(forThisPage(release.body ?? ""), {
            highlight: false,
          });

          return {
            version: release.tag_name!,
            date: release.published_at!,
            url: release.html_url!,
            notes: parsed.body,
          };
        }),
      );
    } catch {
      return [];
    }
  },
  { maxAge: 60 * 60 },
);
