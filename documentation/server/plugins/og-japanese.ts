/**
 * Japanese share cards draw their kanji with Noto Sans JP.
 *
 * A card takes a character from the first font that has it. Noto Sans SC
 * comes before Noto Sans JP in `nuxt.config.ts`, so Chinese cards keep
 * Chinese shapes; on a Japanese card that would draw its kanji the Chinese
 * way. So on a Japanese card, Noto Sans JP goes right after the Latin face of
 * every text, before the Chinese font gets a chance.
 *
 * The language comes from the path of the page the card is for, which
 * nuxt-og-image hands the hook as `basePath`: the pages do not pass their
 * language to the card.
 */
import { languageOf } from "../../shared/utils/languages";

const JAPANESE_FONT = "Noto Sans JP";

interface CardNode {
  style?: { fontFamily?: string };
  children?: unknown[];
}

function preferJapanese(node: CardNode) {
  const fontFamily = node.style?.fontFamily;
  if (fontFamily && !fontFamily.includes(JAPANESE_FONT)) {
    const [latin, ...rest] = fontFamily.split(",");
    node.style!.fontFamily = [latin, `"${JAPANESE_FONT}"`, ...rest].join(",");
  }

  for (const child of node.children ?? []) {
    if (child && typeof child === "object") {
      preferJapanese(child as CardNode);
    }
  }
}

export default defineNitroPlugin((nitroApp) => {
  // The hook is nuxt-og-image's, and not in Nitro's list of hooks.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (nitroApp.hooks as any).hook(
    "nuxt-og-image:takumi:nodes",
    (nodes: CardNode, event: { basePath?: string }) => {
      if (languageOf(event.basePath ?? "/") === "ja") {
        preferJapanese(nodes);
      }
    },
  );
});
