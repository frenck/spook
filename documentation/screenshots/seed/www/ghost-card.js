// A dashboard resource that is added twice, for Spook to point out. It
// loads on every page, so it does nothing, and does it only once.
if (!customElements.get("ghost-card")) {
  customElements.define("ghost-card", class extends HTMLElement {});
}
