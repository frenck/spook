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

As with automations, only values shaped like a device ID are considered: thirty-two hexadecimal characters, which is what Home Assistant hands out. An integration taking a `device_id` that means its own hardware, such as RFLink's protocol address, is left alone.

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

### Unknown referenced actions

Scripts are inspected for the use of actions. If a script is using an action that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the action that is referenced but not found.

To resolve the raised issue, you can either remove the reference to the non-existing action or restore the integration that provides the action. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced floors

Scripts are inspected for the use of {term}`floors <floor>`. If a script is targeting a floor in one of its actions that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the floor that is referenced but not found.

To resolve the raised issue, you can either remove the reference to the non-existing floor or fix the referenced floor. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced labels

Scripts are inspected for the use of {term}`labels <label>`. If a script is targeting a label that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the label that is referenced but not found.

To resolve the raised issue, you can either remove the reference to the non-existing label or fix the referenced label. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced conditions

Scripts are inspected for the conditions they use. Conditions are provided by {term}`integrations <integration>`, so a condition that no installed integration can provide cannot be evaluated. A script like that fails validation outright and becomes unavailable, which is why Spook deliberately inspects unavailable scripts: they are the broken ones.

Home Assistant does notice, but it raises a generic issue about the script. Spook names the exact conditions, which is the part you need in order to fix it.

This usually means the integration that provided the condition was removed. To resolve the raised issue, you can either remove the use of these conditions or restore the integration that provides them. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced triggers

Scripts are inspected for the trigger configurations they contain, such as the ones a `wait_for_trigger` step waits on. If no installed integration can provide a trigger a script waits on, the whole script goes down with it: it fails validation and becomes unavailable.

Home Assistant raises a generic issue about the script without saying which trigger caused it. Spook names the trigger.

To resolve the raised issue, you can either remove the use of these triggers or restore the integration that provides them. Spook will automatically remove the repair issue once the issue is fixed.

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
