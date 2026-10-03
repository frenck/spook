---
subject: Enhanced integrations
title: HomeKit Bridge
subtitle: Lost in translation, between Home Assistant and the Home app.
description: Spook enhances the Home Assistant HomeKit Bridge integration by reporting issues with its configuration.
date: 2026-10-03T15:00:00+02:00
---

```{image} https://brands.home-assistant.io/homekit/logo.png
:alt: The Home Assistant HomeKit Bridge logo
:width: 250px
:align: center
```

<br><br>

The HomeKit Bridge integration in Home Assistant makes your entities available in Apple's Home app, and to Siri.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown entities

A HomeKit bridge keeps a list of the entities it includes, or excludes, by their entity ID. It does not follow an entity that is renamed. An included entity that was renamed or removed silently disappears from the Home app, and an excluded entity that was renamed shows up in it again.

Spook inspects the entities each HomeKit bridge includes and excludes, and raises a repair issue for a bridge naming entities that do not exist. Excluded entities are marked as such in the list. Bridges that are disabled are left alone.

To resolve the raised issue, go to the HomeKit Bridge integration, select **Configure** on the bridge, and pick the entities again. For a bridge set up in YAML, edit the `filter` of that bridge in your configuration instead. Spook will automatically remove the repair issue once the issue is fixed.

:::{attention} Known limitations
:class: dropdown

- Only the entities a bridge names one by one are checked. Domains and glob patterns are not entity IDs, and are left alone.
- Per-entity settings in YAML (`entity_config`) are not checked.
  :::
