---
subject: Enhanced integrations
title: Humidifier
subtitle: Not too dry, not too damp. 💧
description: Spook adds actions that turn a humidifier's target humidity up or down a step.
date: 2026-10-04T16:00:00+02:00
---

```{image} https://brands.home-assistant.io/humidifier/icon.png
:alt: The Home Assistant humidifier icon
:width: 250px
:align: center
```

<br><br>

The humidifier {term}`integration <integration>` is how {term}`Home Assistant` controls humidifiers and dehumidifiers.

Home Assistant can set a humidifier to a target humidity, but not turn it up a step. Spook adds the step, the same way it does for [thermostats](climate) and [water heaters](water_heater).

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Increase humidity

Turn up a humidifier's target humidity a step, within the limits it reports.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Humidifier: Increase humidity 👻
* - {term}`Action name`
  - `humidifier.increase_humidity`
* - {term}`Action targets`
  - Yes, `humidifier` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=humidifier.increase_humidity)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=humidifier.increase_humidity)
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
  - No
  - The humidifier's own step
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: humidifier.increase_humidity
target:
  entity_id: humidifier.bedroom
data:
  step: 5
```

:::

### Decrease humidity

Turn down a humidifier's target humidity a step, within the limits it reports.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Humidifier: Decrease humidity 👻
* - {term}`Action name`
  - `humidifier.decrease_humidity`
* - {term}`Action targets`
  - Yes, `humidifier` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=humidifier.decrease_humidity)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=humidifier.decrease_humidity)
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
  - No
  - The humidifier's own step
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: humidifier.decrease_humidity
target:
  entity_id: humidifier.bedroom
```

:::

Both actions work the same way:

- The step is the one you give, or the humidifier's own step, or one percent when it has none, the same as the slider in the Home Assistant interface.
- Steps are whole percentages, since Home Assistant hands a humidifier its target as a whole number. A step of its own that is not one, like half a percent, moves a whole percent.
- The target stays within the minimum and maximum the humidifier reports. A step that would cross one stops at it.
- Adjusting is not switching. A humidifier that is off gets its target moved and stays off.

:::{attention} Known limitations
:class: dropdown

- A humidifier that has not reported a target yet is left alone.
- A target already past one of the humidifier's own limits, which some integrations report, is left where it is rather than pulled back.

:::

## Repairs

Spook has no repair detections for this integration.
