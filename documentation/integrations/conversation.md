---
subject: Enhanced integrations
title: Conversation
subtitle: Which lamp? Exactly.
description: Spook enhances Assist by reporting entities that share a name or alias Assist cannot tell apart, so asking for them by name fails.
date: 2026-10-10T12:00:00+02:00
---

```{image} https://brands.home-assistant.io/conversation/logo.png
:alt: The Home Assistant conversation logo
:width: 250px
:align: center
```

<br><br>

The conversation {term}`integration <integration>` is the part of Assist that listens to what you say and works out what you mean. Say "turn on the lamp", and it looks for an {term}`entity <entity>` exposed to Assist with the name or alias "lamp".

Names don't have to be unique in {term}`Home Assistant`, and that is fine almost everywhere. Assist is the exception: it has to pick one entity from a name, and when several answer to it, it needs something else to choose by.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Names Assist cannot tell apart

Spook raises a repair issue for every name or alias that several entities exposed to Assist answer to, when Assist cannot pick out each of them by it. Asking for it then fails, usually with an answer that more than one device has that name, and nothing tells you which ones, or why.

When names are the same, Assist only tells them apart by {term}`area <area>`: the one you name in the sentence, or the one your voice satellite is in. So two lamps in different areas are fine, and Spook leaves them alone. Two in the same area, or one without an area, can't be picked out by that name from anywhere.

A few things worth knowing about how Assist compares names, all of which Spook follows:

- Case and the spaces around a name don't count. "Lamp" and " lamp" are the same name.
- Aliases count as much as the name. An alias on one entity that matches the name of another collides.
- An entity that has no area of its own is in the area of its device.
- The kind of entity doesn't help. Turning something on or off, or asking how it is, looks at every entity with that name, lights and sensors alike.
- Entities that are not exposed to Assist are never looked at, by Assist or by Spook.

To fix it, give each entity a name or alias of its own, or move them into different areas. Aliases and exposure are under Settings > Voice assistants > Expose. Spook will automatically remove the repair issue once it is fixed.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Two smart plugs in the living room, both still called "Smart plug" because that is what they were called out of the box.
- A new lamp added without an area, sharing its name with the lamp in the bedroom. "Turn on the lamp" still works from the bedroom speaker, fails from every other room, and the new lamp can't be reached by name at all.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
