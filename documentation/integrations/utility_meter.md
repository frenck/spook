---
subject: Enhanced integrations
title: Utility meter
subtitle: Help you to get scared of your utility bills before they arrive.
description: Spook enhances the Home Assistant utility meter integration by report issues in the repairs dashboard.
date: 2024-01-12T20:41:55+01:00
---

```{image} https://brands.home-assistant.io/utility_meter/logo.png
:alt: The Home Assistant utility meter logo
:width: 250px
:align: center
```

<br><br>

The utility meter {term}`helper <helper>` integration can track the consumption of utilities, such as electricity, gas, or water. It does so by tracking the state of a source entity, such as a smart meter, and calculating the usage based on the difference between the current and previous state.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown source entity

Spook inspects all utility meters created to find source entities they meter that no longer exist. If Spook finds such a case, it will raise a repair issue, informing you about the problematic utility meter and the source entity that is missing.

To resolve the raised issue, you can either remove the utility meter helper or restore the referenced source entity. Spook will automatically remove the repair issue once the issue is fixed.

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
