---
subject: Enhanced integrations
title: Scripts
subtitle: Script kiddies. 🍼
thumbnail: ../images/integrations/script/example.png
description: Spook enhances the script integrations of Home Assistant by raising repairs issues, in case it detects something is wrong with a script, for example, if it is using non-existing entities.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/script/logo.png
:alt: The Home Assistant script icon.
:width: 250px
:align: center
```

<br><br>

A script in {term}`Home Assistant` is a sequence of actions that are executed when the script is started or called via start using a {term}`action <performing actions>`. Scripts are similar to {term}`automations <automation>`, but are not automatically executed when a trigger fires. Scripts are a great way to group a sequence of actions together that can be executed on demand and reused in multiple automations.

Non-working scripts, however, are (just like automations) a source of frustration. And sometimes, it can take you a bit to notice there is an issue with a script. Spook enhances the script integration of Home Assistant by raising repair issues in case it detects something is wrong with a script.

```{figure} ../images/integrations/script/example.png
:name: example
:alt: Screenshot showing a repair raised by Spook for a script.
:align: center

Spook found an issue with a script that is using non-existing entities.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown referenced areas

Scripts are inspected for the use of areas. If a script is targeting an area in one of its actions that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the area that is referenced but not found.

```{figure} ../images/integrations/script/unknown_area.png
:name: Spook found an issue with a script that is using a non-existing area.
:alt: Screenshot showing a repair raised by Spook for a script.
:align: center

Spook found an issue with a script that is using a non-existing area.
```

To resolve the raised issue, you can either remove the reference to the non-existing area or fix the referenced area. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced devices

Scripts are inspected for the use of devices. If a script is using a device that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the device that is referenced but not found.

```{figure} ../images/integrations/script/unknown_device.png
:name: Spook found an issue with a script that is using a non-existing device.
:alt: Screenshot showing a repair raised by Spook for a script.
:align: center

Spook found an issue with a script that is using a non-existing device.
```

To resolve the raised issue, you can either remove the reference to the non-existing device or fix the referenced device. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced entities

Scripts are inspected for the use of {term}`entities <entity>`. If a script uses an {term}`entity ID <entity id>` that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the entity ID that is referenced but not found.

```{figure} ../images/integrations/script/example.png
:name: Spook found an issue with a script that is using a non-existing entity.
:alt: Screenshot showing a repair raised by Spook for a script.
:align: center

Spook found an issue with a script that is using non-existing entities.
```

To resolve the raised issue, you can either remove the reference to the non-existing entity ID or fix the referenced entity ID. Spook will automatically remove the repair issue once the issue is fixed.

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
