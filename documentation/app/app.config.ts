// The signature pairing of the design system: a cyan fill with ink text,
// like the ghost itself. Light and dark pick their own shade of cyan, see
// `--ui-primary-fill` in main.css.
const primaryFill =
  "bg-(--ui-primary-fill) text-(--ui-on-primary) hover:bg-(--ui-primary-fill-hover) active:bg-(--ui-primary-fill-hover) disabled:bg-(--ui-primary-fill) aria-disabled:bg-(--ui-primary-fill)";

const eyebrow =
  "flex items-center gap-2.5 font-mono text-xs font-medium uppercase tracking-[0.14em] text-primary";

export default defineAppConfig({
  ui: {
    colors: {
      primary: "spook",
      neutral: "ink",
      error: "tongue",
      success: "emerald",
      warning: "orange",
      info: "blue",
    },

    // Material Design Icons, the icon set of Home Assistant itself.
    icons: {
      arrowDown: "i-mdi-arrow-down",
      arrowLeft: "i-mdi-arrow-left",
      arrowRight: "i-mdi-arrow-right",
      arrowUp: "i-mdi-arrow-up",
      caution: "i-mdi-alert-circle-outline",
      check: "i-mdi-check",
      chevronDoubleLeft: "i-mdi-chevron-double-left",
      chevronDoubleRight: "i-mdi-chevron-double-right",
      chevronDown: "i-mdi-chevron-down",
      chevronLeft: "i-mdi-chevron-left",
      chevronRight: "i-mdi-chevron-right",
      chevronUp: "i-mdi-chevron-up",
      close: "i-mdi-close",
      copy: "i-mdi-content-copy",
      copyCheck: "i-mdi-check-all",
      dark: "i-mdi-weather-night",
      drag: "i-mdi-drag-vertical",
      edit: "i-mdi-pencil-outline",
      ellipsis: "i-mdi-dots-horizontal",
      error: "i-mdi-close-circle-outline",
      external: "i-mdi-arrow-top-right",
      eye: "i-mdi-eye-outline",
      eyeOff: "i-mdi-eye-off-outline",
      file: "i-mdi-file-outline",
      folder: "i-mdi-folder-outline",
      folderOpen: "i-mdi-folder-open-outline",
      hash: "i-mdi-pound",
      info: "i-mdi-information-outline",
      light: "i-mdi-weather-sunny",
      loading: "i-mdi-loading",
      menu: "i-mdi-menu",
      minus: "i-mdi-minus",
      panelClose: "i-mdi-dock-left",
      panelOpen: "i-mdi-dock-left",
      plus: "i-mdi-plus",
      reload: "i-mdi-refresh",
      search: "i-mdi-magnify",
      star: "i-mdi-star-outline",
      stop: "i-mdi-stop",
      success: "i-mdi-check-circle-outline",
      system: "i-mdi-monitor",
      tip: "i-mdi-lightbulb-outline",
      trash: "i-mdi-delete-outline",
      upload: "i-mdi-upload",
      warning: "i-mdi-alert-outline",
    },

    button: {
      compoundVariants: [
        { color: "primary", variant: "solid", class: primaryFill },
      ],
    },

    badge: {
      compoundVariants: [
        { color: "primary", variant: "solid", class: primaryFill },
      ],
    },

    // Group names in the sidebar: small, mono, all caps.
    contentNavigation: {
      slots: {
        trigger:
          "font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-dimmed",
        listWithChildren: "ms-0 border-none",
      },
    },

    // Marks the headings in view, for main.css to light up only the first.
    contentToc: {
      variants: {
        active: {
          true: { link: "toc-in-view" },
        },
      },
    },

    footer: {
      slots: {
        root: "border-t border-default",
      },
    },

    // Section headlines are the design system's eyebrow: small, mono, all
    // caps, in cyan.
    pageHero: {
      variants: {
        headline: {
          true: { headline: eyebrow },
        },
      },
    },
    pageSection: {
      variants: {
        headline: {
          true: { headline: eyebrow },
        },
      },
    },
  },

  seo: {
    siteName: "Spook",
  },

  // The areas of the site, shown as tabs in the header, after the tour. Each
  // takes the content folders that belong to it; the sidebar only shows the
  // area the current page is in.
  //
  // Get started and About sit close to the marketing side: short, and read
  // once. Docs is everything you come back for, behind one tab.
  sections: [
    {
      key: "getStarted",
      label: "Get started",
      icon: "i-mdi-rocket-launch-outline",
      folders: ["getting-started", "guides"],
    },
    {
      key: "docs",
      label: "Docs",
      icon: "i-mdi-book-open-variant",
      // The integrations come last: it is the long one, and whatever is
      // below an open group of 45 is a long way down.
      folders: [
        "core-extensions",
        "helpers",
        "features",
        "reference",
        "enhanced-integrations",
      ],
      hub: "/docs",
    },
    {
      key: "about",
      label: "About",
      icon: "i-mdi-ghost-outline",
      folders: ["about-the-project", "boring-stuff"],
    },
  ],

  github: {
    url: "https://github.com/frenck/spook",
    edit: "https://github.com/frenck/spook/edit/main/documentation/content",
  },
});
