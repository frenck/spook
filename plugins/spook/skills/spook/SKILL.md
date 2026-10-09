---
name: spook
description: Knows Spook, the Home Assistant custom integration (domain spook) that finds ghosts (references to things that no longer exist, and leftovers nobody uses) and reports them as Repairs, and that adds over a hundred actions plus triggers, conditions and helpers. Use when Spook is installed and you manage Home Assistant from an agent (HA-MCP, Home Assistant's MCP server, the API), for example to call Spook actions like homeassistant.add_label_to_entity, repairs.list or light.set_brightness, to write automations with spook.* triggers and conditions such as spook.cron or spook.is_available, or to read, explain, fix or ignore the repair issues Spook raised.
license: MIT
---

# Spook

Spook is a custom integration for Home Assistant. It does two things:

- **Finds ghosts.** It watches automations, scripts, dashboards, helpers, groups, scenes, the energy dashboard and more for references to entities, devices, areas, floors, labels, actions, triggers and conditions that do not exist. It also points out leftovers: empty areas and floors, unused labels and blueprints, orphaned statistics. Every finding is an issue in Repairs, under the `spook` domain.
- **Adds the tools Home Assistant leaves out.** Actions, automation triggers and conditions, and a few helpers (calibration, inverse, time in state).

Reach for this skill when Spook is installed and the job is cleaning up a Home Assistant instance, managing its registries (areas, floors, labels, categories, entity IDs) from an agent, or writing automations that need something core does not offer.

Not sure Spook is there? Its actions only exist when it is: look for `spook.boo` or `repairs.list` among the actions, or a `spook` config entry.

## Actions

Call them like any core action: `domain.action`, fields under `data`, entities under `target`.

- Most of them live on the domain they act on, not on `spook`. `homeassistant.add_label_to_entity`, `homeassistant.create_area`, `repairs.list`, `light.set_brightness`, `input_select.random`. The UI marks them with a 👻 after the name.
- One on another domain only exists while that integration is loaded. No `light` integration, no `light.set_brightness`.
- Registry actions (create, delete, rename, labels, aliases, areas, floors, categories, entity IDs) need an admin user. So do `repairs.list`, `repairs.ignore_all` and `repairs.unignore_all`.
- Some hand back a response, like `repairs.list` and `calendar.delete_event`. Ask for it (`response_variable` in YAML, `return_response` over the API).
- An ID that does not exist is an error, not a silent no-op. Read the error: it names what is missing.
- Home Assistant's own MCP server offers the Assist tools and exposed scripts, not every action. To reach a Spook action from there, wrap it in a script and expose that.
- From Home Assistant 2026.11, Spook also brings its own tools to Home Assistant's administrator API (`homeassistant`), for conversation agents and Home Assistant's MCP server: `spook__overview`, `spook__list_ghosts`, `spook__explain_ghost`, `spook__find_usages`, `spook__check_references`, `spook__list_features`, `spook__ignore_ghost`, `spook__unignore_ghost` and `spook__fix_ghost`. When they are there, prefer them over calling actions by hand. `spook__check_references` checks a draft automation or script for ghosts before you save it.

Every action, with its fields: [references/actions.md](references/actions.md).

## Triggers and conditions

They use the new-style syntax, with `spook.<name>` as the platform, options under `options:` and the target under `target:`.

```yaml
triggers:
  - trigger: spook.cron
    options:
      schedule: "0 7 * * 1-5"
conditions:
  - condition: spook.is_available
    target:
      entity_id: media_player.bathroom
  - condition: spook.cooldown
    options:
      duration: "00:30:00"
actions:
  - action: media_player.play_media
    # ...
```

Some take other triggers or conditions as options, like `spook.all_of`, `spook.sequence`, `spook.debounce` and `spook.condition_met`. Those nest in the same shape as the automation they sit in.

Every trigger and condition, with its options: [references/triggers.md](references/triggers.md) and [references/conditions.md](references/conditions.md).

## Repairs

Spook raises issues under the `spook` domain. The issue ID starts with the kind of repair, followed by what it was found in.

- **Unknown references** (`*_unknown_*`): something points at a thing Home Assistant does not know. Usually it was renamed or removed. Find what it became and fix the reference, rather than deleting the automation that holds it.
- **Leftovers** (`empty_areas`, `empty_floors`, `unused_labels`, `unused_blueprints`, `orphaned_statistics`): nothing uses them. Could be a plan, could be junk. Ask before removing.
- **Fixable** repairs offer a fix in the Repairs dashboard: remove, keep and stop telling me, or fix it myself. Most of the ones that remove something look again first, and leave alone what came back.

Reading them: `repairs.list` with `domain: spook` hands back the open issues with `issue_id`, `title`, `severity`, `is_fixable`, `learn_more_url` and `ignored`. Add `include_ignored: true` to see ignored ones too.

Ignoring is per finding, not per place. Ignoring "unknown entity in automation X" silences that entity in that automation. A new unknown entity in the same automation raises a new issue. That is on purpose: one shrug should not hide the next real break.

Your own issues, with `repairs.create` and `repairs.remove`:

- `repairs.create` stores the `issue_id` with a `user_` prefix, and files it under `spook` whatever `domain` you gave.
- `repairs.list` shows that prefixed ID. Drop one `user_` before handing it to `repairs.remove` or `repairs.create`.
- Created issues are gone after a restart unless `persistent: true`.

Every kind of repair, what it means and where it is documented: [references/repairs.md](references/repairs.md).

## Rules

1. **Do not rename entity IDs to make a repair go away.** Entity IDs are what automations and dashboards hold on to. Fix the reference, or ask.
2. **Leave alone what you did not create.** Labels, areas and automations are somebody's setup.
3. **Check before you remove.** A leftover today can be next week's plan, and orphaned statistics are history that does not come back.
4. **Read the reference, do not guess field names.** The references are generated from Spook's own definitions.

Full documentation: https://spook.boo
