---
subject: Enhanced integrations
title: HACS
subtitle: Skip the wait on HACS's own update check.
description: Spook adds a button that asks Home Assistant to poll every HACS update entity right away, instead of waiting for HACS's own scheduled check.
date: 2026-09-04T00:00:00+02:00
---

```{image} https://brands.home-assistant.io/hacs/logo.png
:alt: The HACS logo
:width: 250px
:align: center
```

<br><br>

[HACS](https://hacs.xyz) is a third-party {term}`integration` that lets you install and track community-made integrations, Lovelace cards, and other add-ons from outside the Home Assistant default repositories. It already creates an {term}`entity` of the {term}`update` {term}`platform` for every repository it tracks, complete with an install button, so those show up in Home Assistant's own updates overview without Spook's help.

HACS checks those repositories for updates on its own schedule, spread out so it does not burn through GitHub's rate limit checking hundreds of repositories at once. That pace is right for HACS as a whole, and the wrong one for somebody who has just pushed a new release of their own integration or card and wants Home Assistant to notice it now, rather than whenever HACS gets around to it.

Spook adds a single button for that: pressing it has Home Assistant poll every one of HACS's update entities immediately, the same as calling the `homeassistant.update_entity` {term}`action` on all of them by hand from Developer Tools.

## Devices & entities

Spook adds a single new device with an entity for this integration to your Home Assistant instance, shown only while HACS itself is set up.

### Buttons

#### Check for updates

_Default {term}`entity ID <Entity ID>`: `button.hacs_check_for_updates`_

Asks Home Assistant to immediately check every HACS-tracked {term}`update` entity for a newer version, instead of waiting for HACS's own scheduled check.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

Spook has no repair detections for this integration.

## Use cases

Some use cases for the enhancement Spook provides for this integration:

- Press the button right after pushing a release of an integration or card you develop yourself, so it shows up as an available update straight away instead of after HACS's next scheduled scan.
- Call the button's underlying `button.press` {term}`action` from an automation right after you know a repository you track was updated.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
