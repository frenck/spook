# The real-world corpus

Most of Spook's tests are made up: `light.kitchen` with `Brightness`. They pin
the rules, not how people actually write configuration, and that is where false
findings hide. The corpus holds the shapes people really write, and runs each
one through exactly what Spook's repairs read.

This is layer one: configuration in, references out. No house, no issues.

## Cases are distilled, never copied

A case is our own minimal reproduction of a shape or a mistake seen in public:
a forum thread, a public configuration repository, an issue, or a trap one of
Spook's own tests already knows about.

- Never a verbatim copy. Rewrite it down to the part that matters.
- No personal data: no names, addresses, tokens, URLs to somebody's house.
- Our own entity IDs: `light.kitchen`, `sensor.outdoor_temperature`.
- Keep the link to where the shape came from in `source`.

## The format

One file per case, in `tests/corpus/<kind>/<case-name>.yaml`. The kinds are
`automation`, `script` and `dashboard`. A file holds two YAML documents:

```yaml
source: https://community.home-assistant.io/t/...
note: >-
  One or two lines: what shape this is, and why it is interesting.
expect:
  states:
    find:
      - light.kitchen: "on"
    not_find:
      - light.kitchen: "On"
  entities:
    find: [light.kitchen]
---
alias: Kitchen light follows the door
triggers:
  - trigger: state
    entity_id: binary_sensor.kitchen_door
    to: "on"
actions: []
```

The first document says what the case is:

- `source` (required): where the shape was seen, or the Spook test or pull
  request that knows the trap.
- `note` (required): what the shape is, and why it is here.
- `expect` (optional): only what matters. `find` must be in the result,
  `not_find` must not. Attributes and states are written as
  `entity_id: value`; quote `"on"`, `"off"`, `"yes"` and `"no"`, or YAML reads
  them as booleans.
- `known_issue` (optional): Spook gets this case wrong today. The `expect`
  rules say what should happen, and the test is an expected failure until they
  all hold. Once they do, the test fails until the mark is removed.

The second document is the configuration, as Home Assistant would load it: one
automation, one script (its body, with `sequence`), or one dashboard, view or
card. Home Assistant's own tags (`!secret`, `!input`, `!include` and friends)
load as plain text, like `"!input motion_sensor"`.

## What the result means

Every case is loaded the way a house loads it, then handed to the repairs for
its kind. The house is empty, so what a repair would report as unknown is every
reference it reads. Three types are taken one step earlier:

- `triggers` and `conditions`: every key the repair reads, because Home
  Assistant's own platforms always exist.
- `attributes` and `states`: the pairs the repair would ask the recorder about,
  as `entity_id: value`.

Automations and scripts are set up through Home Assistant itself, so `loaded`
says whether Home Assistant would load it at all. When it would not, only the
trigger and condition readers look at it, as in a real house. The integration
itself is loaded, so its own actions, like `script.turn_on`, are never
reported.

A dashboard case that is a view or a card is put in a dashboard first, since
the repairs only read dashboards, view by view.

## Adding a case

1. Write the case file. Keep it small: one shape, one reason.
2. Run it and generate its snapshot:

   ```shell
   timeout 900 python -m pytest -q -p no:cacheprovider --no-cov \
     tests/corpus/test_corpus.py --snapshot-update
   ```

3. Read the new part of `tests/corpus/snapshots/test_corpus.ambr` by hand,
   once. Is everything in there really a reference, and is nothing missing?
4. Add `expect` lines for what matters, and commit the case with its snapshot.

A case that shows a false finding or a miss is a bug. Fix it in the same pull
request when it is small, otherwise mark it with `known_issue` and file it.

## Updating snapshots

When a change to Spook moves what the readers find, the snapshot test fails and
shows the difference. Update with the same command as above, and read the diff
of the `.ambr` file before committing it. The `expect` rules are checked
regardless, so a careless update that breaks one still fails.
