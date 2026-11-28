import { describe, expect, it } from "vitest";
import { loadTranslations, localize } from "../src/localize";
import { fakeHass } from "./fake-hass";

describe("loadTranslations", () => {
  it("loads the config_panel section of Spook", async () => {
    const hass = fakeHass();

    await loadTranslations(hass);

    expect(hass.loadBackendTranslation).toHaveBeenCalledExactlyOnceWith(
      "config_panel",
      "spook",
    );
  });
});

describe("localize", () => {
  it("looks up the key under Spook's config_panel section", () => {
    const hass = fakeHass();

    expect(localize(hass, "repairs.title", { count: 3 })).toBe(
      "<component.spook.config_panel.repairs.title>",
    );
    expect(hass.localize).toHaveBeenCalledExactlyOnceWith(
      "component.spook.config_panel.repairs.title",
      { count: 3 },
    );
  });
});
