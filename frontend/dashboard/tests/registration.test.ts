import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  defineBadge,
  defineCard,
  defineCardFeature,
  register,
  registerAll,
  type SpookElementDefinition,
} from "../src/registration";

// A new tag for every test: a custom element stays defined for as long as
// the document lives, and happy-dom keeps one document per file.
let count = 0;
const unique = () => `ghost${++count}`;

class FakeElement extends HTMLElement {}

beforeEach(() => {
  delete window.customCards;
  delete window.customCardFeatures;
  delete window.customBadges;
});

describe("register", () => {
  it("defines a card and puts it in the card picker", () => {
    const tag = `spook-${unique()}-card` as const;

    register(
      defineCard({
        tag,
        element: class extends FakeElement {},
        name: "Ghost",
        description: "A card for testing.",
        preview: true,
      }),
    );

    expect(customElements.get(tag)).toBeDefined();
    expect(window.customCards).toEqual([
      expect.objectContaining({
        type: tag,
        name: "Ghost",
        description: "A card for testing.",
        preview: true,
      }),
    ]);
    expect(window.customCardFeatures).toBeUndefined();
    expect(window.customBadges).toBeUndefined();
  });

  it("defines a card feature and puts it in the features editor", () => {
    const tag = `spook-${unique()}-feature` as const;
    const isSupported = () => true;

    register(
      defineCardFeature({
        tag,
        element: class extends FakeElement {},
        name: "Ghost",
        isSupported,
        configurable: true,
      }),
    );

    expect(customElements.get(tag)).toBeDefined();
    expect(window.customCardFeatures).toEqual([
      { type: tag, name: "Ghost", isSupported, configurable: true },
    ]);
  });

  it("defines a badge and puts it in the badge picker", () => {
    const tag = `spook-${unique()}-badge` as const;

    register(
      defineBadge({
        tag,
        element: class extends FakeElement {},
        name: "Ghost",
      }),
    );

    expect(customElements.get(tag)).toBeDefined();
    expect(window.customBadges).toEqual([
      expect.objectContaining({ type: tag, name: "Ghost" }),
    ]);
  });

  it("adds to what other cards already listed", () => {
    const tag = `spook-${unique()}-card` as const;
    window.customCards = [{ type: "mushroom-light-card", name: "Mushroom" }];

    register(
      defineCard({ tag, element: class extends FakeElement {}, name: "Ghost" }),
    );

    expect(window.customCards.map((entry) => entry.type)).toEqual([
      "mushroom-light-card",
      tag,
    ]);
  });

  it("does nothing the second time, when the bundle loads twice", () => {
    const tag = `spook-${unique()}-card` as const;
    const element = class extends FakeElement {};

    register(defineCard({ tag, element, name: "Ghost" }));
    register(
      defineCard({ tag, element: class extends FakeElement {}, name: "Ghost" }),
    );

    expect(customElements.get(tag)).toBe(element);
    expect(window.customCards).toHaveLength(1);
  });
});

describe("registerAll", () => {
  it("registers the elements of a directory, the way the entry does", () => {
    registerAll(
      import.meta.glob<SpookElementDefinition>("./elements/*.ts", {
        eager: true,
        import: "default",
      }),
    );

    expect(customElements.get("spook-test-ghost-card")).toBeDefined();
    expect(window.customCards).toEqual([
      expect.objectContaining({ type: "spook-test-ghost-card", name: "Ghost" }),
    ]);
  });

  it("carries on past an element that fails to register", () => {
    const tag = `spook-${unique()}-card` as const;
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    registerAll({
      "./elements/broken.ts": defineCard({
        // Not a valid custom element name, so defining it throws.
        tag: "spook-Broken-card",
        element: class extends FakeElement {},
        name: "Broken",
      }),
      "./elements/fine.ts": defineCard({
        tag,
        element: class extends FakeElement {},
        name: "Fine",
      }),
    });

    expect(customElements.get(tag)).toBeDefined();
    expect(window.customCards?.map((entry) => entry.type)).toEqual([tag]);
    expect(consoleError).toHaveBeenCalledExactlyOnceWith(
      "Spook could not register ./elements/broken.ts",
      expect.anything(),
    );
  });
});

describe("the entry", () => {
  it("loads", async () => {
    await expect(import("../src/spook")).resolves.toBeDefined();
  });
});
