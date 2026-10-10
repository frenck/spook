---
subject: Enhanced integrations
title: Alert
subtitle: An alarm nobody hears is just furniture.
description: Spook enhances the Home Assistant alert integration by reporting alerts that watch an entity that no longer exists, or that notify through actions Home Assistant does not have.
date: 2026-08-21T12:10:00+02:00
---

```{image} https://brands.home-assistant.io/alert/logo.png
:alt: The Home Assistant alert logo
:width: 250px
:align: center
```

<br><br>

The alert {term}`integration <integration>` in {term}`Home Assistant` watches a single {term}`entity` and, when that entity enters a state you named, keeps notifying you at an interval until somebody acknowledges it. The classic use is the garage door that is still open, or the freezer that is getting warm.

Alerts are configured in {term}`YAML` only, and they are the kind of thing you set up once and then forget about, which is rather the point. That also means nothing tells you when one quietly stops working.

Spook enhances the alert integration by raising {term}`repairs <repairs>` issues when it finds an alert that can no longer do its job.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown watched entity

An alert only ever watches the one entity named in its `entity_id`. Spook inspects every alert to find the ones watching an entity that no longer exists. If Spook finds such a case, it will raise a repair issue, naming the alert and the entity that is missing.

An alert like that can never fire again, and there is nothing to see: an alert with nothing to report and an alert watching a ghost look exactly the same from the outside.

To resolve the raised issue, edit the `alert:` section of your configuration and point the alert at an entity that exists. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown notifiers

An alert sends its notifications through the {term}`actions <performing actions>` named in its `notifiers:` list, where `my_phone` means the `notify.my_phone` action. Spook inspects every alert to find notifiers that Home Assistant does not have. If Spook finds such a case, it will raise a repair issue, naming the alert and the actions that are missing.

The alert itself carries on: it fires, it repeats, it can be acknowledged. Only the notification goes nowhere. Home Assistant does write an error to the log about it, but it writes that error at the moment the alert fires, which is the worst possible moment to discover that nobody was listening.

To resolve the raised issue, edit the `notifiers:` list of that alert and remove or correct the entries. Spook will automatically remove the repair issue once the issue is fixed.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Renaming the sensor an alert watches. The alert keeps the old name and goes silent, and because a quiet alert is the normal state of a healthy alert, nothing looks wrong.
- Removing or replacing a notify integration. Every alert that named one of its actions keeps firing into the void.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
