import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    projects: [
      {
        test: {
          name: "shared",
          root: "shared",
        },
      },
      {
        test: {
          name: "dashboard",
          root: "dashboard",
          environment: "happy-dom",
        },
      },
      "panel/vitest.config.ts",
    ],
  },
});
