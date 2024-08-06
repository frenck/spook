---
subject: Enhanced integrations
title: Riemann sum integral
subtitle: The only integration that gives you energy if you provide it power.
thumbnail: ../images/social.png
description: Spook enhances the Riemann sum integral integration by inspecting it for missing source entities.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/integration/logo.png
:alt: The Home Assistant Riemann sum integral icon.
:width: 250px
:align: center
```

<br><br>

The Riemann sum integral {term}`helper <helper>` calculates the <wiki:Riemann_sum> of the values provided by a source sensor. The Riemann sum is an approximation of an **[integral](wiki:Integral)** by a [finite sum](wiki:Summation).

This is most often used to calculate the total energy usage of a power meter by using the power meter’s power consumption and the time between the measurements.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repair issues if it has found something that is not right.

### Unknown source entity

Spook inspects all Riemann sum integral created {term}`entities <entity>`, and looks for cases where a source sensor entity is no longer present. If Spook finds such a case, it will raise a {term}`repair issue <repairs>`, informing you about the problematic entity.

To resolve the raised issue, you can either remove the helper or fix the referenced source {term}`entity ID <entity id>`. Spook will automatically remove the repair issue once the issue is fixed.

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
