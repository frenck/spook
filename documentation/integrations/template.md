---
subject: Enhanced integrations
title: Template helpers
subtitle: Keep template helpers free of ghosts. 👻
description: Spook inspects Template helpers and raises repair issues for references to unavailable entities and actions.
date: 2026-08-03T00:00:00+02:00
---

The [Template integration](https://www.home-assistant.io/integrations/template/)
lets you create helpers whose values and actions are based on templates. Spook
inspects Template helpers created in the Home Assistant user interface and
raises repair issues when it finds references that are no longer available.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it raises a
repair issue when it finds something that is not right.

### Unknown referenced entities

Spook inspects templates in Template helpers for entity IDs that do not exist.
The repair issue lists the helper and the unavailable entity IDs. To resolve the
issue, open the linked helper, update the reference to an existing entity, or
remove it. Spook automatically removes the repair issue once it is fixed.

### Unknown referenced actions

Spook inspects action sequences configured in Template helpers, such as the
`press` action of a Template Button or the `turn_on` and `turn_off` actions of
a Template Switch. If an action is unavailable, the repair issue lists the
helper and the unavailable action.

To resolve the issue, open the linked helper, update the action to one provided
by Home Assistant, or restore the integration or script that provided it.
Templated action names are ignored because their value is determined at runtime.
Spook automatically removes the repair issue once it is fixed.

## Features requests, ideas, and support

If you have an idea for a new action, entity, or repair detection, [let us know
in the discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck? See the [](../support) page for where to get help.
