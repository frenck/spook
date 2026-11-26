/**
 * Turn a parsed page (a minimark tree) into one that prints as plain
 * Markdown, for the Markdown copies of the pages and `llms-full.txt`.
 *
 * On the site, the components in the docs (`:term[...]`, `::screenshot`,
 * `::accordion` and friends) render into something a person sees. In a
 * Markdown copy, they would print as MDC syntax: noise a model has to guess
 * at. Each one becomes the plain Markdown closest to what it shows.
 */

export type MinimarkNode = string | MinimarkElement;
export type MinimarkElement = [
  string,
  Record<string, unknown>,
  ...MinimarkNode[],
];

// What plain Markdown can print. Anything else is a component.
const MARKDOWN_TAGS = new Set([
  "a",
  "blockquote",
  "br",
  "code",
  "del",
  "em",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "hr",
  "img",
  "input",
  "li",
  "ol",
  "p",
  "pre",
  "strong",
  "style",
  "table",
  "tbody",
  "td",
  "th",
  "thead",
  "tr",
  "ul",
]);

// The callouts, and the word they start with.
const CALLOUTS: Record<string, string> = {
  note: "Note",
  tip: "Tip",
  warning: "Warning",
  caution: "Caution",
  important: "Important",
};

// Components that fill themselves from data, not from the Markdown. The
// copy has nothing to show for them, so it sends the reader to the page.
const DATA_COMPONENTS = new Set([
  "blueprint-list",
  "docs-hub",
  "integration-catalog",
  "media-list",
  "release-notes",
  "repair-index",
]);

// The screenshots in the copies are the English ones, in the light theme.
const SCREENSHOTS = "/images/screenshots/en/light";

function isElement(node: MinimarkNode): node is MinimarkElement {
  return Array.isArray(node);
}

function childrenOf(node: MinimarkElement): MinimarkNode[] {
  return node.slice(2) as MinimarkNode[];
}

/** The contents of a card, as one line: its paragraphs run together. */
function inline(nodes: MinimarkNode[]): MinimarkNode[] {
  return nodes.flatMap((node, index) => {
    const separator = index > 0 ? [" "] : [];
    if (isElement(node) && node[0] === "p") {
      return [...separator, ...childrenOf(node)];
    }

    return [...separator, node];
  });
}

/** A link to a card's page, with what the card says about it. */
function card(node: MinimarkElement, convert: Convert): MinimarkNode[] {
  const { title, to } = node[1] as { title?: string; to?: string };
  const text = inline(convert(childrenOf(node)));
  const link: MinimarkNode = to
    ? ["a", { href: to }, title ?? to]
    : ["strong", {}, title ?? ""];

  return text.length ? [link, ": ", ...text] : [link];
}

/** A callout: a quote that starts with what kind it is, in bold. */
function callout(label: string, children: MinimarkNode[]): MinimarkElement {
  const lead: MinimarkNode[] = [["strong", {}, `${label}:`], " "];
  const [first, ...rest] = children;
  if (first && isElement(first) && first[0] === "p") {
    return [
      "blockquote",
      {},
      ["p", {}, ...lead, ...childrenOf(first)],
      ...rest,
    ];
  }

  return ["blockquote", {}, ["p", {}, ...lead], ...children];
}

type Convert = (nodes: MinimarkNode[]) => MinimarkNode[];

/**
 * The plain Markdown version of a page's nodes. Returns new nodes, and
 * leaves the ones it was given alone.
 *
 * `page` is the address of the page, for components that only exist on it.
 */
export function plainMarkdown(
  nodes: MinimarkNode[],
  { page }: { page: string },
): MinimarkNode[] {
  const convert: Convert = (list) => list.flatMap(one);

  function one(node: MinimarkNode): MinimarkNode[] {
    if (!isElement(node)) {
      return [node];
    }

    const [tag, props] = node;

    // A code block prints from its own source, whatever is inside it.
    if (tag === "pre") {
      return [node];
    }

    // Plain Markdown, with only the attributes Markdown has a place for:
    // `{class="mx-auto"}` after an image is MDC too.
    if (MARKDOWN_TAGS.has(tag)) {
      if (tag === "img") {
        const { src, alt, title } = props;
        return [["img", { src, alt, ...(title ? { title } : {}) }]];
      }

      if (tag === "code") {
        return [["code", {}, ...childrenOf(node)]];
      }

      return [[tag, props, ...convert(childrenOf(node))]];
    }

    const children = convert(childrenOf(node));

    if (tag in CALLOUTS) {
      return [callout(CALLOUTS[tag]!, children)];
    }

    // A word from the glossary: just the word. A link on every one of them
    // would add far more than it tells, and the glossary is a page of its
    // own.
    if (tag === "term") {
      return children;
    }

    if (tag === "screenshot") {
      const { name, alt } = props as { name?: string; alt?: string };
      return [
        ["p", {}, ["img", { src: `${SCREENSHOTS}/${name}.webp`, alt }]],
        ...children,
      ];
    }

    // What sits behind a fold or a tab is all there in the copy, below its
    // label.
    if (tag === "accordion-item" || tag === "tabs-item") {
      const { label } = props as { label?: string };
      return label ? [["p", {}, ["strong", {}, label]], ...children] : children;
    }

    if (tag === "card-group") {
      const cards = childrenOf(node).filter(isElement);
      return [
        [
          "ul",
          {},
          ...cards.map((item): MinimarkNode => [
            "li",
            {},
            ...card(item, convert),
          ]),
        ],
      ];
    }

    if (tag === "card") {
      return [["p", {}, ...card(node, convert)]];
    }

    if (tag === "iframe") {
      const { src, title } = props as { src?: string; title?: string };
      return src ? [["p", {}, ["a", { href: src }, title ?? src]]] : [];
    }

    if (DATA_COMPONENTS.has(tag)) {
      return [
        [
          "p",
          {},
          "The list is on ",
          ["a", { href: page }, "the page itself"],
          ".",
        ],
      ];
    }

    // Anything else (`::accordion`, `::tabs`, a slot, a component with
    // nothing to say like `::star-ask`): what is inside it, or nothing.
    return children;
  }

  return convert(nodes);
}
