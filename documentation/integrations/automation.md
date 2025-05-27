---
subject: Enhanced integrations
title: Automations 🤖
short_title: Automations
subtitle: The breathing (mechanical) heart of Home Assistant.
thumbnail: ../images/integrations/automation/example.png
description: Spook enhances the automation integrations of Home Assistant by raising repairs issues, in case it detects something is wrong with an automation, for example, if it is using non-existing entities.
date: 2024-02-10T15:58:22+01:00
---

```{image} https://brands.home-assistant.io/automation/logo.png
:alt: The Home Asistant automation icon
:width: 250px
:align: center
```

<br><br>

Automations are the heart of {term}`Home Assistant`. It is what makes Home Assistant a home automation platform. It is the glue that binds all the other {term}`integrations <integration>` together, and it is what makes your home smart and comfortable.

Non-working automations, however, are a source of frustration. And sometimes, it can take you a bit to notice there is an issue with an automation. Spook enhances the automation integration of Home Assistant by raising repairs issues in case it detects something is wrong with an automation.

```{figure} ../images/integrations/automation/example.png
:name: example
:alt: Screenshot showing a repair raised by Spook for an automation.
:align: center

Spook found an issue with an automation that is using non-existing entities.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown referenced areas

Automations are inspected for the use of areas. If an automation is targeting an area in one of its actions that do not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the automation and the area that is referenced but not found.

```{figure} ../images/integrations/automation/unknown_areas.png
:name: Spook found an issue with an automation that is using a non-existing area.
:alt: Screenshot showing a repair raised by Spook for an automation.
:align: center

Spook found an issue with an automation that is using a non-existing area.
```

To resolve the raised issue, you can either remove the reference to the non-existing area or fix the referenced area. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced devices

Automations are inspected for the use of devices. If an automation is using a device that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the automation and the device that is referenced but not found.

```{figure} ../images/integrations/automation/unknown_device.png
:name: Spook found an issue with an automation that is using a non-existing device.
:alt: Screenshot showing a repair raised by Spook for an automation.
:align: center

Spook found an issue with an automation that is using a non-existing device.
```

To resolve the raised issue, you can either remove the reference to the non-existing device or fix the referenced device. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced entities

Automations are inspected for the use of {term}`entities <entity>`. If an automation is using an {term}`entity ID <entity id>` that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the automation and the entity ID that is referenced but not found.

```{figure} ../images/integrations/automation/example.png
:name: Spook found an issue with an automation that is using a non-existing entity.
:alt: Screenshot showing a repair raised by Spook for an automation.
:align: center

Spook found an issue with an automation that is using non-existing entities.
```

To resolve the raised issue, you can either remove the reference to the non-existing entity ID or fix the referenced entity ID. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced actions

Automations are inspected for the use of actions. If an automation is using a action that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the automation and the action that is referenced but not found.

To resolve the raised issue, you can either remove the reference to the non-existing actions. Spook will automatically remove the repair issue once the issue is fixed.

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
