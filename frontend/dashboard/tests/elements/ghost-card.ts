/** A fake element, laid out the way a real one in `src/elements/` is. */
import { defineCard } from "../../src/registration";

class SpookTestGhostCard extends HTMLElement {}

export default defineCard({
  tag: "spook-test-ghost-card",
  element: SpookTestGhostCard,
  name: "Ghost",
  description: "A card that only exists in tests.",
});
