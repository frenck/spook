import { defineNuxtModule } from "@nuxt/kit";

type Element = [string, Record<string, unknown>, ...Node[]];
type Node = string | Element;

function isElement(node: Node | undefined, tag?: string): node is Element {
  return Array.isArray(node) && (!tag || node[0] === tag);
}

function childrenOf(node: Element): Node[] {
  return node.slice(2) as Node[];
}

// A cell holding nothing but bold text, like `**Attribute**`.
function boldOnly(cell: Element): boolean {
  const children = childrenOf(cell);
  return children.length === 1 && isElement(children[0], "strong");
}

function unbold(cell: Element): Element {
  const [tag, props, ...children] = cell;
  const inner = children.flatMap((child) =>
    isElement(child, "strong") ? childrenOf(child) : [child],
  );
  return [tag, props, ...inner];
}

/**
 * Give tables their title back.
 *
 * Markdown tables have exactly one header row, with a cell per column. The
 * property and parameter tables carry a title above their columns, like
 * "Action properties", which Markdown can only put in the first header cell
 * with the rest left empty. Here that title becomes one cell across the whole
 * table, and a bold first row below it (the column names) becomes a second
 * header row, which is what these tables looked like on the old site.
 */
export default defineNuxtModule({
  meta: { name: "table-titles" },
  setup(_options, nuxt) {
    nuxt.hook("content:file:afterParse", ({ content }) => {
      const body = content.body as { type?: string; value?: Node[] };
      if (body?.type !== "minimark" || !body.value) {
        return;
      }

      const visit = (node: Node): void => {
        if (!isElement(node)) {
          return;
        }

        if (node[0] !== "table") {
          childrenOf(node).forEach(visit);
          return;
        }

        const head = childrenOf(node).find((child) =>
          isElement(child, "thead"),
        );
        const tbody = childrenOf(node).find((child) =>
          isElement(child, "tbody"),
        );
        const titleRow = head && (childrenOf(head as Element)[0] as Node);
        if (!isElement(titleRow, "tr")) {
          return;
        }

        const [first, ...rest] = childrenOf(titleRow) as Element[];
        const isTitle =
          first &&
          rest.length > 0 &&
          childrenOf(first).length > 0 &&
          rest.every((cell) => childrenOf(cell).length === 0);
        if (!isTitle) {
          return;
        }

        titleRow.splice(
          2,
          titleRow.length - 2,
          unbold([
            first[0],
            { ...first[1], colspan: rest.length + 1 },
            ...childrenOf(first),
          ]),
        );

        const columns = isElement(tbody) && (childrenOf(tbody)[0] as Node);
        if (isElement(columns, "tr")) {
          const cells = childrenOf(columns) as Element[];
          if (cells.length && cells.every(boldOnly)) {
            (tbody as Element).splice(2, 1);
            (head as Element).push([
              "tr",
              {},
              ...cells.map((cell) =>
                unbold(["th", cell[1], ...childrenOf(cell)]),
              ),
            ]);
          }
        }
      };

      body.value.forEach(visit);
    });
  },
});
