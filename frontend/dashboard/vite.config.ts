import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

// Into the integration, which serves it. Not in git: a release builds it.
const outDir = fileURLToPath(
  new URL("../../custom_components/spook/static/dashboard", import.meta.url),
);

export default defineConfig({
  build: {
    outDir,
    emptyOutDir: true,
    // The bundle loads on every page, old wall tablets too. Home Assistant's
    // legacy build goes back to Chrome 67, which cannot parse ES2020: see
    // "Old browsers" in frontend/README.md.
    target: "es2020",
    lib: {
      entry: "src/spook.ts",
      formats: ["es"],
      // The name Home Assistant is told about, so it never changes.
      fileName: () => "spook.js",
    },
    rolldownOptions: {
      output: {
        // All the way, whitespace too. Library mode keeps an ES module
        // readable for the bundler of whoever uses the library, and here
        // the browser is the one that uses it.
        minify: true,
        // What an element loads later. Hashed, so a new release never gets
        // a stale copy out of a browser's cache.
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
