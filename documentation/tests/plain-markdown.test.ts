import assert from "node:assert/strict";
import { test } from "node:test";
import { stringify } from "minimark/stringify";

import { plainMarkdown } from "../server/utils/plain-markdown.ts";
import type { MinimarkNode } from "../server/utils/plain-markdown.ts";

const page = { page: "/all-repairs" };

/** The nodes as the Markdown copy prints them. */
function markdown(nodes: MinimarkNode[]): string {
  return stringify(
    { type: "minimark", value: plainMarkdown(nodes, page) as never },
    { format: "markdown/mdc" },
  ).trim();
}

test("a glossary term is just the word", () => {
  assert.equal(
    markdown([
      [
        "p",
        {},
        "Set up ",
        ["term", { to: "integration" }, "integrations"],
        ".",
      ],
    ]),
    "Set up integrations.",
  );
});

test("a screenshot is an image, with its caption below it", () => {
  assert.deepEqual(
    plainMarkdown(
      [
        [
          "screenshot",
          { name: "marketplace-search", alt: "The Marketplace." },
          ["p", {}, "Step 3: search for Spook."],
        ],
      ],
      page,
    ),
    [
      [
        "p",
        {},
        [
          "img",
          {
            src: "/images/screenshots/en/light/marketplace-search.webp",
            alt: "The Marketplace.",
          },
        ],
      ],
      ["p", {}, "Step 3: search for Spook."],
    ],
  );
});

test("a callout is a quote that says what kind it is", () => {
  assert.equal(
    markdown([["warning", {}, ["p", {}, "Make a backup first."]]]),
    "> **Warning:** Make a backup first.",
  );
});

test("an accordion and a tab show everything, below their label", () => {
  assert.equal(
    markdown([
      [
        "accordion",
        {},
        [
          "accordion-item",
          { label: "Technical details", icon: "i-mdi-cog" },
          ["p", {}, "The details."],
        ],
      ],
      [
        "tabs",
        {},
        ["tabs-item", { label: "HACS" }, ["p", {}, "Through HACS."]],
      ],
    ]),
    "**Technical details**\n\nThe details.\n\n**HACS**\n\nThrough HACS.",
  );
});

test("cards are a list of links, with what each one is about", () => {
  assert.equal(
    markdown([
      [
        "card-group",
        {},
        [
          "card",
          { title: "Inverse", to: "/inverse", icon: "i-mdi-swap" },
          ["p", {}, "On becomes off."],
        ],
        ["card", { title: "Calibration", to: "/calibration" }],
      ],
    ]),
    "- [Inverse](/inverse): On becomes off.\n- [Calibration](/calibration)",
  );
});

test("a list that fills itself from data sends you to the page", () => {
  assert.equal(
    markdown([["repair-index", {}]]),
    "The list is on [the page itself](/all-repairs).",
  );
});

test("a video is a link to it", () => {
  assert.equal(
    markdown([
      ["iframe", { src: "https://youtube.com/embed/x", title: "Video" }],
    ]),
    "[Video](https://youtube.com/embed/x)",
  );
});

test("a component with nothing to say is gone", () => {
  assert.deepEqual(plainMarkdown([["star-ask", {}]], page), []);
});

test("images and code lose the attributes Markdown has no place for", () => {
  assert.equal(
    markdown([
      [
        "p",
        {},
        ["img", { src: "/a.png", alt: "A", className: ["mx-auto"] }],
        " and ",
        ["code", { language: "yaml" }, "on: true"],
      ],
    ]),
    "![A](/a.png) and `on: true`",
  );
});

test("a code block is left as it is", () => {
  const block: MinimarkNode = [
    "pre",
    { language: "yaml", code: "a: 1\n" },
    ["code", {}, ["span", { class: "line" }, "a: 1"]],
  ];

  assert.deepEqual(plainMarkdown([block], page), [block]);
});

test("the nodes it was given are left alone", () => {
  const nodes: MinimarkNode[] = [["p", {}, ["term", {}, "entity"]]];
  plainMarkdown(nodes, page);

  assert.deepEqual(nodes, [["p", {}, ["term", {}, "entity"]]]);
});
