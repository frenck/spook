---
subject: Enhanced integrations
title: Dashboards
subtitle: There is more than meets the eye. 🤩
thumbnail: ../images/integrations/lovelace/unknown_entity.png
description: Spook enhances the dashboard integration of Home Assistant by raising repairs issues, in case it detects something is wrong with a dashboard, like for example, used non-existing entities.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/lovelace/logo.png
:alt: The Home Assistant dashboard icon
:width: 250px
:align: center
```

<br><br>

A {term}`dashboard <dashboard>` in {term}`Home Assistant` provides the user interface to monitor and control your Home Assistant instance. They are extremely flexible, and there is quite a community around creating the fanciest dashboards you've ever seen. But with this great power comes great responsibility. It is easy to make mistakes in your dashboards, and it is not always easy to find them.

Spook enhances the dashboard integration of Home Assistant by raising {term}`repairs <repairs>` issues in case it detects something is wrong with a dashboard.

:::{note}
You might see the term "Lovelace" everywhere in the community. This is the internal codename of the current dashboard system used in Home Assistant, which was used until it fully replaced the old (and now removed) state UI from before. The term "Lovelace" is still used by many in the community and is, of course, still present in the codebase of Home Assistant.

TL;DR: "Lovelace" is the dashboard system of Home Assistant and is nowadays just referred to as "Dashboards".
:::

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown referenced entities

Dashboards are inspected for the use of {term}`entities <entity>`. If a dashboard uses an {term}`entity ID <entity id>` in one of its cards that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the dashboard and the entity ID that is referenced but not found.

```{figure} ../images/integrations/lovelace/unknown_entity.png
:name: unknown entity
:alt: Screenshot showing a repair raised by Spook for a dashboard.
:align: center

Spook found an issue with an dashboard that is using non-existing entities.
```

To resolve the raised issue, you can either remove the reference to the non-existing entity ID or fix the referenced entity ID. Spook will automatically remove the repair issue once the issue is fixed.

:::{attention} Known limitations
:class: dropdown

- Spook is not aware of all possible configuration for all possible cards. Especially with third-party cards, configuration can sometimes differ and Spook might not be able to detect the use of an unknown entity ID in such cases.
  :::

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
