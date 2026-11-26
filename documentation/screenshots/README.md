# Screenshots

The screenshots of Home Assistant on spook.boo, made from a real Home Assistant
instead of by hand. Run it when Home Assistant changes how something looks, or
when you add a shot.

```bash
npm run screenshots                     # English, light and dark
LANGUAGES=en,nl,de npm run screenshots  # one language after the other
KEEP=1 npm run screenshots              # leave the last Home Assistant running
npm run screenshots -- -g repair        # only the shots matching "repair"
```

This is a manual run. It is not part of CI.

## What it does

`run.ts` goes through the languages one at a time. Every language gets a
Home Assistant of its own, so everything in the pictures is in that
language: the interface, and also the rooms, lamps, automations and the
names Home Assistant translates itself. For each language it:

1. Starts the latest stable Home Assistant in Docker, on port 18123, with the
   config in `seed/`, the names of the language filled in, and Spook from this
   repository in it. The language is in the config from the first start:
   Home Assistant names the entities of an integration in the language it has
   when that integration sets up, and never again after.
2. Onboards it in that language with you as the owner, and gives you your
   GitHub avatar.
3. Renames what the YAML of the seed made. Those entities start out named
   after their IDs, like `movie_night`, because Home Assistant makes an entity
   ID out of the first name an entity has and keeps it. This way the IDs are
   the same in every language. Then it checks every entity is there under its
   ID, and that no room exists twice.
4. Adds Spook through its setup flow, waits for the repairs the seed config
   is built to cause, and ignores any Home Assistant raised itself.
5. Takes every shot in `shots.spec.ts`, in light and dark.
6. Removes the container, and the config in it, before the next language.

A language takes a few minutes. A shot that fails in one language does not
stop the others.

Every shot lands in
`public/images/screenshots/<language>/<light|dark>/<name>.webp`,
as lossless WebP.

## What you need

- Docker.
- Google Chrome. Playwright uses the one installed on the machine:
  `npx playwright install chrome` installs it.
- A color emoji font on Linux, or every 👻 is an empty box. On Debian and
  Ubuntu, that is `fonts-noto-color-emoji`. The run stops early without one.
- A Chinese and Japanese font on Linux for the Chinese and Japanese shots,
  or the text comes out in whatever font the system falls back to, or as
  empty boxes. With only a Chinese fallback font, Japanese kanji get Chinese
  shapes. On Debian and Ubuntu, `fonts-noto-cjk` covers both.

`HA_IMAGE`, `HA_PORT`, `HA_OWNER_NAME`, `HA_OWNER_USERNAME` and
`HA_OWNER_GITHUB` change the image, the port and who the owner is.

## The names of the home

Everything people read in the home is in `seed/names/<language>.yml`: rooms,
floors, labels, lamps, helpers, automations with their descriptions, the
script, the scene, the zone, the dashboard, and what the action shots type
in. The seed refers to a name as `"${light.living_room_lamp}"`, always inside
double quotes. The keys are the IDs, and IDs are never translated: the
website shows them in YAML examples.

English (`en.yml`) has every name. Another language without a name gets the
English one, except for `search`: a language without a search word skips
that shot.

The three rooms Home Assistant creates itself when it is onboarded (living
room, kitchen, bedroom) must have the exact names it gives them in that
language. Otherwise onboarding adds its own next to ours, and the setup
stops with a message saying so. They are in Home Assistant's
`homeassistant/components/onboarding/translations/<language>.json`.

## Adding a language

1. Copy `seed/names/en.yml` to `seed/names/<language>.yml`, with the code
   Home Assistant uses for it, like `fr`, `es`, `it`, `zh-Hans` or `pt-BR`.
2. Translate the names the way somebody in that language names things at
   home. Use the words of `translations/corpus/<language>/glossary.yml` for
   what Home Assistant calls its things. `dashboard.overview` is Home
   Assistant's own name for the default dashboard: leave it out when Home
   Assistant has none in that language, see the comment in `en.yml`.
