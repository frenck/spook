import { defineNuxtModule } from "@nuxt/kit";

type Node = string | [string, Record<string, unknown>, ...Node[]];

// MDC only reads `:term[...]` as a component after a space, a line break,
// `[`, `(`, `*` or `_`. Right after a letter it stays text, and the reader
// sees `:term[集成]{to="integration"}`. Chinese writes no space before a word,
// French writes `l':term[...]`, German `Spook-:term[...]`.
const GLUED = /(?<=[^\s[(*_]):term\[/g;

// What goes in front of such a term for MDC's sake: a space, with an
// invisible separator before it, so the space can be told apart from one the
// text really has, and taken out again once the page is parsed.
const MARK = "⁣ ";

/** Take the marked spaces out of every bit of text in a parsed page. */
function unmark(node: Node): Node {
  if (typeof node === "string") {
    return node.replaceAll(MARK, "");
  }

  const [tag, props, ...children] = node;
  return [tag, props, ...children.map(unmark)];
}

/**
 * Make a glossary term work wherever it is in a sentence.
 *
 * The English docs always have a space before a term. Translations often
 * do not, and the term would show as its raw syntax. Before a page is
 * parsed, a space goes in front of every term glued to the word before it;
 * after, that space comes out again, so the page reads as it was written.
 *
 * The `0.` in the file name makes this the first module: the other modules
 * that read the parsed page, like `page-features.ts`, must see it clean.
 */
export default defineNuxtModule({
  meta: { name: "term-boundaries" },
  setup(_options, nuxt) {
    nuxt.hook("content:file:beforeParse", ({ file }) => {
      if (file.id.endsWith(".md")) {
        file.body = file.body.replace(GLUED, `${MARK}:term[`);
      }
    });

    nuxt.hook("content:file:afterParse", ({ content }) => {
      const body = content.body as { type?: string; value: Node[] } | undefined;
      if (body?.type === "minimark") {
        body.value = body.value.map(unmark);
      }
    });
  },
});
