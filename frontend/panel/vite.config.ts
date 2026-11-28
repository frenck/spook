import { fileURLToPath } from "node:url";
import ui from "@nuxt/ui/vite";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";
import router from "vue-router/vite";

const root = fileURLToPath(new URL(".", import.meta.url));

// Into the integration, which serves it. Not in git: a release builds it.
const outDir = fileURLToPath(
  new URL("../../custom_components/spook/static/panel", import.meta.url),
);

export default defineConfig({
  // Its own directory, also when the tests run from the workspace root, so
  // `src/pages` is always this package's.
  root,
  plugins: [
    // A page is a file in `src/pages/`. Before vue(), which it hands the
    // pages to.
    router({ root, dts: false }),
    vue(),
    ui({
      // The icons the panel uses go into the bundle. A Home Assistant can be
      // offline, so none of them are fetched from the Iconify API.
      icon: { clientBundle: { scan: true } },
    }),
  ],
  build: {
    outDir,
    emptyOutDir: true,
    target: "es2020",
    rolldownOptions: {
      // A script, not a page: Home Assistant loads a panel in an iframe by
      // its module. `index.html` is only for `npm run dev`.
      input: "src/main.ts",
      output: {
        // The names Home Assistant is told about, so they never change.
        entryFileNames: "spook-panel.js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: (asset) =>
          asset.names.includes("main.css")
            ? "spook-panel.css"
            : "assets/[name]-[hash][extname]",
      },
    },
  },
});
