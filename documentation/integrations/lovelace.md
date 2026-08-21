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

### Unknown referenced areas

Dashboards are inspected for the use of {term}`areas <area>`. An area can be referenced in more than one way: by an area card, by the area view strategy, by the areas dashboard strategy listing areas to hide or order, and by an `area_id` used as the target of an action. Spook looks for all of them and raises a repair issue naming the dashboard and the areas that are missing.

None of this breaks the dashboard. An area card with a missing area shows nothing, which looks a lot like an area where nothing is happening; a button whose action targets a missing area renders perfectly and does nothing when you press it.

To resolve the raised issue, you can either remove the reference to the non-existing area or fix the referenced area. Spook will automatically remove the repair issue once the issue is fixed.

### Missing dashboard resources

Dashboard resources tell Home Assistant which extra JavaScript and CSS files to load, which is how custom cards get there. Spook checks the ones it can: a resource served from `/local/` or `/hacsfiles/` maps to a file on disk, so Spook can see whether that file is there. If it is not, it will raise a repair issue listing the resources in question.

Resources on an external URL, or served by an integration, are deliberately skipped. Spook cannot verify those without going and asking, so it does not claim to.

A missing local resource usually means a custom card was removed but its resource stayed behind. The cost is paid on every page load, by every browser, for a file that is never going to arrive.

To resolve the raised issue, go to Settings > Dashboards > Resources and remove or correct these resources. Spook will automatically remove the repair issue once the issue is fixed.

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
