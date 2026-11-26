/**
 * Read an integration page into the pieces it is laid out from.
 *
 * The Markdown stays the source, with every repair a `###` heading under
 * `## Repairs`: that is what search, the counts, the plain Markdown copy and
 * the documentation tests read, and what released versions of Spook link to.
 * Only the page itself shows the repairs as rows to open.
 */

type Node = string | [string, Record<string, unknown>, ...Node[]];

interface Body {
  type?: string;
  value?: Node[];
}

export interface IntegrationRepair {
  // The heading's anchor. Every repair in Home Assistant has a "learn more"
  // that points at it, so it is exactly the id the heading had.
  id: string;
  title: string;
  // What is wrong, in a line or two: the first paragraph.
  summary: Node[];
  // How to fix it, and how Spook checks.
  details: Node[];
}

export type IntegrationChunk =
  | { kind: "content"; nodes: Node[] }
  | { kind: "repairs"; repairs: IntegrationRepair[] };

function textOf(node: Node): string {
  if (typeof node === "string") {
    return node;
  }

  const [, , ...children] = node;
  return children.map(textOf).join("");
}

/** The integration's logo, when the page opens with one. */
function logoOf(node: Node): string | undefined {
  if (typeof node === "string" || node[0] !== "p" || node.length !== 3) {
    return undefined;
  }

  const image = node[2]!;
  const source =
    typeof image !== "string" && image[0] === "img" && image[1].src;
  return typeof source === "string" &&
    source.startsWith("https://brands.home-assistant.io/")
    ? source
    : undefined;
}

/** Split the body by its `##` headings. */
function sectionsOf(nodes: Node[]) {
  const intro: Node[] = [];
  const sections: { heading: string; nodes: Node[] }[] = [];

  for (const node of nodes) {
    if (typeof node !== "string" && node[0] === "h2") {
      sections.push({ heading: textOf(node).trim(), nodes: [node] });
    } else {
      (sections.at(-1)?.nodes ?? intro).push(node);
    }
  }

  return { intro, sections };
}

/** Split what is under `## Repairs` into what it opens with, and the repairs. */
function repairsOf(nodes: Node[]) {
  const before: Node[] = [];
  const repairs: IntegrationRepair[] = [];

  for (const node of nodes) {
    if (typeof node !== "string" && node[0] === "h3") {
      repairs.push({
        id: node[1].id as string,
        title: textOf(node).trim(),
        summary: [],
        details: [],
      });
      continue;
    }

    const repair = repairs.at(-1);
    if (!repair) {
      before.push(node);
    } else if (!repair.summary.length && !repair.details.length) {
      repair.summary.push(node);
    } else {
      repair.details.push(node);
    }
  }

  return { before, repairs };
}

export function integrationPage(body?: Body): { chunks: IntegrationChunk[] } {
  const { intro, sections } = sectionsOf(body?.value ?? []);

  // The header shows the integration's icon, so the big logo a page opens
  // with would be the same picture twice.
  const chunks: IntegrationChunk[] = [
    { kind: "content", nodes: intro.filter((node) => !logoOf(node)) },
  ];

  for (const section of sections) {
    const [heading, ...rest] = section.nodes as [Node, ...Node[]];
    const id = (heading as [string, Record<string, unknown>])[1].id;

    // Found by its anchor, which is the same in every language.
    if (id !== "repairs") {
      chunks.push({ kind: "content", nodes: section.nodes });
      continue;
    }

    const { before, repairs } = repairsOf(rest);
    chunks.push({ kind: "content", nodes: [heading, ...before] });
    if (repairs.length) {
      chunks.push({ kind: "repairs", repairs });
    }
  }

  return { chunks };
}
