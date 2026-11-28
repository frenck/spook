import { describe, expect, it, vi } from "vitest";
import { callSpookCommand, isNotLoaded } from "../src/websocket/command";
import { fetchSpookInfo } from "../src/websocket/info";
import { fakeHass } from "./fake-hass";

describe("callSpookCommand", () => {
  it("sends the command with its fields", async () => {
    const hass = fakeHass({
      callWS: vi.fn().mockResolvedValue({ done: true }),
    });

    await expect(
      callSpookCommand(hass, "spook/example/get", { name: "ghost" }),
    ).resolves.toEqual({ done: true });
    expect(hass.callWS).toHaveBeenCalledExactlyOnceWith({
      type: "spook/example/get",
      name: "ghost",
    });
  });

  it("keeps the type when a field has the same name", async () => {
    const hass = fakeHass({ callWS: vi.fn().mockResolvedValue(null) });

    await callSpookCommand(hass, "spook/example/get", { type: "something" });

    expect(hass.callWS).toHaveBeenCalledExactlyOnceWith({
      type: "spook/example/get",
    });
  });
});

describe("isNotLoaded", () => {
  it("tells a Spook that is not loaded from a command that failed", () => {
    expect(isNotLoaded({ code: "not_loaded", message: "Not now" })).toBe(true);
    expect(isNotLoaded({ code: "unauthorized", message: "No" })).toBe(false);
    expect(isNotLoaded(new Error("not_loaded"))).toBe(false);
    expect(isNotLoaded(undefined)).toBe(false);
  });
});

describe("fetchSpookInfo", () => {
  it("asks spook/info", async () => {
    const hass = fakeHass({
      callWS: vi.fn().mockResolvedValue({ version: "4.2.0" }),
    });

    await expect(fetchSpookInfo(hass)).resolves.toEqual({ version: "4.2.0" });
    expect(hass.callWS).toHaveBeenCalledExactlyOnceWith({ type: "spook/info" });
  });
});