3. Fill in `search` with a word from Spook's own translation of each topic's
   actions, the way somebody would type it.
4. `LANGUAGES=<language> npm run screenshots`.

Spook needs its own translation in that language as well:
`custom_components/spook/translations/<language>.json`.

## Adding a shot

Add an entry to `shots` in `shots.spec.ts`: a name, the page to open, and
optionally what to do on it before the picture. Find things on the page by
their role, by Spook's own translated text, or by a name from `seed/names`,
never by English words: the same shot runs in every language.

When a shot needs something in Home Assistant that is not there yet, like
another broken automation, add it to `seed/`, with its name in
`seed/names/en.yml` and the other languages.

Not everything can live in YAML. The setup in `home-assistant.ts` makes the
rest: the helpers the delete actions remove (those only work on helpers made
in the UI), the family calendar and the shopping list, the babysitter user,
a time in state sensor, and the traces of a home lived in for a while that
Spook finds: statistics of a gas meter that is gone, an energy dashboard
counting a washing machine that is gone, a dashboard resource added twice,
and a blueprint nothing uses, made to look two days old. The garden tap
comes from a small integration of our own in `seed/custom_components/`: no
valve in Home Assistant has a position in YAML.

The blueprint `seed/blueprints/automation/spook/door_light.yaml` was
"imported" from `seed/www/.blueprints/door_light.yaml`, which Home Assistant
serves at `/local/`, and which has moved on since. So Spook offers an update
for it without going on the internet.

Some of what Spook finds it only reports after a wait, on purpose: the first
look for blueprint updates comes 5 to 30 minutes after a start, and a
statistic has to look orphaned for 15 minutes. The container sets
`SPOOK_SCREENSHOT_HOME=1`, and with that Spook does not wait
(`custom_components/spook/const.py`). Nothing else ever sets it.

Most shots come from a few builders, so a new one is often one line:

- `action("homeassistant.create_area", { data: {...} })`: one of Spook's
  actions in the Actions tool, filled in, the way "Try this action" on the
  website opens it. Saved as `action-homeassistant-create-area`. Use the
  areas, labels, lamps and helpers in `seed/` by their IDs. Text people read
  comes from `seed/names`: pass a function instead,
  `action("zone.create", (name) => ({ data: { name: name("examples.new_zone") } }))`.
  A device or an integration entry only gets its ID once Home Assistant runs,
  so write `{ deviceOf: "sun" }` or `{ entry: "radio_browser" }` and it is
  looked up, by domain. A user has only a name: `{ user: name("user.babysitter") }`.
  A field that takes several values gets a list by itself.
- `repair("script-unknown-areas", "script_unknown_area_references", "script.goodnight")`:
  a repair Spook raised, opened. The last part is what the repair is about, by
  its place in `seed/names`, because several repairs start the same.
- `actionSearch("area", "area")`: the Add action dialog searched for the word
  under `search.area` in `seed/names`.
- `automationPart("trigger", "stale", "1732000000014")`: one of Spook's
  triggers or conditions, selected in the automation of the seed made for it,
  so the sidebar shows its options. Saved as `trigger-stale`. Every trigger
  and condition has an automation of its own in `seed/automations.yaml`.
- `helperForm("spook_calibration", (name) => ({...}))`: one of Spook's
  helpers, picked under Create helper, its form filled in. Saved as
  `helper-calibration`.

Only Spook's repairs show: setup ignores the ones Home Assistant itself
raises, so they never end up in a picture.

## Looking over a run

`sheet.ts` stacks shots into one tall PNG, a contact sheet, so a run is
checked by scrolling one picture instead of opening every file:

```bash
npm run screenshots:sheet -- /tmp/nl-light.png public/images/screenshots/nl/light/*.webp
```

## Using a shot on the website

```md
::screenshot{name="repairs" alt="What the screenshot shows, for screen readers."}
An optional caption.

::
```

The website shows the light or the dark one, to match the site.
