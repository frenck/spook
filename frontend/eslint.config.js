import js from "@eslint/js";
import vue from "eslint-plugin-vue";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

export default defineConfig(
  {
    // Written by Nuxt UI's Vite plugin when the panel builds or runs.
    ignores: ["panel/auto-imports.d.ts", "panel/components.d.ts"],
  },
  js.configs.recommended,
  tseslint.configs.recommended,
  // The rules that catch mistakes, not the ones about layout: Prettier
  // has the last word on that.
  vue.configs["flat/essential"],
  {
    files: ["**/*.vue"],
    languageOptions: {
      parserOptions: { parser: tseslint.parser },
    },
    rules: {
      // TypeScript knows the globals of a browser and of Vue, ESLint does not.
      "no-undef": "off",
    },
  },
  {
    // A page is named after its route, and `index` is a fine route.
    files: ["panel/src/pages/**/*.vue"],
    rules: {
      "vue/multi-word-component-names": "off",
    },
  },
);
