---
subject: Enhanced integrations
title: Switch as X
subtitle: Help a switch with an identity crisis discover its true self.
thumbnail: ../images/social.png
description: The Switch as X helper lets you convert any Home Assistant switch entity into a light, cover, fan, lock, or siren entity. Spook detects issues with them.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/switch_as_x/logo.png
:alt: The Home Assistant switch as x icon
:width: 250px
:align: center
```

<br><br>

The Switch as X {term}`helper <helper>` lets you convert any {term}`Home Assistant` switch {term}`entity <entity>` into a light, cover, fan, lock, or siren entity.

In Home Assistant’s world, a wall plug is a switch. And while that is correct for a wall plug, in general, those plugs are often used with, for example, a light fixture or a fan. General-purpose relays are similar, as they are sometimes used for things like locks or garage doors.

Using the Switch as X integration, you can convert those switches into the entity types that best match your use case. The helper will create a new entity of the desired type and use the switch entity as its source to mirror its state and commands.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown source entity

Spook inspects all Switch as X created entities, in case one of your existing helper entities points to a source switch entity, that no longer exists. If Spook finds such a case, it will raise a repair issue, informing you about the problematic entity.

To resolve the raised issue, you can either remove the helper or fix the referenced source entity ID. Spook will automatically remove the repair issue once the issue is fixed.

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
