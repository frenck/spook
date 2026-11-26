/**
 * Bold and italic that Markdown actually closes.
 *
 * Markdown only closes `**` when it is right-flanking: a `**` right after
 * punctuation has to be followed by a space or more punctuation. Chinese and
 * Japanese put a letter there, so `**怎么修复：**从修复里` shows its
 * asterisks. The same goes for an opening `**` right after a letter with
 * punctuation behind it, like `选择**+ 创建辅助元素**`. French without a
 * space after the colon, `**Note :**texte`, has it too.
 *
 * The rule is Markdown's, not a language's, so it is checked and fixed for
 * every language. The verdict comes from micromark, the parser under the
 * site's own Markdown, not from a guess of ours.
 */
import { micromark } from "micromark";
import { gfm, gfmHtml } from "micromark-extension-gfm";

const CODE = /<code[^>]*>[\s\S]*?<\/code>/g;
const INLINE_CODE = /(`+)(?!`)(.*?[^`])\1(?!`)/g;

// Lines that are not prose: a component and its props, a lone token.
const COMPONENT = /^\s*:+[a-z]/;
const LONE_TOKEN = /^\s*⟦[A-Z]+\d+⟧\s*$/;

const WIDE =
  "[\\p{Script=Han}\\p{Script=Hiragana}\\p{Script=Katakana}\\p{Script=Hangul}]";

/** The page as the site shows it, without its code. */
function rendered(markdown: string): string {
  return micromark(markdown, {
    extensions: [gfm()],
    htmlExtensions: [gfmHtml()],
  }).replace(CODE, "");
}

/** How often `**` or `__` is left as text, outside code, once rendered. */
export function literalStrong(markdown: string): number {
  return rendered(markdown).match(/\*\*|__/g)?.length ?? 0;
}

/** How many `*` and `_` are left as text, outside code, once rendered. */
function literalDelimiters(markdown: string): number {
  return rendered(markdown).match(/[*_]/g)?.length ?? 0;
}

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * The places a delimiter might fail, as a fix each. Only candidates: a fix
 * is kept when micromark agrees it closes something.
 */
function candidates(line: string, labels: Set<string>): string[] {
  const fixes: string[] = [];

  for (const delimiter of ["**", "__", "*", "_"]) {
    const run = escape(delimiter);
    const character = escape(delimiter[0]!);
    // `_` inside a word is not emphasis at all, so it never opens there.
    const before =
      delimiter[0] === "_"
        ? `(?<![${character}\\\\\\p{L}\\p{N}])`
        : `(?<![${character}\\\\])`;
    const open = `${before}${run}(?!${character})`;
    const close = `${run}(?!${character})`;
    const inside = `(?:(?!${run}).)`;

    // `**怎么修复：**从`: the punctuation at the end goes outside the span,
    // with any space in front of it. A label keeps its own punctuation.
    const trailing = new RegExp(
      `${open}(?!\\s)(${inside}*?[^\\s])(\\s*\\p{Po}+)${close}(?=[^\\s\\p{P}\\p{S}])`,
      "gu",
    );
    for (const match of line.matchAll(trailing)) {
      // `**Todo esto sucedió.**` is a label as Home Assistant has it.
      if (labels.has(match[1]! + match[2]!)) {
        continue;
      }
      fixes.push(
        line.slice(0, match.index) +
          delimiter +
          match[1] +
          delimiter +
          match[2] +
          line.slice(match.index + match[0].length),
      );
    }

    // `选择**+ 创建辅助元素**`: a span that starts with punctuation does not
    // open right after a letter. That punctuation is often part of a label,
    // so it stays, and a space goes in front of the span.
    const leading = new RegExp(
      `(?<=[^\\s\\p{P}\\p{S}])${open}(?=[\\p{P}\\p{S}])${inside}+?${close}`,
      "gu",
    );
    for (const match of line.matchAll(leading)) {
      fixes.push(`${line.slice(0, match.index)} ${line.slice(match.index)}`);
    }

    // `最后一次_进入_其中`: `_` does not open or close inside a word, `*`
    // does. The English has `_became_`, the span is the same either way.
    // Only between Chinese, Japanese or Korean: between Latin letters,
    // `snake_case_name` is a name.
    if (delimiter[0] === "_") {
      const inWord = new RegExp(
        `(?<=${WIDE})${run}(?![_\\s])(${inside}+?)(?<!\\s)${run}(?=${WIDE})`,
        "gu",
      );
      for (const match of line.matchAll(inWord)) {
        const star = "*".repeat(delimiter.length);
        fixes.push(
          line.slice(0, match.index) +
            star +
            match[1] +
            star +
            line.slice(match.index + match[0].length),
        );
      }
    }
  }

  return fixes;
}

/** Close the spans of one line of prose. */
function closeLine(line: string, labels: Set<string>): string {
  if (!/[*_]/.test(line) || COMPONENT.test(line) || LONE_TOKEN.test(line)) {
    return line;
  }

  // Inline code is put aside, so nothing in it is ever a delimiter.
  const code: string[] = [];
  let text = line.replace(INLINE_CODE, (span) => {
    code.push(span);
    return `${code.length - 1}`;
  });

  const restore = (masked: string) =>
    masked.replace(/\ue000(\d+)\ue001/g, (_, index) => code[Number(index)]!);

  // Judged on its own, so a line indented under a list item is not taken
  // for a code block.
  const left = (candidate: string) =>
    literalDelimiters(restore(candidate).trimStart());

  let literal = left(text);
  while (literal) {
    let improved = false;

    for (const fix of candidates(text, labels)) {
      const remaining = left(fix);
      if (remaining < literal) {
        text = fix;
        literal = remaining;
        improved = true;
        break;
      }
    }

    if (!improved) {
      break;
    }
  }

  return text.replace(/(\d+)/g, (_, index) => code[Number(index)]!);
}

/**
 * Make every bold and italic span of a masked section close, where moving
 * its trailing punctuation out, or a space in front of it, does that.
 *
 * `labels` are the label translations of the glossary: what Home Assistant
 * shows, letter for letter. Their punctuation stays inside. What cannot be
 * fixed here is left as it is, for `verifyPage` to report.
 */
export function closeEmphasis(
  masked: string,
  kind: "frontmatter" | "body",
  labels: string[] = [],
): string {
  // Front matter values are plain text on the site, not Markdown.
  if (kind === "frontmatter") {
    return masked;
  }

  const kept = new Set(labels);
  return masked
    .split("\n")
    .map((line) => closeLine(line, kept))
    .join("\n");
}
