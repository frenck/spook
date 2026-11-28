# Spook's frontends

Two frontends, one workspace:

- `dashboard/`: the cards, card features and badges for dashboards. Lit,
  built into one ES module that Home Assistant loads on every page.
- `panel/`: Spook's own panel, for settings and status. Vue with Nuxt UI,
  loaded in an iframe when someone opens it.
- `shared/`: what both use. The types of `hass`, the websocket commands,
  the strings.

Both build into the integration, `custom_components/spook/static/`, which
Spook serves at `/api/spook/static/`. That directory is not in git: a release
builds it. Without it, Spook runs as a backend only.

## Commands

From `frontend/`, with the Node.js version in `.nvmrc`:

```bash
npm ci                  # install
npm run lint            # ESLint and Prettier
npm run format          # fix what lint can fix
npm run typecheck       # TypeScript, the .vue files too
npm run test            # Vitest, all three packages
npm run build           # both frontends, into the integration
npm run build:release   # what a release ships: the dashboard bundle only
npm run size            # the dashboard bundle against its budget, after a build
npm run home-assistant  # a Home Assistant with Spook from this checkout
cd panel && npm run dev # the panel on its own, on http://localhost:5173
```

CI runs all of them but the last two, on every pull request that touches
`frontend/`.

## Adding things

### A dashboard element

One file in `dashboard/src/elements/`, with a default export made by
`defineCard`, `defineCardFeature` or `defineBadge` from
`dashboard/src/registration.ts`. That is all: the entry finds every file in
that directory and registers it, and nothing else lists them.

```ts
import { LitElement, html } from "lit";
import { defineCardFeature } from "../registration";

class SpookAutomationActionsFeature extends LitElement {
  render() {
    return html`...`;
  }
}

export default defineCardFeature({
  tag: "spook-automation-actions-feature",
  element: SpookAutomationActionsFeature,
  name: "Automation actions",
  isSupported: (hass, context) =>
    context.entity_id?.startsWith("automation.") ?? false,
});
```

- Only the files directly in `elements/` count. What an element needs on the
  side goes in a directory of its own next to it, like
  `elements/automation-actions/`.
- The entry is in the bundle every user downloads on every page. Anything
  heavy goes behind an `import()` in the element, which puts it in a chunk
  that loads when the element shows. `npm run size` fails over 30 KB
  gzipped. Lit itself costs about 6 KB.
- Decorators like `@property` work the way Lit documents them for
  TypeScript: `experimentalDecorators` in `dashboard/tsconfig.json`.
- Registering twice is safe. The bundle can end up on a page twice, like
  from the page and from a dashboard resource for Cast.

### A panel page

One `.vue` file in `panel/src/pages/`. The file name is the route:
`pages/repairs.vue` is `/repairs`, `pages/index.vue` is `/`. Nuxt UI's
components (`UButton`, `UCard`) and composables (`useToast`) are there
without importing them. What comes from `vue` and `vue-router` is imported
as usual.

Icons are Material Design Icons, like Home Assistant's own, written the way
the website writes them: `i-mdi-ghost`. The ones the panel uses go into the
build. Nothing fetches an icon from the internet: a Home Assistant can be
offline.

### A websocket command

Two small files, one on each side:

- The command itself, in the integration:
  `custom_components/spook/ectoplasms/<domain>/websocket/<name>.py`. See
  `custom_components/spook/websocket.py` for how.
- Its twin in `shared/src/websocket/<name>.ts`: the shape of its answer, and
  a function that asks it with `callSpookCommand`. `info.ts` is the example.

Import it by its path, `@spook/shared/websocket/<name>`. There is no index
file to add it to.

A command called while Spook reloads fails with `not_loaded`. Check for that
with `isNotLoaded`, and ask again later.

### A string

Strings live in `custom_components/spook/translations/en.json`, under
`config_panel`, for both frontends. Load them once with `loadTranslations`
from `@spook/shared/localize`, and read one with
`localize(hass, "repairs.title")`. Only `en.json` is edited by hand: Weblate
owns the other languages. A new string needs a Weblate pass before a release.

