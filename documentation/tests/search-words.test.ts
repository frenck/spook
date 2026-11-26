import assert from "node:assert/strict";
import { test } from "node:test";
import MiniSearch from "minisearch";

import {
  searchByPrefix,
  searchTokenizer,
  searchTypos,
} from "../shared/utils/searchWords.ts";

/** A tiny index, set up the way the site search sets up its own. */
function indexOf(language: string, titles: string[]) {
  const index = new MiniSearch<{ id: number; title: string }>({
    fields: ["title"],
    storeFields: ["title"],
    tokenize: searchTokenizer(language),
    processTerm: (term) => term.toLowerCase(),
    searchOptions: { prefix: searchByPrefix, fuzzy: searchTypos },
  });
  index.addAll(titles.map((title, id) => ({ id, title })));

  return index;
}

const found = (index: MiniSearch, term: string) =>
  index.search(term, { combineWith: "AND" }).map((hit) => hit.title);

test("English splits on what is not a letter, as it always did", () => {
  assert.deepEqual(searchTokenizer("en")("automation.snooze create_area"), [
    "automation",
    "snooze",
    "create",
    "area",
  ]);
});

test("Chinese is cut into words, not into one long word", () => {
  const words = searchTokenizer("zh-Hans")("使用打盹动作暂停自动化");
  assert.ok(words.length > 3, words.join("|"));
  assert.ok(words.includes("打盹"), words.join("|"));
});

test("a Chinese action name finds its action", () => {
  const index = indexOf("zh-Hans", [
    "自动化：打盹",
    "区域：创建区域",
    "实体：隐藏实体",
  ]);

  assert.deepEqual(found(index, "打盹"), ["自动化：打盹"]);
  assert.deepEqual(found(index, "创建区域"), ["区域：创建区域"]);
  assert.deepEqual(found(index, "隐藏"), ["实体：隐藏实体"]);
});

test("the first character of a Chinese word finds it", () => {
  const index = indexOf("zh-Hans", ["自动化：打盹"]);
  assert.deepEqual(found(index, "打"), ["自动化：打盹"]);
});

test("the code in a Chinese page is found by its parts", () => {
  const index = indexOf("zh-Hans", ["用 automation.snooze 让自动化打盹"]);
  assert.equal(found(index, "snooze").length, 1);
});

test("Chinese words get no typo matching", () => {
  assert.equal(searchTypos("打盹"), false);
  assert.equal(searchTypos("automation"), 2);
  assert.equal(searchTypos("on"), false);
});

test("one Latin letter is no prefix, one Chinese character is", () => {
  assert.equal(searchByPrefix("o"), false);
  assert.equal(searchByPrefix("自"), true);
});

test("a Japanese action name finds its action", () => {
  const index = indexOf("ja", [
    "オートメーション: スヌーズ 👻",
    "エリア: エリアを作成 👻",
    "エンティティ: エンティティを非表示 👻",
  ]);

  assert.deepEqual(found(index, "スヌーズ"), ["オートメーション: スヌーズ 👻"]);
  assert.deepEqual(found(index, "非表示"), [
    "エンティティ: エンティティを非表示 👻",
  ]);
});
