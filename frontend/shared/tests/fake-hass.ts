/** A `hass` object for tests, with every call it gets written down. */
import { vi } from "vitest";
import type { HomeAssistant } from "../src/hass";

export const fakeHass = (overrides: Partial<HomeAssistant> = {}) => {
  const hass: HomeAssistant = {
    language: "en",
    states: {},
    themes: { darkMode: false },
    callWS: vi.fn(),
    localize: vi.fn((key: string) => `<${key}>`),
    loadBackendTranslation: vi.fn(),
    ...overrides,
  };
  return hass;
};