## Dependencies

Everything both frontends are going to need is installed. A thread that
wants a new dependency asks first. Every package is one more to keep up to
date, and two threads that each add one fight over `package-lock.json`.

## Naming

> **Proposal, for Frenck to confirm.** These are forever once shipped: they
> end up in people's dashboards, settings and automations, and a rename
> breaks them.

- **Custom element tags** start with `spook-` and end in what they are:
  `-card`, `-feature` or `-badge`, like `spook-automation-actions-feature`.
  The types in `registration.ts` refuse anything else. A dashboard says the
  tag with `custom:` in front, `type: custom:spook-automation-actions-feature`:
  Home Assistant strips `custom:` and creates the element with the rest as
  its tag (`stripCustomPrefix`, `src/data/lovelace_custom_cards.ts:100` in
  the frontend). The well-known cards do the same, like
  `mushroom-light-card` and `mushroom-template-badge`.
- **A strategy**, should Spook get one, is `ll-strategy-dashboard-spook-...`.
  That prefix is Home Assistant's, not ours.
- **Websocket commands** follow the rule in
  `custom_components/spook/websocket.py`: `spook/<area>/<verb>` in lower
  snake case, like `spook/repairs/list`, and `spook/<name>` for the few
  about Spook as a whole, like `spook/info`.
- **The panel** lives at `/spook`. A dashboard's address needs a hyphen in
  Home Assistant, so no dashboard can ever take it.
- **The Labs preview feature** that switches the dashboard bundle on is
  `dashboard_elements`. Labs keys are lower snake case and say what they
  switch on, like `winter_mode` and `improved_presence_detection` in Home
  Assistant itself.
- **Files**: the dashboard entry is `spook.js`, the panel entry
  `spook-panel.js` with `spook-panel.css`. Home Assistant is told about
  those, so they keep their names. Everything else gets a hash in its name.

## Old browsers

The bundle is built for ES2020: browsers from 2020 on. Home Assistant's
legacy build goes further back, to Chrome 67 and Safari 15.4, for old wall
tablets. Chrome 67 to 79 cannot parse ES2020 (`?.` and `??`), so a Spook
card does not show there, and the rest of the page is unaffected. Lowering
the target is one line in `dashboard/vite.config.ts`, and costs bytes.

## Looking at it in a real Home Assistant

```bash
npm run build
npm run home-assistant
```

That starts the latest stable Home Assistant in Docker on
<http://127.0.0.1:18125>, with Spook from this checkout mounted into it. Make
a user, then add Spook under Settings, Devices and services. `HA_IMAGE` picks
another image (`ghcr.io/home-assistant/home-assistant:beta`), `HA_PORT`
another port. Stop it with Ctrl+C. It keeps its configuration in a Docker
volume, so the next start skips the onboarding:
`docker volume rm spook-home-assistant` starts over.

Spook is mounted, not copied, so:

- After `npm run build`, reload the page. The files are served with a month
  of cache headers: until the URL carries a version, that is a hard reload.
- A build made after Spook started is served once Spook reloads (the three
  dots on its integration card). Before the first build there is nothing to
  serve.
- A change to Python code needs a restart: `docker restart spook-home-assistant`.

It is an empty home. The screenshot tool in `documentation/screenshots/`
starts one with rooms, lamps, broken automations and Spook's repairs in it,
onboarded and all. It copies Spook in rather than mounting it, and removes
the container when it is done, so it does not fit working on a frontend as
is. `KEEP=1 npm run screenshots` in `documentation/` leaves that one running.

## Things that are easy to trip over

- The repository's `.gitignore` is a Python one, and it hides more than it
  looks like: any file or directory named `build`, `dist`, `lib`, `env`,
  `output`, `parts`, `var` or `config`, anywhere. A `lib/` or `config/`
  directory in a frontend package would silently never be committed. Pick
  another name.
- `panel/auto-imports.d.ts` and `panel/components.d.ts` are written by Nuxt
  UI's Vite plugin whenever the panel builds, runs or is tested. They are
  committed, so the type check knows the components. Commit them with the
  page that changed them.
