/**
 * Read a reference page (actions, triggers, conditions, the glossary) into
 * entries, so it can be shown as an index instead of a wall of headings.
 *
 * The Markdown stays the source. Every entry is still a `##` heading there,
 * which is what search, the counts on the home page, the plain Markdown copy
 * and the documentation tests read. Only the page itself is laid out from
 * what is read here.
 */

type Node = string | [string, Record<string, unknown>, ...Node[]];

interface Body {
  type?: string;
  value?: Node[];
}

export interface ReferenceSection {
  // The heading's anchor. Released versions of Spook link to these, so it is
  // exactly the id the heading had, never one made up here.
  id: string;
  heading: string;
  nodes: Node[];
}

export interface ReferenceEntry {
  id: string;
  title: string;
  group?: string;
  // What the entry says, still as Markdown nodes: it can have links, code
  // and glossary terms in it.
  nodes: Node[];
  name?: string;
  tryIt?: string;
  docs?: string;
  // Everything about the entry in lowercase, for the filter to match on.
  text: string;
}

export interface ReferenceGroup<Entry = ReferenceEntry> {
  id: string;
  title: string;
  entries: Entry[];
}

function textOf(node: Node): string {
  if (typeof node === "string") {
    return node;
  }

  const [, , ...children] = node;
  return children.map(textOf).join("");
}

/** Everything a section says, in lowercase, for a filter to match on. */
export function referenceText(section: ReferenceSection): string {
  return [section.heading, ...section.nodes.map(textOf)]
    .join(" ")
    .toLowerCase();
}

/** Split a page into what comes before the first `##`, and the sections. */
export function referenceSections(body?: Body): {
  intro: Node[];
  sections: ReferenceSection[];
} {
  const intro: Node[] = [];
  const sections: ReferenceSection[] = [];

  for (const node of body?.value ?? []) {
    if (typeof node !== "string" && node[0] === "h2") {
      sections.push({
        id: node[1].id as string,
        heading: textOf(node).trim(),
        nodes: [],
      });
      continue;
    }

    const current = sections.at(-1);
    if (current) {
      current.nodes.push(node);
    } else {
      intro.push(node);
    }
  }

  return { intro, sections };
}

/**
 * The line under an entry that names it in YAML and links to it, like
 * `` `zone.create`, [Try this action](...), [documentation](/zone) ``.
 */
function isEntryLine(node: Node): boolean {
  if (typeof node === "string" || node[0] !== "p") {
    return false;
  }

  const [, , first, ...rest] = node;
  return (
    typeof first !== "string" &&
    first?.[0] === "code" &&
    rest.some((child) => typeof child !== "string" && child[0] === "a")
  );
}

/**
 * A link on the entry line, picked by where it goes. Not by what it says:
 * "Try this action" reads differently in every language.
 */
function linkTo(
  line: Node,
  matches: (href: string) => boolean,
): string | undefined {
  if (typeof line === "string") {
    return undefined;
  }

  const [, , ...children] = line;
  for (const child of children) {
    if (typeof child === "string" || child[0] !== "a") {
      continue;
    }

    const href = child[1].href as string;
    if (matches(href)) {
      return href;
    }
  }

  return undefined;
}

/**
 * Mark the hashtags in a paragraph: `_#BobTheBuilder_` is the joke, shown
 * as a tag rather than in italics. They stay where they were written.
 */
function withTags(node: Node): Node {
  if (typeof node === "string") {
    return node;
  }

  const [tag, props, ...children] = node;
  if (tag === "em" && textOf(node).startsWith("#")) {
    return ["span", { class: "reference-tag" }, textOf(node)];
  }

  return [tag, props, ...children.map(withTags)];
}

/**
 * Read the entries of an actions, triggers or conditions page.
 *
 * A heading like `Areas: Create an area` puts the entry in the Areas group.
 */
export function referenceEntries(sections: ReferenceSection[]) {
  return sections.map((section): ReferenceEntry => {
    const [group, title] = section.heading.includes(": ")
      ? section.heading.split(/: (.*)/s)
      : [undefined, section.heading];

    const line = section.nodes.find(isEntryLine);
    const nodes = section.nodes.filter((node) => node !== line).map(withTags);

    const name = line && typeof line !== "string" ? textOf(line[2]!) : "";

    return {
      id: section.id,
      title: title!,
      group,
      nodes,
      name: name || undefined,
      // Opens the action in the reader's own Home Assistant.
      tryIt:
        line && linkTo(line, (href) => href.includes("my.home-assistant.io")),
      // Its documentation: a page of this site.
      docs: line && linkTo(line, (href) => href.startsWith("/")),
      text: referenceText(section),
    };
  });
}

/**
 * Put entries together by their group, in the order the groups first show
 * up on the page. Returns nothing when no entry has a group.
 */
export function referenceGroups<Entry extends ReferenceEntry>(
  entries: Entry[],
): ReferenceGroup<Entry>[] {
  if (!entries.some((entry) => entry.group)) {
    return [];
  }

  const groups = new Map<string, ReferenceGroup<Entry>>();
  for (const entry of entries) {
    const title = entry.group ?? "Other";
    if (!groups.has(title)) {
      // An anchor never has an underscore in it, so a group can never take
      // the id of an entry. `group-` could: "Group: Add members" is
      // `group-add-members`.
      groups.set(title, { id: `group_${anchor(title)}`, title, entries: [] });
    }
    groups.get(title)!.entries.push(entry);
  }

  return [...groups.values()];
}
