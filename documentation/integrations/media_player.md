---
subject: Enhanced integrations
title: Media player
subtitle: Turn it up, just a little. 🔊
description: Spook adds actions that turn a media player's volume up or down by exactly the step you give.
date: 2026-10-04T19:00:00+02:00
---

```{image} https://brands.home-assistant.io/media_player/icon.png
:alt: The Home Assistant media player icon
:width: 250px
:align: center
```

<br><br>

The media player {term}`integration <integration>` is how {term}`Home Assistant` controls speakers, televisions, receivers and everything else that plays.

Home Assistant has volume up and volume down, but how far those go is up to the player: its own step, or the press of its own button. Spook adds a step you choose.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Increase volume

Turn a media player's volume up by exactly the step you give, stopping at full volume.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Media player: Increase volume 👻
* - {term}`Action name`
  - `media_player.increase_volume`
* - {term}`Action targets`
  - Yes, `media_player` entities that can set their volume
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=media_player.increase_volume)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=media_player.increase_volume)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `step`
  - {term}`integer <integer>`
  - Yes
  - `5`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: media_player.increase_volume
target:
  entity_id: media_player.kitchen
data:
  step: 5
```

:::

### Decrease volume

Turn a media player's volume down by exactly the step you give, stopping at silent.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Media player: Decrease volume 👻
* - {term}`Action name`
  - `media_player.decrease_volume`
* - {term}`Action targets`
  - Yes, `media_player` entities that can set their volume
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=media_player.decrease_volume)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=media_player.decrease_volume)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `step`
  - {term}`integer <integer>`
  - Yes
  - `5`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: media_player.decrease_volume
target:
  entity_id: media_player.kitchen
data:
  step: 10
```

:::

Both actions work the same way:

- The step is required, in percent of full volume. A step that would go past full volume or silence stops there.
- Home Assistant's own `media_player.volume_up` and `media_player.volume_down` remain for when the player's own step will do.
- Muting is left alone: turning the volume of a muted player changes the level it comes back at.

:::{attention} Known limitations
:class: dropdown

- A player with only volume up and down buttons, and no volume level to set, cannot be targeted.
- A player that does not report its volume, which many do while off, is left alone.

:::

## Repairs

Spook has no repair detections for this integration.
