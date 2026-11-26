import { defineNuxtModule } from "@nuxt/kit";
import { anchor } from "../shared/utils/anchor";

type Node = string | [string, Record<string, unknown>, ...Node[]];

interface TocLink {
  id: string;
  text: string;
  children?: TocLink[];
}

interface Body {
  type: string;
  value: Node[];
  toc?: { links: TocLink[] };
}

// A heading can carry the anchor of a label it used to have, like
// `## MIT License {#mit}`, when that label is what people link to.
const EXPLICIT = /\s*\{#([a-z0-9-]+)\}\s*$/;

function textOf(node: Node): string {
  if (typeof node === "string") {
    return node;
  }

  const [, , ...children] = node;
  return children.map(textOf).join("");
}

function stripExplicit(node: Node): void {
  if (typeof node === "string") {
    return;
  }

  const last = node.length - 1;
  const child = node[last];
  if (typeof child === "string") {
    node[last] = child.replace(EXPLICIT, "");
  } else if (last >= 2) {
    stripExplicit(child as Node);
  }
}

/**
 * Give every heading the anchor MyST gave it, before Docus renders it.
 *
 * The heading itself, the table of contents and search all read the id from
 * the parsed page, so changing it here changes it everywhere at once.
 */
export default defineNuxtModule({
  meta: { name: "myst-anchors" },
  setup(_options, nuxt) {
    nuxt.hook("content:file:afterParse", ({ content }) => {
      const body = content.body as Body | undefined;
      if (body?.type !== "minimark") {
        return;
      }

      const renamed = new Map<string, { id: string; text: string }>();
      const seen = new Map<string, number>();

      const visit = (node: Node): void => {
        if (typeof node === "string") {
          return;
        }

        const [tag, props, ...children] = node;
        if (!/^h[2-6]$/.test(tag)) {
          children.forEach(visit);
          return;
        }

        let text = textOf(node);
        let id = anchor(text);

        const explicit = text.match(EXPLICIT);
        if (explicit) {
          text = text.replace(EXPLICIT, "");
          id = explicit[1]!;
          stripExplicit(node);
        }

        // MyST numbers repeats the same way: the second one gets `-1`.
        const count = seen.get(id) ?? 0;
        seen.set(id, count + 1);
        if (count) {
          id = `${id}-${count}`;
        }

        renamed.set(props.id as string, { id, text });
        props.id = id;
      };

      body.value.forEach(visit);

      const relink = (links: TocLink[] = []): void => {
        for (const link of links) {
          const heading = renamed.get(link.id);
          if (heading) {
            link.id = heading.id;
            link.text = heading.text;
          }
          relink(link.children);
        }
      };

      relink(body.toc?.links);
    });
  },
});
