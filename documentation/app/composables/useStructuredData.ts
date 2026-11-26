/**
 * Structured data (JSON-LD): the facts of a page in a form search engines
 * and AI assistants read without guessing. Who makes Spook, what it costs,
 * where a page sits in the docs.
 *
 * Every page describes the site and its maker the same way, under the same
 * `@id`, so the pieces add up to one picture instead of a pile of copies.
 */

export const SPOOK_ID = `${SITE_URL}/#spook`;
const WEBSITE_ID = `${SITE_URL}/#website`;
const FRENCK_ID = `${SITE_URL}/#frenck`;

export type StructuredNode = Record<string, unknown>;

/** Frenck, who makes Spook. */
export const frenckNode: StructuredNode = {
  "@type": "Person",
  "@id": FRENCK_ID,
  name: "Franck Nijhof",
  alternateName: "Frenck",
  url: "https://frenck.dev",
  // His own profiles elsewhere, so search engines and assistants know which
  // Frenck this is.
  sameAs: [
    "https://github.com/frenck",
    "https://fosstodon.org/@frenck",
    "https://bsky.app/profile/frenck.social",
    "https://www.linkedin.com/in/frenck/",
    "https://youtube.com/@frenck",
  ],
};

/** The site itself, in the language being read. */
export function websiteNode(language: string): StructuredNode {
  return {
    "@type": "WebSite",
    "@id": WEBSITE_ID,
    name: "Spook",
    url: siteUrl("/"),
    inLanguage: language,
    publisher: { "@id": FRENCK_ID },
  };
}

/** Plain text for structured data: Markdown links and emphasis taken out. */
export function plainText(text: string): string {
  return text
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[*_`]/g, "")
    .trim();
}

/** Put structured data on the page, as one graph. */
export function useStructuredData(graph: () => StructuredNode[]) {
  useHead({
    script: [
      {
        key: "structured-data",
        type: "application/ld+json",
        // `<` written out, so text in the data can never close the script.
        innerHTML: computed(() =>
          JSON.stringify({
            "@context": "https://schema.org",
            "@graph": graph(),
          }).replace(/</g, "\\u003c"),
        ),
      },
    ],
  });
}
