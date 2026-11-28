import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

// The panel's own Vite setup, so a test sees the pages and components the
// way the build does.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      name: "panel",
      environment: "happy-dom",
    },
  }),
);
