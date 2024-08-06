---
subject: Enhanced integrations
title: Groups
subtitle: Never underestimate the power of stupid people in large groups.
thumbnail: ../images/integrations/group/example.png
description: Spook enhances the Home Assistant group integration by report issues in the repairs dashboard if members are missing.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/group/logo.png
:alt: The Home Assistant group logo
:width: 250px
:align: center
```

<br><br>

The group {term}`helper <helper>` integration lets you combine multiple {term}`entities <entity>` into a single entity. Entities that are members of a group can be controlled and monitored as a whole.

This can be useful for cases where you want to control, for example, the multiple bulbs in a light fixture as a single light in {term}`Home Assistant`, or maybe you want to combine all the wall plugs that control all your Christmas decorations into a single switch entity.

```{figure} ../images/integrations/group/example.png
:name: example
:alt: Screenshot showing an repair raised by Spook for a group that has an unknown member entity.
:align: center

Spook found an issue with a group that has a non-existing entity as a member.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown source entity

Spook inspects all groups created to find group member entities that no longer exist. If Spook finds such a case, it will raise a repair issue, informing you about the problematic group and the member entity that is missing.

To resolve the raised issue, you can either remove the missing entity from the group or fix the referenced source entity. Spook will automatically remove the repair issue once the issue is fixed.

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
