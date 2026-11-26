import assert from "node:assert/strict";
import { test } from "node:test";

import { closeEmphasis, literalStrong } from "./emphasis.ts";

const body = (text: string, labels: string[] = []) =>
  closeEmphasis(text, "body", labels);

test("trailing punctuation moves out of a span a letter follows", () => {
  assert.equal(body("**怎么修复：**从修复里"), "**怎么修复**：从修复里");
  assert.equal(
    body("- **重启：**这个时刻会保留。"),
    "- **重启**：这个时刻会保留。",
  );
  assert.equal(body("**直し方：**修復"), "**直し方**：修復");
  assert.equal(body("**Note :**texte"), "**Note** :texte");
  assert.equal(body("**Note :**texte"), "**Note** :texte");
  assert.equal(body("*注意：*文"), "*注意*：文");
  assert.equal(body("__注意：__文"), "__注意__：文");
});

test("a span that starts with punctuation gets a space in front", () => {
  assert.equal(
    body("2. 选择**+ 创建辅助元素**。"),
    "2. 选择 **+ 创建辅助元素**。",
  );
});

test("an underscore inside a word becomes an asterisk", () => {
  assert.equal(body("最后一次_进入_其中"), "最后一次*进入*其中");
});

test("what already closes is left alone", () => {
  for (const line of [
    "**怎么修复**：从修复里",
    "**How to fix it:** remove it.",
    "选择**保存**。",
    "Not that \\*\\*bad word\\*\\*.",
    "* a list item, 2 * 3",
    "snake_case_name",
  ]) {
    assert.equal(body(line), line);
  }
});

test("code, components, tokens and front matter are never touched", () => {
  for (const line of [
    "`**a：**b` 文",
    '::callout{title="**a：**b"}',
    "⟦CODE1⟧",
  ]) {
    assert.equal(body(line), line);
  }
  assert.equal(
    closeEmphasis("title: **a：**b", "frontmatter"),
    "title: **a：**b",
  );
});

test("a label keeps its punctuation, and verify gets the last word", () => {
  const line = "Marca **Todo esto sucedió.**ahora";
  assert.equal(body(line, ["Todo esto sucedió."]), line);
  assert.equal(literalStrong(line), 2);

  // Without the label, the full stop would have moved.
  assert.equal(body(line), "Marca **Todo esto sucedió**.ahora");
});
