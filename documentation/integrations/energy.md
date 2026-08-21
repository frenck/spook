---
subject: Enhanced integrations
title: Energy
subtitle: Watching the meter so you do not have to.
description: Spook enhances the Home Assistant energy dashboard by reporting entities it is configured to use that no longer exist.
date: 2026-08-21T16:20:00+02:00
---

```{image} https://brands.home-assistant.io/energy/logo.png
:alt: The Home Assistant energy logo
:width: 250px
:align: center
```

<br><br>

The energy {term}`dashboard <dashboard>` in {term}`Home Assistant` is where your consumption, production, gas, water, and battery numbers come together. It is configured once, in Settings > Dashboards > Energy, by pointing it at the {term}`entities <entity>` that carry those numbers.

That configuration is a list of {term}`entity IDs <entity id>` held separately from the entities themselves, and nothing keeps the two in step. Home Assistant does validate it, but it shows the result only inside that configuration panel, which is a page you visit when you are changing something rather than one you check.

Spook enhances the energy dashboard by taking Home Assistant's own validation and raising a {term}`repairs <repairs>` issue for it, so a removed entity comes to you instead of waiting to be found.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown referenced entities

Spook runs Home Assistant's own energy validation and looks for the one result that means a reference has gone stale: an entity that has no state at all, because it was removed. The other results it can report are either transient (an entity that happens to be unavailable right now) or a configuration choice rather than a mistake, so Spook leaves those alone.

What this buys you is where the answer appears. The dashboard itself does not complain: it draws the sources it can still read and leaves out the one it cannot, so the graph stays plausible while quietly being wrong. A missing gas sensor does not look like an error, it looks like a month where you used no gas.

To resolve the raised issue, go to Settings > Dashboards > Energy and update or remove these entities. Spook will automatically remove the repair issue once the issue is fixed.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Replacing an energy meter. The new integration gives you new entity IDs, the energy dashboard keeps the old ones, and the totals silently stop adding up.
- Renaming a sensor that feeds the dashboard. Renaming is cheap and easy to do, which is exactly why it is easy to forget that the energy configuration was pointing at the old name.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
