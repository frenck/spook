---
subject: Enhanced integrations
title: Timer
subtitle: Ready, set, go! ⏲
description: Spook adds a new action to the timer integration, which allows you to set the duration of an existing timer entity.
date: 2023-11-04T02:05:00+02:00
---

```{image} https://brands.home-assistant.io/timer/icon.png
:alt: The Home Assistant timer icon
:width: 250px
:align: center
```

<br><br>

The timer {term}`helper` in {term}`Home Assistant` aims to simplify {term}`automations <automation>` based on (dynamic) durations.

Spook adds a new action to the timer {term}`integration <integration>`, which allows you to set the duration of a timer to a given value.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Set duration

Set the duration for a timer entity.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Timer: Set duration 👻
* - {term}`Action name`
  - `timer.set_duration`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.set_duration)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.set_duration)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `duration`
  - {term}`string <string>`
  - Yes
  - 00:01:00, 60
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: timer.set_duration
data:
  entity_id: timer.my_timer
  duration: "00:15:00"
```

:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Quickly, with a single action, set the duration of a timer without having to got through the UI.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
