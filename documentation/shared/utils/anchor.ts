/**
 * Turn a heading, or a glossary term, into the anchor MyST gave it.
 *
 * Spook releases out in the wild link straight to these anchors (every repair
 * has a "learn more" pointing at its heading), so they stay exactly what they
 * were when this site was still built with MyST. Docus would otherwise drop
 * punctuation instead of replacing it, and turn "min/max" into "minmax".
 */
export function anchor(text: string): string {
  return text
    .toLowerCase()
    .replace(/['’]/g, "")
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/^([0-9-])/, "id-$1")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "");
}
