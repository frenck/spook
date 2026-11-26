import assert from "node:assert/strict";
import { test } from "node:test";

import { honestSitemap, withCanonical } from "../modules/static-site.ts";

test("sitemap.md no longer promises content negotiation", () => {
  const before = [
    "# Spook Sitemap",
    "",
    "> Markdown index of every page on spook.boo. Links point at the raw markdown; append `.md` to any page URL (or set `Accept: text/markdown`) to get it from the page URL instead.",
    "",
    "## Pages",
  ].join("\n");

  const after = honestSitemap(before, "spook.boo");

  assert.doesNotMatch(after, /Accept/);
  assert.match(after, /^> Markdown index of every page on spook\.boo\. /m);
  assert.match(after, /`\/automation\.md` for `\/automation`/);
  assert.match(after, /^## Pages$/m);
});

test("a redirect page gets a canonical link to where it goes", () => {
  assert.equal(
    withCanonical(
      '<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0; url=/docs"></head></html>',
      "https://spook.boo/docs",
    ),
    '<!DOCTYPE html><html><head><link rel="canonical" href="https://spook.boo/docs"><meta http-equiv="refresh" content="0; url=/docs"></head></html>',
  );
});
