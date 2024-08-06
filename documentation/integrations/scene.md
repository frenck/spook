---
subject: Enhanced integrations
title: Scenes
subtitle: Whatever the scene states, it's not over yet.
thumbnail: ../images/integrations/scene/unknown_entity.png
description: Spook enhances the scene integration of Home Assistant by raising repairs issues, in case it detects something is wrong with a scene, like for example, used non-existing entities.
date: 2023-09-27T21:23:46+02:00
---

```{image} https://brands.home-assistant.io/scene/logo.png
:alt: The Home Assistant scene icon
:width: 250px
:align: center
```

<br><br>

A scene in {term}`Home Assistant` is a collection of {term}`entities <entity>` and their states. Scenes are used to set a predefined state for a group of entities. For example, a scene can be used to set the lights in your living room to a specific color and brightness or to set your media player's volume to a specific level and all restored to that stored state when the scene is activated.

Spook enhances the scene integration of Home Assistant by raising {term}`repairs <repairs>` issues in case it detects something is wrong with a scene.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown referenced entities

Scenes are inspected for the use of {term}`entities <entity>`. If a scene uses an {term}`entity ID <entity id>` that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the scene and the entity ID that is referenced but not found.

```{figure} ../images/integrations/scene/unknown_entity.png
:name: unknown entity
:alt: Screenshot showing a repair raised by Spook for a scene.
:align: center

Spook found an issue with a scene that is using non-existing entities.
```

To resolve the raised issue, you can either remove the reference to the non-existing entity ID or fix the referenced entity ID. Spook will automatically remove the repair issue once the issue is fixed.

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
