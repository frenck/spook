---
subject: Enhanced integrations
title: Home Assistant
subtitle: The tidying up nobody volunteers for.
description: Spook enhances the Home Assistant core integration by reporting dead entity registrations, dangling customizations, forgotten access tokens, helpers whose sources are gone, and areas, floors, labels and blueprints that are not doing anything.
date: 2026-08-21T16:20:00+02:00
---

```{image} https://brands.home-assistant.io/homeassistant/logo.png
:alt: The Home Assistant logo
:width: 250px
:align: center
```

<br><br>

`homeassistant` is the {term}`integration <integration>` that is {term}`Home Assistant` itself. It owns the registries that everything else hangs off: the {term}`areas <area>`, {term}`floors <floor>`, {term}`labels <label>`, {term}`devices <device>` and {term}`entities <entity>` that give your configuration its shape, plus the `homeassistant:` section of your {term}`YAML`.

Registries are good at remembering and bad at forgetting. An entry stays until something removes it, and almost nothing ever does. That is the right default, and it is also why an instance that has been running for a few years accumulates a quiet layer of things that refer to nothing.

Spook enhances the core integration by raising {term}`repairs <repairs>` issues for that layer.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds a large number of actions in the `homeassistant` domain, but they are documented by subject rather than all on one page. See [](../areas), [](../floors), [](../labels), [](../devices), [](../entities), [](../devices_entities), [](../users) and [](../misc).

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

Some of these are broken things, and some are only untidy ones. The untidy ones are all fixable from the issue itself, and every one of them offers to stop mentioning it, because an empty area you keep on purpose is nobody's business but yours.

### Non-existing registered entities

An {term}`entity <entity>` is registered by its integration, and the registry entry survives across restarts so the entity keeps its ID, its name and its settings. When the thing behind it is gone, the entry stays.

Spook watches for integrations that finished setting up and then never provided entities they have registry entries for. Those entities do not exist any more: they show as unavailable, forever, and they are grouped per integration entry so one removed device does not produce twenty separate issues.

Only integrations that finished loading are considered, so an integration that is slow to start or retrying is never mistaken for a dead one.

To resolve the raised issue, remove these entities from the entity registry if you no longer need them. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown customized entities

The `customize:` section of your configuration pins attributes onto a specific entity, which is how a sensor gets a friendly name or a different icon that its integration does not offer.

Spook checks the entity each customization names. If the entity does not exist, that block of YAML is doing nothing at all. Only exact entity keys are checked: glob and domain customizations are patterns rather than references, so they are left alone.

To resolve the raised issue, edit the `customize:` section in your configuration and remove these entities. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown helper sources

Many {term}`helpers <helper>` are built on top of another entity: a threshold on a sensor, a derivative on a counter, a group on a handful of switches. Spook reads each helper's own configuration to find the source entities it names, and raises a repair issue when one of them is unknown to Home Assistant.

Reading the configuration rather than the running helper matters here: it means a helper whose entity failed to set up entirely is still checked, and that is exactly the helper most likely to be broken.

Without its source, a helper like this cannot work. The raised issue is fixable: Spook can remove the helper for you, or you can fix it yourself on the Helpers page.

### Unknown min/max helper members

A min/max helper combines several entities into one number. Spook reads its configuration and raises a repair issue when it names members that no longer exist.

This one is fixable by pruning rather than removing: Spook can drop the missing members so the helper carries on with the ones that remain. A min/max helper needs at least two members, though, so if removing the missing ones would leave fewer than that, Spook says so and sends you to the Helpers page instead of quietly breaking the helper a different way.

### Forgotten long-lived access tokens

A long-lived access token does not expire. That is the point of it, and it is also the problem: a token issued for a script you stopped running three years ago is still a working key to your instance.

Spook raises a repair issue for every token that has not been used in 180 days, one issue per token, and checks once a day.

The raised issue is fixable: Spook can revoke the token for you. Be deliberate about it. Revoking a token stops anything still using it from working until it gets a new one, and "not used in 180 days" is evidence, not proof.

### Empty areas

An {term}`area` with no devices, no entities, and no automation or script targeting it is not doing anything.

Spook checks references as well as contents, so an area that is deliberately empty because an automation targets it is left alone. The raised issue is fixable: Spook can remove the area for you.

### Empty floors

A {term}`floor` exists to group areas. One with no areas at all, and no automation or script targeting it, is not doing that.

The raised issue is fixable: Spook can remove the floor for you.

### Unused labels

A {term}`label` that is applied to no entity, device or area, and that no automation or script targets, is not doing anything either.

The raised issue is fixable: Spook can remove the label for you.

### Unused blueprints

{term}`Blueprints <blueprint>` collect. You import one to try it, decide against it, and it stays. Spook raises a repair issue for a blueprint that no automation or script uses.

A blueprint whose file was added or changed in the last day is left alone, so importing one and setting it up a few minutes later does not earn you an instant repair issue for your trouble.

The raised issue is fixable: Spook can remove the blueprint for you.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Replacing a batch of devices. The new ones set themselves up, the old registry entries stay behind as permanently unavailable entities, and grouping them per integration turns a wall of unavailable entities into one issue you can act on.
- Auditing who still has a key to your instance. Long-lived tokens are easy to create and easy to forget, and nothing else in Home Assistant will bring one up unprompted.
- Cleaning up after a reorganisation. Renaming and regrouping leaves empty areas, empty floors and unused labels behind, and none of them are visible unless you go looking.
- Finding helpers that broke months ago. A helper without its source is not merely wrong, it is silently wrong, and it will keep reporting a last known value as if nothing happened.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
