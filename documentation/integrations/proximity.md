---
subject: Enhanced integrations
title: Proximity
subtitle: Proximity isn’t everything, but it's close...
description: Spook enhances the Home Assistant proximity integration by reporting issues with its configuration.
date: 2024-02-10T14:33:44+01:00
---

```{image} https://brands.home-assistant.io/proximity/logo.png
:alt: The Home Assistant proximity logo
:width: 250px
:align: center
```

<br><br>

The proximity integration in Home Assistant allows you to track the proximity of devices or persons to a zone. This can be used to trigger automations based on the proximity of a person or device to a specific location.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown zone

Spook inspects all proximity configurations to find configurations based on zones that no longer exist. If Spook finds such a case, it will raise a repair issue, informing you about the problematic proximity configuration and the zone that is missing.

To resolve the raised issue, you can either remove the proximity configuration or restore the referenced zone. Unfortunately, Home Assistant doesn't allow you to adjust the main zone that is used for the proximity configuration.

Spook will automatically remove the repair issue once the issue is fixed.

### Unknown tracked devices or persons

Spook inspects all proximity configurations to find configurations based on tracked devices or persons that no longer exist. If Spook finds such a case, it will raise a repair issue, informing you about the problematic proximity configuration and the tracked device or person that is missing.

To resolve the raised issue, you can edit the proximity configuration and remove the missing tracked device or person. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown ignored zones

A proximity configuration allows for ignoring certain zones. Spook inspects all proximity configurations to find ignored zones that no longer exist. If Spook finds such a case, it will raise a repair issue, informing you about the problematic proximity configuration and the ignored zone that is missing.

While this is not a critical issue, it is a good one to clean up. To resolve the raised issue, you can edit the proximity configuration and remove the missing ignored zone. Spook will automatically remove the repair issue once the issue is fixed.

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
