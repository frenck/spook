import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, test } from "node:test";

import { lastChanged, parseGitLog } from "../modules/page-dates.ts";

test("the newest commit that touched a file is its date", () => {
  const output = [
    "",
    "2026-11-20T10:00:00+01:00\n\nguides/one.md\nguides/two.md\n",
    "2026-10-01T09:00:00+02:00\n\nguides/one.md\nthree.md\n",
  ].join("\0");

  assert.deepEqual(parseGitLog(output), {
    "guides/one.md": "2026-11-20T10:00:00+01:00",
    "guides/two.md": "2026-11-20T10:00:00+01:00",
    "three.md": "2026-10-01T09:00:00+02:00",
  });
});

test("no history, no dates", () => {
  assert.deepEqual(parseGitLog(""), {});
});

// A real repository: two commits on different days, and a file that was
// never committed.
const repository = mkdtempSync(join(tmpdir(), "page-dates-"));
after(() => rmSync(repository, { recursive: true, force: true }));

function commit(file: string, date: string): void {
  writeFileSync(join(repository, file), date);
  const env = {
    ...process.env,
    GIT_AUTHOR_DATE: date,
    GIT_COMMITTER_DATE: date,
    GIT_AUTHOR_NAME: "Test",
    GIT_AUTHOR_EMAIL: "test@example.com",
    GIT_COMMITTER_NAME: "Test",
    GIT_COMMITTER_EMAIL: "test@example.com",
  };
  execFileSync("git", ["add", file], { cwd: repository, env });
  execFileSync("git", ["commit", "--quiet", "--no-gpg-sign", "-m", file], {
    cwd: repository,
    env,
  });
}

execFileSync("git", ["init", "--quiet"], { cwd: repository });
mkdirSync(join(repository, "content", "guides"), { recursive: true });
commit("content/guides/old.md", "2026-01-02T03:04:05+00:00");
commit("content/new.md", "2026-11-24T12:00:00+00:00");
writeFileSync(join(repository, "content", "draft.md"), "not committed");

test("pages get the date of their last commit, by their path in the folder", () => {
  assert.deepEqual(lastChanged(join(repository, "content")), {
    "guides/old.md": "2026-01-02T03:04:05+00:00",
    "new.md": "2026-11-24T12:00:00+00:00",
  });
});

test("a shallow clone gives no dates, rather than one date for everything", () => {
  const clone = join(
    repository,
    "..",
    `${repository.split("/").pop()}-shallow`,
  );
  execFileSync("git", [
    "clone",
    "--quiet",
    "--depth",
    "1",
    `file://${repository}`,
    clone,
  ]);

  try {
    assert.deepEqual(lastChanged(join(clone, "content")), {});
  } finally {
    rmSync(clone, { recursive: true, force: true });
  }
});

test("outside a Git checkout, no dates", () => {
  const outside = mkdtempSync(join(tmpdir(), "page-dates-outside-"));

  try {
    assert.deepEqual(lastChanged(outside), {});
  } finally {
    rmSync(outside, { recursive: true, force: true });
  }
});
