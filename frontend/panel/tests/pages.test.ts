import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import { routes } from "vue-router/auto-routes";
import ui from "@nuxt/ui/vue-plugin";
import App from "../src/App.vue";

describe("the panel", () => {
  it("has a page for every file in src/pages", () => {
    expect(routes.map((route) => route.path)).toContain("/");
  });

  it("shows the first page", async () => {
    const router = createRouter({ history: createMemoryHistory(), routes });
    await router.push("/");

    const wrapper = mount(App, { global: { plugins: [router, ui] } });
    await router.isReady();

    expect(wrapper.find("h1").text()).toBe("Spook");
  });
});
