---
subject: Enhanced integrations
title: Sensor
subtitle: How many decimals is too many decimals?
description: Spook adds a new action to the sensor integration, which allows you to set the number of decimals shown for one or more sensors at once.
date: 2026-08-30T12:00:00+02:00
---

```{image} https://brands.home-assistant.io/sensor/logo.png
:alt: The Home Assistant sensor icon
:width: 250px
:align: center
```

<br><br>

The sensor {term}`integration <integration>` is the one that reports things: temperatures, power usage, how full the bins are. Most {term}`integrations <integration>` you install bring some along.

Home Assistant lets you set how many decimals a sensor shows, but only one sensor at a time, by opening its settings in the UI. That is fine for one. It is less fine when an integration hands you forty power sensors that all report six decimals.

Spook adds an action that sets the display precision on as many sensors as you like in a single call.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Set display precision

Sets the number of decimals shown for one or more sensors.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Set display precision 👻
* - {term}`Action name`
  - `sensor.set_display_precision`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=sensor.set_display_precision)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=sensor.set_display_precision)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `entity_id`
  - {term}`string <string>` or {term}`list <list>`
  - Yes
  - `"sensor.living_room_temperature"`
* - `display_precision`
  - {term}`integer <integer>`
  - Yes
  - `1`
```

:::{note}
This is the same setting you find under a sensor's own settings in the UI, so
it survives restarts and applies everywhere the sensor is shown.

Every entity you name is looked up before any of them are changed. If one of
them does not exist, the whole call fails and nothing is touched, rather than
leaving you with half your sensors updated and nothing saying which half.
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: sensor.set_display_precision
data:
  entity_id:
    - sensor.living_room_temperature
    - sensor.bedroom_temperature
  display_precision: 1
```

:::

## Repairs

Spook has no repair detections for this integration.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Trim every sensor an integration added down to a sensible number of decimals in one action, instead of opening each one in the UI.
- Show more decimals on a sensor temporarily, for example while working out why a reading looks wrong, and set it back afterwards.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
