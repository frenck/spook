/**
 * The dashboard bundle of Spook: its cards, card features and badges.
 *
 * Loaded on every page, for every user, so it stays small. An element with
 * something heavy behind it loads that with `import()` when it first renders.
 *
 * Every file in `elements/` is one element. They are bundled in here, not
 * loaded later: the features editor reads the list of card features once,
 * when it first loads, and a feature that registers after that is missing
 * from it until the page reloads.
 */
import { registerAll, type SpookElementDefinition } from "./registration";

registerAll(
  import.meta.glob<SpookElementDefinition>("./elements/*.ts", {
    eager: true,
    import: "default",
  }),
);
