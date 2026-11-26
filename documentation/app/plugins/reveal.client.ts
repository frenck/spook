/**
 * Things that arrive as you scroll to them: once an element with one of the
 * reveal classes comes into view, it gets `data-revealed`, and the CSS in
 * main.css plays its entrance.
 *
 * An attribute, not a class: Vue owns the class of its components and
 * writes it again when one updates, like a card that lights up on hover.
 * A class added here would be gone then, and the card hidden for good.
 *
 * Everything stays visible without this: the hidden starting state only
 * applies once `reveal-ready` is on the page, which this sets. So without
 * script, for a search engine, or for anyone who asked their system for less
 * motion, nothing is ever hidden.
 */
const SELECTOR = ".reveal, .reveal-left, .reveal-right, .reveal-stagger > *";

export default defineNuxtPlugin((nuxtApp) => {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        // In view, or already scrolled past: a fast scroll or a jump to an
        // anchor must never leave something hidden above you.
        if (entry.isIntersecting || entry.boundingClientRect.top < 0) {
          entry.target.setAttribute("data-revealed", "");
          observer.unobserve(entry.target);
        }
      }
    },
    // A little into the screen, so the entrance is seen, not missed below
    // the fold.
    { rootMargin: "0px 0px -12% 0px" },
  );

  const watch = (root: ParentNode) => {
    for (const element of root.querySelectorAll(SELECTOR)) {
      if (!element.hasAttribute("data-revealed")) {
        observer.observe(element);
      }
    }
  };

  document.documentElement.classList.add("reveal-ready");
  nuxtApp.hook("app:mounted", () => watch(document));
  nuxtApp.hook("page:finish", () => watch(document));

  // Pages and components that render later bring their own.
  new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node instanceof Element) {
          if (node.matches(SELECTOR)) {
            observer.observe(node);
          }
          watch(node);
        }
      }
    }
  }).observe(document.body, { childList: true, subtree: true });
});
