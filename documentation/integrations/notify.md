---
subject: Enhanced integrations
title: Notify
subtitle: A message nobody receives is just a thought.
description: Spook enhances the Home Assistant notify integration by reporting notify groups that forward to actions Home Assistant does not have.
date: 2026-08-21T13:20:00+02:00
---

```{image} https://brands.home-assistant.io/notify/logo.png
:alt: The Home Assistant notify logo
:width: 250px
:align: center
```

<br><br>

The notify {term}`integration <integration>` in {term}`Home Assistant` sends messages to people. One of the things you can build with it is a notify group: a single {term}`action <performing actions>` that forwards whatever you send it to a list of other notify actions, so one call reaches everybody.

Spook enhances the notify integration by raising {term}`repairs <repairs>` issues when it finds a notify group that can no longer reach all of its members.

:::{note}
This is about the notify group you configure in {term}`YAML` under `notify:`, the one whose members are action names:

```yaml
notify:
  - platform: group
    name: everyone
    services:
      - action: phone
      - action: tablet
```

The newer notify group, the one you create as a helper and whose members are notify {term}`entities <entity>`, is covered by the [](group) page instead.
:::

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown group members

Every member of a notify group is the name of another notify action, so `phone` in the configuration means the `notify.phone` action. Spook inspects every legacy YAML notify group to find members Home Assistant does not have. If Spook finds such a case, it will raise a repair issue, naming the group and the actions that are missing.

The group keeps working, which is the problem. It fires its members off as background tasks and waits on them with `asyncio.wait`, which does not re-raise, so the group action reports success to whatever called it no matter how many members failed. From the outside, the notification went out.

The failure is not lost entirely. Nobody reads the task result, so the event loop eventually reports it as a stray `Task exception was never retrieved`. That arrives whenever the task happens to be collected, names no group, and reads like a bug rather than something you configured, so it is a poor way to discover that one person stopped being notified.

To resolve the raised issue, edit the `services:` list of that group in your configuration and remove or correct the entries. Spook will automatically remove the repair issue once the issue is fixed.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Replacing a phone, and with it the notify action it was set up under. Every group that still names the old one keeps sending into nothing.
- Removing a notify integration you no longer use. The groups that forwarded to it never mention that they lost a member.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
