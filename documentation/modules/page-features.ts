import { defineNuxtModule } from "@nuxt/kit";

type Node = string | [string, Record<string, unknown>, ...Node[]];

// What an integration page can offer, by the anchor of the heading it is
// listed under. The anchor, not the text: a translated page says "Reparaties",
// and still has `repairs` as its anchor.
const FEATURES: Record<string, string> = {
  repairs: "repairs",
  actions: "actions",
  "devices-entities": "entities",
};

function textOf(node: Node): string {
  if (typeof node === "string") {
    return node;
  }

  const [, , ...children] = node;
  return children.map(textOf).join("");
}

/**
 * Note what each page offers, for the integration catalog to filter on.
 *
 * Every integration page has a Repairs, an Actions and a Devices & entities
 * section, also when there is nothing in it ("Spook does not provide any new
 * devices"). A section counts when it has at least one entry below it.
 *
 * Every repair is kept by name too, with its anchor and what it says is
 * wrong, for the page that lists all of them.
 *
 * Alongside, each page gets how many entries it has per section, and how many
 * top-level sections it has at all. On the reference pages every section is
 * one action, trigger or condition, which is what the home page counts.
 */
export default defineNuxtModule({
  meta: { name: "page-features" },
  setup(_options, nuxt) {
    nuxt.hook("content:file:afterParse", ({ content }) => {
      const body = content.body as { type?: string; value?: Node[] };
      if (body?.type !== "minimark" || !body.value) {
        return;
      }

      const counts: Record<string, number> = {};
      const repairs: { id: string; title: string; summary: string }[] = [];
      let sections = 0;
      let current: string | undefined;
      for (const node of body.value) {
        if (typeof node === "string") {
          continue;
        }

        if (node[0] === "h2") {
          sections += 1;
          current = FEATURES[node[1].id as string];
        } else if (node[0] === "h3" && current) {
          counts[current] = (counts[current] ?? 0) + 1;

          if (current === "repairs") {
            repairs.push({
              id: node[1].id as string,
              title: textOf(node).trim(),
              summary: "",
            });
          }
        } else if (node[0] === "p" && current === "repairs") {
          // What is wrong, in a line or two: the first paragraph of a repair.
          const repair = repairs.at(-1);
          if (repair && !repair.summary) {
            repair.summary = textOf(node).trim();
          }
        }
      }

      content.meta = {
        ...(content.meta as object),
        offers: Object.keys(counts),
        counts,
        repairs,
        sections,
      };
    });
  },
});
