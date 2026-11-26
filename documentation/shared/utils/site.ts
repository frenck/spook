/** Where the site lives. Canonical addresses and structured data use it. */
export const SITE_URL = "https://spook.boo";

/** An address on the site, written out in full: `/automation` to `https://spook.boo/automation`. */
export function siteUrl(path: string): string {
  return path === "/" ? `${SITE_URL}/` : `${SITE_URL}${path}`;
}
